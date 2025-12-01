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
from typing import List, Optional, Sequence, Type

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

    source: str
    text: str
    stage: str
    sequence: int


@dataclass(frozen=True)
class AudioInputConfig:
    """Configuration for wiring a physical microphone to a listener."""

    source: str
    device_index: Optional[int] = None
    sample_rate: int = 48000
    channel_mapping: Optional[List[int]] = None


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
        try:
            info = _sd.query_devices(device=self.device_index, kind="input")
            return int(info.get("max_input_channels", 1))
        except Exception:
            return 1

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
        sample_rate: int = 48000,
        *,
        device_index: Optional[int] = None,
        source_name: Optional[str] = None,
        channel_mapping: Optional[List[int]] = None,
        api_key: Optional[str] = None,
    ) -> None:
        """Configure AssemblyAI streaming with the given audio source details."""

        self.sample_rate = sample_rate
        self.device_index = device_index
        self.channel_mapping = channel_mapping
        self.source_name = source_name or (f"mic-{device_index}" if device_index is not None else "mic-default")
        self.api_key = api_key or _get_api_key()
        if not self.api_key:
            raise RuntimeError("ASSEMBLYAI_API_KEY is not set")

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
                print(
                    f"[voice:{self.source_name}] opening microphone with rate={self.sample_rate}, "
                    f"device={self.device_index}, mapping={self.channel_mapping}"
                )
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
        return ChannelSelectMicrophoneStream(
            sample_rate=self.sample_rate,
            device_index=self.device_index,
            channel_mapping=self.channel_mapping,
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
    def input_device_index(self) -> Optional[int]:
        """Return the PyAudio device index, if one was specified."""

        return self.device_index

    @property
    def error(self) -> Optional[str]:
        """Return the most recent streaming error, if any."""

        return self._error

    @property
    def running(self) -> bool:
        """Return ``True`` while the microphone stream is active."""

        return self._running


class MultiMicAudioController:
    """Manage multiple ``AudioListener`` instances, one per microphone input."""

    def __init__(self, configs: Sequence[AudioInputConfig], *, auto_start: bool = True) -> None:
        """Spin up listeners for each configuration and optionally start them."""

        if not configs:
            raise ValueError("At least one AudioInputConfig is required")
        self.listeners: List[AudioListener] = [
            AudioListener(
                sample_rate=config.sample_rate,
                device_index=config.device_index,
                source_name=config.source,
                channel_mapping=config.channel_mapping,
            )
            for config in configs
        ]
        if auto_start:
            self.start()

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

    def snapshots(self) -> List[TranscriptEvent]:
        """Return the latest transcript state for each listener."""

        return [listener.snapshot() for listener in self.listeners]

    def errors(self) -> List[tuple[str, str]]:
        """Return a list of ``(source, error)`` pairs for active errors."""

        problems: List[tuple[str, str]] = []
        for listener in self.listeners:
            if listener.error:
                problems.append((listener.source, listener.error))
        return problems

    @property
    def running(self) -> bool:
        """Return ``True`` only if every listener is active."""

        return all(listener.running for listener in self.listeners)

    @staticmethod
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


class MicrophoneConfigurationCancelled(Exception):
    """Raised when the user aborts microphone selection (e.g., via Ctrl+C)."""


def _prompt_for_device_index(player_name: str) -> Optional[int]:
    """Ask the user to select a microphone device for the given player."""

    devices = MultiMicAudioController.list_input_devices()
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
    print("1. Dual Device (Two separate microphones)")
    print("2. Single Device (Stereo Split - Left=P1, Right=P2)")

    mode = _prompt_audio_mode()
    if mode == "2":
        return _configure_stereo_split(player_names)
    return _configure_dual_device(player_names)


def _prompt_audio_mode() -> str:
    mode = "1"
    while True:
        try:
            mode = input("Select mode (1/2) [default: 1]: ").strip() or "1"
            if mode in ("1", "2"):
                return mode
            print("Invalid selection.")
        except KeyboardInterrupt:
            raise MicrophoneConfigurationCancelled


def _configure_stereo_split(player_names: List[str]) -> List[AudioInputConfig]:
    print("\n[Stereo Split Mode] Select the single device for both players.")
    device_index = _prompt_for_device_index("Stereo Input")
    configs: List[AudioInputConfig] = []

    if len(player_names) >= 1:
        configs.append(_build_stereo_config(player_names[0], device_index, 1))

    if len(player_names) >= 2:
        configs.append(_build_stereo_config(player_names[1], device_index, 2))

    return configs


def _build_stereo_config(player_name: str, device_index: Optional[int], channel: int) -> AudioInputConfig:
    print(f"[voice] {player_name} mapped to {'Left' if channel == 1 else 'Right'} Channel of device {device_index}")
    return AudioInputConfig(
        source=player_name,
        device_index=device_index,
        channel_mapping=[channel],
    )


def _configure_dual_device(player_names: List[str]) -> List[AudioInputConfig]:
    configs: List[AudioInputConfig] = []
    for name in player_names:
        device_index = _prompt_for_device_index(name)
        configs.append(AudioInputConfig(source=name, device_index=device_index))
        if device_index is None:
            print(f"[voice] {name} microphone: default input")
        else:
            print(f"[voice] {name} microphone: device index {device_index}")
    return configs


__all__ = [
    "AudioListener",
    "AudioInputConfig",
    "TranscriptEvent",
    "MultiMicAudioController",
    "MicrophoneConfigurationCancelled",
    "interactive_configure_microphones",
]
