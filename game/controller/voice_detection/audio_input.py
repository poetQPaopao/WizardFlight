"""Audio input helper using AssemblyAI streaming.

The ``AudioListener`` class can run continuously, mirroring the behaviour in
``test/whisperTest.py``. As streaming audio arrives, the latest transcript is
kept in the public ``command`` attribute so other subsystems can poll for
updates.
"""
from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional, Sequence, Type

import assemblyai as aai
from assemblyai.streaming.v3 import (
    BeginEvent,
    StreamingClient,
    StreamingClientOptions,
    StreamingError,
    StreamingEvents,
    StreamingParameters,
    StreamingSessionParameters,
    TerminationEvent,
    TurnEvent,
)

try:
    import sounddevice as _sd
except ImportError:
    _sd = None


@dataclass(frozen=True)
class TranscriptEvent:
    """Represents a transcript update emitted from a specific audio source."""

    source_index: int
    source: str
    text: str
    stage: str
    sequence: int


@dataclass(frozen=True)
class AudioInputConfig:
    """Configuration describing how a device/channel maps to one audio source."""

    source_index: int
    device_index: Optional[int] = None
    sample_rate: int = 48000
    channel_mapping: Optional[List[int]] = None
    label: Optional[str] = None


def list_input_devices() -> List[tuple[int, str]]:
    """Return ``(index, name)`` pairs for available audio input devices."""

    devices: List[tuple[int, str]] = []
    if _sd is not None:
        try:
            for idx, info in enumerate(_sd.query_devices()):
                if info.get("max_input_channels", 0) > 0:
                    name = info.get("name", f"Device {idx}")
                    host = info.get("hostapi")
                    if host is not None and 0 <= host < len(_sd.query_hostapis()):
                        host_name = _sd.query_hostapis()[host].get("name", "")
                        if host_name:
                            name = f"{name} ({host_name})"
                    devices.append((idx, name))
        except Exception:
            devices = []
    if devices:
        return devices

    try:
        pa = aai.extras.pyaudio.PyAudio()
    except Exception:
        return []
    try:
        device_count = pa.get_device_count()
        for idx in range(device_count):
            info = pa.get_device_info_by_index(idx)
            if info.get("maxInputChannels", 0) > 0:
                devices.append((idx, info.get("name", f"Device {idx}")))
    finally:
        pa.terminate()
    return devices


def max_input_channels(device_index: Optional[int]) -> int:
    """Return the maximum input channels supported by a device index."""

    if device_index is None:
        return 1

    if _sd is not None:
        try:
            info = _sd.query_devices(device=device_index, kind="input")
            channels = int(info.get("max_input_channels", 0))
            if channels > 0:
                return channels
        except Exception:
            pass

    try:
        pa = aai.extras.pyaudio.PyAudio()
    except Exception:
        return 1
    try:
        info = pa.get_device_info_by_index(device_index)
        return int(info.get("maxInputChannels", 0))
    except Exception:
        return 1
    finally:
        try:
            pa.terminate()
        except Exception:
            pass


class ChannelSelectMicrophoneStream:
    """Custom microphone stream that supports channel selection via mapping."""

    def __init__(
        self,
        sample_rate: int = 48000,
        device_index: Optional[int] = None,
        channel_mapping: Optional[List[int]] = None,
    ) -> None:
        """Persist the capture parameters used for building the iterator."""

        self.sample_rate = sample_rate
        self.device_index = device_index
        self.channel_mapping = channel_mapping

    def __iter__(self):
        """Yield PCM chunks while optionally remapping requested channels."""

        if _sd is None:
            raise RuntimeError("sounddevice is not installed")

        max_hw_channels = self._max_input_channels()
        req_channels = self._required_channels(max_hw_channels)
        kwargs = {
            "samplerate": self.sample_rate,
            "device": self.device_index,
            "dtype": "int16",
            "channels": req_channels,
        }
        chunk_size = self._chunk_size()

        with _sd.InputStream(**kwargs) as stream:
            while True:
                data, _ = stream.read(chunk_size)
                yield self._select_channels(data).tobytes()

    def _max_input_channels(self) -> int:
        return max_input_channels(self.device_index)

    def _required_channels(self, max_hw_channels: int) -> int:
        if not self.channel_mapping:
            return 1

        required = max(self.channel_mapping)
        if max_hw_channels >= 2:
            # Prevent driver-side mono downmixing when only the first channel is requested.
            required = max(required, 2)
        return min(required, max_hw_channels)

    def _chunk_size(self) -> int:
        # AssemblyAI requires chunks > 50ms. Use ~100ms chunks (e.g. 4800 samples at 48kHz).
        return int(self.sample_rate * 0.1)

    def _select_channels(self, data):
        if not self.channel_mapping:
            return data

        indices = [m - 1 for m in self.channel_mapping if (m - 1) < data.shape[1]]
        if not indices:
            return data
        return data[:, indices]


def _get_api_key() -> Optional[str]:
    """Return the AssemblyAI API key, preferring the environment variable."""

    return os.getenv("ASSEMBLYAI_API_KEY", "995e19ff8cc5433787f017cd20f226c3")


class AudioListener:
    """Streaming microphone listener that keeps the latest transcript."""

    def __init__(
        self,
        source_index: int,
        sample_rate: int = 48000,
        *,
        source_name: Optional[str] = None,
        api_key: Optional[str] = None,
        microphone_stream_factory: Optional[Callable[[], Iterable[bytes]]] = None,
        stream_description: Optional[str] = None,
    ) -> None:
        """Configure AssemblyAI streaming with the given audio source details."""

        self.source_index = source_index
        self.sample_rate = sample_rate
        self.source_name = source_name or f"source-{source_index}"
        self.api_key = api_key or _get_api_key()
        if not self.api_key:
            raise RuntimeError("ASSEMBLYAI_API_KEY is not set")

        self._microphone_stream_factory = microphone_stream_factory
        self._stream_description = stream_description

        self.command: str = ""
        self.command_stage: str = ""
        self._command_seq: int = 0
        self._command_consumed: int = 0
        self._latest_stage: str = ""
        self._latest_sequence: int = 0
        self._awaiting_formatted_final: bool = False

        self._client: Optional[StreamingClient] = None
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._final_event = threading.Event()
        self._running = False
        self._error: Optional[str] = None

    def start(self) -> None:
        """Begin microphone streaming and update ``command`` as audio arrives."""

        if self._running:
            return

        self._reset_state()
        client = self._create_client()
        self._register_client_handlers(client)
        client.connect(
            StreamingParameters(
                sample_rate=self.sample_rate,
                format_turns=True,
            )
        )
        self._launch_stream_thread(client)

    def _reset_state(self) -> None:
        self._error = None
        self._final_event.clear()
        self._command_consumed = self._command_seq
        self._awaiting_formatted_final = False

    def _create_client(self) -> StreamingClient:
        return StreamingClient(
            StreamingClientOptions(
                api_key=self.api_key,
                api_host="streaming.assemblyai.com",
            )
        )

    def _register_client_handlers(self, client: StreamingClient) -> None:
        client.on(StreamingEvents.Begin, self._handle_begin)
        client.on(StreamingEvents.Turn, self._handle_turn)
        client.on(StreamingEvents.Termination, self._handle_termination)
        client.on(StreamingEvents.Error, self._handle_error)

    def _handle_begin(self, self_client: Type[StreamingClient], event: BeginEvent) -> None:  # noqa: ARG002
        return None

    def _handle_turn(self, self_client: Type[StreamingClient], event: TurnEvent) -> None:
        if not event.transcript:
            return
        text = event.transcript.strip().lower()
        stage = "final" if event.end_of_turn else "partial"
        with self._lock:
            self.command = text
            self.command_stage = stage
            self._latest_stage = stage
            self._latest_sequence = self._command_seq
        if not event.end_of_turn:
            return

        # AssemblyAI may send an unformatted final first, followed by a formatted
        # final (with punctuation). Only mark the turn complete on a formatted
        # final to avoid double final events for the same utterance.
        if not event.turn_is_formatted:
            self._awaiting_formatted_final = True
            params = StreamingSessionParameters(format_turns=True)
            self_client.set_params(params)
            return

        self._awaiting_formatted_final = False
        with self._lock:
            self._command_seq += 1
            self._latest_sequence = self._command_seq
        self._final_event.set()

    def _handle_termination(self, self_client: Type[StreamingClient], event: TerminationEvent) -> None:  # noqa: ARG002
        self._final_event.set()
        self._running = False

    def _handle_error(self, self_client: Type[StreamingClient], error: StreamingError) -> None:  # noqa: ARG002
        self._error = str(error)
        self._final_event.set()
        self._running = False

    def _launch_stream_thread(self, client: StreamingClient) -> None:
        def _stream_thread() -> None:
            try:
                desc = f", {self._stream_description}" if self._stream_description else ""
                print(f"[voice:{self.source_name}] opening microphone with rate={self.sample_rate}{desc}")
                mic = self._build_microphone_stream()
                client.stream(mic)
            except Exception as exc:  # pragma: no cover - safety logging
                self._error = str(exc)
                print(f"[voice:{self.source_name}] stream error: {exc}")
            finally:
                self._cleanup_client(client)

        self._client = client
        self._thread = threading.Thread(target=_stream_thread, daemon=True)
        self._thread.start()
        self._running = True

    def _build_microphone_stream(self) -> ChannelSelectMicrophoneStream:
        if self._microphone_stream_factory:
            stream = self._microphone_stream_factory()
            if stream is None:
                raise RuntimeError("microphone_stream_factory returned no stream")
            return stream
        return ChannelSelectMicrophoneStream(
            sample_rate=self.sample_rate,
        )

    def _cleanup_client(self, client: StreamingClient) -> None:
        try:
            client.disconnect(terminate=True)
        except Exception:
            pass
        self._running = False

    def stop(self) -> None:
        """Stop streaming and release resources."""

        if not self._running:
            return

        self._running = False

        if self._client is not None:
            try:
                self._client.disconnect(terminate=True)
            except Exception:
                pass

        if self._thread is not None:
            self._thread.join(timeout=1.5)

        self._client = None
        self._thread = None

    def listen_once(self, timeout_s: float = 8.0) -> str:
        """Convenience wrapper that waits for a final transcript and stops."""

        self.start()
        finished = self._final_event.wait(timeout=timeout_s)
        if not finished:
            self.stop()
            return self.command

        result = self.consume_final() or self.command
        self.stop()
        return result

    def consume_final_event(self) -> Optional[TranscriptEvent]:
        """Return the newest final transcript, tagged with its audio source."""

        with self._lock:
            if self.command_stage != "final" or not self.command:
                return None
            if self._command_consumed == self._command_seq:
                return None
            text = self.command
            sequence = self._command_seq
            self._command_consumed = sequence
        return TranscriptEvent(
            source_index=self.source_index,
            source=self.source_name,
            text=text,
            stage="final",
            sequence=sequence,
        )

    def consume_final(self) -> str:
        """Backward-compatible helper that returns only the transcript text."""

        event = self.consume_final_event()
        return event.text if event else ""

    def snapshot(self) -> TranscriptEvent:
        """Return the latest transcript state (partial or final) for this source."""

        with self._lock:
            return TranscriptEvent(
                source_index=self.source_index,
                source=self.source_name,
                text=self.command,
                stage=self.command_stage,
                sequence=self._latest_sequence,
            )

    @property
    def source(self) -> str:
        """Human-readable name for the audio source."""

        return self.source_name

    @property
    def error(self) -> Optional[str]:
        """Return the most recent streaming error, if any."""

        return self._error

    @property
    def running(self) -> bool:
        """Return ``True`` while the microphone stream is active."""

        return self._running


class AudioController:
    """Manage ``AudioListener`` instances keyed by logical source index."""

    def __init__(
        self,
        configs: Sequence[AudioInputConfig],
        *,
        auto_start: bool = True,
    ) -> None:
        """Spin up listeners for each configuration and optionally start them."""

        if not configs:
            raise ValueError("At least one AudioInputConfig is required")

        self.listeners: List[AudioListener] = []
        seen_indices: set[int] = set()
        for config in configs:
            if config.source_index in seen_indices:
                raise ValueError(f"Duplicate source_index {config.source_index} detected")
            seen_indices.add(config.source_index)

            stream_factory = self._build_stream_factory(config)
            listener = AudioListener(
                source_index=config.source_index,
                sample_rate=config.sample_rate,
                source_name=config.label or f"source-{config.source_index}",
                microphone_stream_factory=stream_factory,
                stream_description=self._stream_description(config),
            )
            self.listeners.append(listener)
        if auto_start:
            self.start()

    def _build_stream_factory(self, config: AudioInputConfig) -> Callable[[], Iterable[bytes]]:
        def _factory() -> ChannelSelectMicrophoneStream:
            return ChannelSelectMicrophoneStream(
                sample_rate=config.sample_rate,
                device_index=config.device_index,
                channel_mapping=config.channel_mapping,
            )

        return _factory

    def _stream_description(self, config: AudioInputConfig) -> Optional[str]:
        parts: list[str] = []
        if config.device_index is not None:
            parts.append(f"device={config.device_index}")
        if config.channel_mapping:
            parts.append(f"channel_mapping={config.channel_mapping}")
        if not parts:
            return None
        return ", ".join(parts)

    def start(self) -> None:
        """Start all underlying listeners."""

        for listener in self.listeners:
            listener.start()

    def stop(self) -> None:
        """Stop all underlying listeners."""

        for listener in self.listeners:
            listener.stop()

    def consume_final_events(self) -> List[TranscriptEvent]:
        """Collect final transcripts from every listener since the last poll."""

        events: List[TranscriptEvent] = []
        for listener in self.listeners:
            event = listener.consume_final_event()
            if event:
                events.append(event)
        return events

    def consume_both_final(self) -> tuple[Optional[str], Optional[str]]:
        """Return final transcripts for the first two sources (left, right)."""

        transcripts: list[Optional[str]] = [None, None]
        for idx, listener in enumerate(self.listeners[:2]):
            event = listener.consume_final_event()
            if event:
                transcripts[idx] = event.text

        if len(self.listeners) == 1:
            return transcripts[0], None
        return transcripts[0], transcripts[1]

    def snapshots(self) -> List[TranscriptEvent]:
        """Return the latest transcript state for each listener."""

        return [listener.snapshot() for listener in self.listeners]

    def errors(self) -> List[tuple[int, str, str]]:
        """Return a list of ``(source_index, source, error)`` tuples for active errors."""

        problems: List[tuple[int, str, str]] = []
        for listener in self.listeners:
            if listener.error:
                problems.append((listener.source_index, listener.source, listener.error))
        return problems

    @property
    def running(self) -> bool:
        """Return ``True`` only if every listener is active."""

        return all(listener.running for listener in self.listeners)

    @staticmethod
    def list_input_devices() -> List[tuple[int, str]]:
        """Return ``(index, name)`` pairs for available audio input devices."""

        return list_input_devices()

    @staticmethod
    def max_input_channels(device_index: Optional[int]) -> int:
        """Return the maximum input channels supported by a device index."""

        return max_input_channels(device_index)


class DualMicAudioController(AudioController):
    """Backward-compatible alias for two-source ``AudioController`` setups."""

    def __init__(
        self,
        configs: Sequence[AudioInputConfig],
        *,
        auto_start: bool = True,
    ) -> None:
        if len(configs) > 2:
            raise ValueError("DualMicAudioController supports at most two microphones")
        super().__init__(configs, auto_start=auto_start)


class MicrophoneConfigurationCancelled(Exception):
    """Raised when the user aborts microphone selection (e.g., via Ctrl+C)."""


def _prompt_for_device_index(player_name: str) -> Optional[int]:
    """Ask the user to select a microphone device for the given player."""

    devices = AudioController.list_input_devices()
    if devices:
        print("\nAvailable microphones:")
        for idx, name in devices:
            print(f"  [{idx}] {name}")
    else:
        print("\nNo audio input devices detected by PyAudio; using system defaults.")
    while True:
        try:
            raw = input(f"Enter microphone device index for {player_name} (blank for default): ").strip()
        except EOFError:
            return None
        except KeyboardInterrupt:
            print()
            raise MicrophoneConfigurationCancelled
        if raw == "":
            return None
        try:
            return int(raw)
        except ValueError:
            print("Please enter a valid integer device index or leave blank.")


def interactive_configure_microphones(player_names: List[str]) -> List[AudioInputConfig]:
    """Interactively build audio configs for the provided player name list."""

    print("\nAudio Configuration Mode:")
    print("1. Single Device (Shared mono input for all players)")
    print("2. Single Device (Multi-channel: separate channels on one device)")
    print("3. Dual Device (Two separate microphones)")

    mode = _prompt_audio_mode()
    if mode == "1":
        return _configure_single_device(player_names)
    if mode == "2":
        return _configure_multi_channel(player_names)
    return _configure_dual_device(player_names)


def _prompt_audio_mode() -> str:
    mode = "1"
    while True:
        try:
            mode = input("Select mode (1/2/3) [default: 1]: ").strip() or "1"
            if mode in ("1", "2", "3"):
                return mode
            print("Invalid selection.")
        except KeyboardInterrupt:
            raise MicrophoneConfigurationCancelled


def _configure_single_device(player_names: List[str]) -> List[AudioInputConfig]:
    print("\n[Single Device Mode] One microphone shared by all players.")
    device_index = _prompt_for_device_index("Shared Input")
    source = "shared-mic"
    if device_index is None:
        print("[voice] shared microphone: default input")
    else:
        print(f"[voice] shared microphone: device index {device_index}")
    return [AudioInputConfig(source_index=0, device_index=device_index, label=source)]


def _configure_multi_channel(player_names: List[str]) -> List[AudioInputConfig]:
    print("\n[Multi-channel Mode] One device with separate channels per player.")
    device_index = _prompt_for_device_index("Multi-Channel Input")
    max_channels = AudioController.max_input_channels(device_index)
    if max_channels < 2:
        print(f"[voice] Device {device_index} supports only {max_channels} channel(s); falling back to mono shared input.")
        return _configure_single_device(player_names)

    configs: List[AudioInputConfig] = []
    if len(player_names) > 2:
        print("[voice] Only the first two players can be mapped to dedicated channels.")
    for idx, name in enumerate(player_names[:2]):
        default_channel = min(idx + 1, max_channels)
        channel = _prompt_for_channel(name, max_channels, default_channel=default_channel)
        configs.append(
            AudioInputConfig(
                source_index=idx,
                device_index=device_index,
                channel_mapping=[channel],
                label=name,
            )
        )
        print(f"[voice] {name} microphone: device {device_index} channel {channel}")
    return configs


def _configure_dual_device(player_names: List[str]) -> List[AudioInputConfig]:
    configs: List[AudioInputConfig] = []
    chosen_devices: set[Optional[int]] = set()
    if len(player_names) > 2:
        print("[voice] Only the first two players can be mapped to dedicated microphones.")
    for idx, name in enumerate(player_names[:2]):
        while True:
            device_index = _prompt_for_device_index(name)
            if device_index in chosen_devices:
                label = "default input" if device_index is None else f"device index {device_index}"
                print(f"[voice] {label} is already assigned. Please choose a different device.")
                continue
            chosen_devices.add(device_index)
            break
        if device_index is None:
            print(f"[voice] {name} microphone: default input")
        else:
            print(f"[voice] {name} microphone: device index {device_index}")

        configs.append(
            AudioInputConfig(
                source_index=idx,
                device_index=device_index,
                label=name,
            )
        )
    return configs


def _prompt_for_channel(player_name: str, max_channels: int, *, default_channel: int = 1) -> int:
    """Prompt the user to select an input channel for a multi-channel device."""

    while True:
        try:
            raw = (
                input(
                    f"Select input channel for {player_name} (1-{max_channels}, default {default_channel}): "
                ).strip()
                or str(default_channel)
            )
            channel = int(raw)
            if 1 <= channel <= max_channels:
                return channel
        except ValueError:
            pass
        except KeyboardInterrupt:
            raise MicrophoneConfigurationCancelled
        print(f"Invalid channel. Please choose a number between 1 and {max_channels}.")


__all__ = [
    "AudioListener",
    "AudioController",
    "AudioInputConfig",
    "TranscriptEvent",
    "DualMicAudioController",
    "MicrophoneConfigurationCancelled",
    "interactive_configure_microphones",
]
