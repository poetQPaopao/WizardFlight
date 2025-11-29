"""Audio input helper using AssemblyAI streaming.

The `AudioListener` class can run continuously, mirroring the behaviour in
`test/whisperTest.py`. As streaming audio arrives, the latest transcript is kept
in the public `command` attribute so other subsystems can poll for updates.
"""
from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import List, Optional, Sequence, Type

import numpy as np
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

	def __init__(self, sample_rate: int = 48000, device_index: Optional[int] = None, channel_mapping: Optional[List[int]] = None):
		self.sample_rate = sample_rate
		self.device_index = device_index
		self.channel_mapping = channel_mapping

	def __iter__(self):
		if _sd is None:
			raise RuntimeError("sounddevice is not installed")
		
		# Check device capabilities to avoid requesting more channels than available
		max_hw_channels = 1
		try:
			info = _sd.query_devices(device=self.device_index, kind='input')
			max_hw_channels = int(info.get('max_input_channels', 1))
		except Exception:
			pass

		# Determine required number of channels to capture
		req_channels = 1
		if self.channel_mapping:
			# We need at least the highest channel index requested
			req_channels = max(self.channel_mapping)
			
			# DJI Fix: If hardware supports >= 2 channels, force 2 channels
			# to prevent driver-side mono downmixing when only Ch 1 is requested.
			if max_hw_channels >= 2:
				req_channels = max(req_channels, 2)
			
			# Clamp to hardware limit to prevent "Invalid number of channels" error
			req_channels = min(req_channels, max_hw_channels)
		
		kwargs = {
			"samplerate": self.sample_rate,
			"device": self.device_index,
			"dtype": "int16",
			"channels": req_channels,
		}
		
		# AssemblyAI requires chunks > 50ms. 
		# We'll use ~100ms chunks (e.g. 4800 samples at 48kHz).
		chunk_size = int(self.sample_rate * 0.1)

		with _sd.InputStream(**kwargs) as stream:
			while True:
				data, overflowed = stream.read(chunk_size)
				# data is a numpy array of shape (frames, channels)
				
				if self.channel_mapping:
					# Extract specific channels based on mapping (1-based indices)
					# We want to select specific columns.
					# e.g. mapping=[1] -> column 0
					# e.g. mapping=[2] -> column 1
					indices = [m - 1 for m in self.channel_mapping]
					
					# Ensure we don't go out of bounds (though req_channels should prevent this)
					valid_indices = [i for i in indices if i < data.shape[1]]
					
					if valid_indices:
						selected = data[:, valid_indices]
						# AssemblyAI expects mono usually, or we just send the selected channels.
						# If multiple channels selected, it sends them interleaved.
						yield selected.tobytes()
					else:
						yield data.tobytes()
				else:
					yield data.tobytes()


def _get_api_key() -> Optional[str]:
	"""Return the AssemblyAI API key, preferring the environment variable."""
	return os.getenv("ASSEMBLYAI_API_KEY", "995e19ff8cc5433787f017cd20f226c3")


class AudioListener:
	"""Streaming microphone listener that keeps the latest transcript."""

	def __init__(self, sample_rate: int = 48000, *, device_index: Optional[int] = None, source_name: Optional[str] = None, channel_mapping: Optional[List[int]] = None) -> None:
		self.sample_rate = sample_rate
		self.device_index = device_index
		self.channel_mapping = channel_mapping
		self.source_name = source_name or (f"mic-{device_index}" if device_index is not None else "mic-default")
		self.api_key = _get_api_key()
		if not self.api_key:
			raise RuntimeError("ASSEMBLYAI_API_KEY is not set")

		self.command: str = ""
		self.command_stage: str = ""
		self._command_seq: int = 0
		self._command_consumed: int = 0
		self._latest_stage: str = ""
		self._latest_sequence: int = 0

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

		self._error = None
		self._final_event.clear()
		self._command_consumed = self._command_seq

		client = StreamingClient(
			StreamingClientOptions(
				api_key=self.api_key,
				api_host="streaming.assemblyai.com",
			)
		)

		def on_begin(self_client: Type[StreamingClient], event: BeginEvent):
			return None

		def on_turn(self_client: Type[StreamingClient], event: TurnEvent):
			if not event.transcript:
				return
			text = event.transcript.strip().lower()
			stage = "final" if event.end_of_turn else "partial"
			incremented = False
			with self._lock:
				self.command = text
				self.command_stage = stage
				self._latest_stage = stage
				self._latest_sequence = self._command_seq
				if event.end_of_turn:
					self._command_seq += 1
					incremented = True
			if event.end_of_turn and not event.turn_is_formatted:
				params = StreamingSessionParameters(format_turns=True)
				self_client.set_params(params)
			if event.end_of_turn and incremented:
				self._final_event.set()

		def on_terminated(self_client: Type[StreamingClient], event: TerminationEvent):
			self._final_event.set()
			self._running = False

		def on_error(self_client: Type[StreamingClient], error: StreamingError):
			self._error = str(error)
			self._final_event.set()
			self._running = False

		client.on(StreamingEvents.Begin, on_begin)
		client.on(StreamingEvents.Turn, on_turn)
		client.on(StreamingEvents.Termination, on_terminated)
		client.on(StreamingEvents.Error, on_error)

		client.connect(
			StreamingParameters(
				sample_rate=self.sample_rate,
				format_turns=True,
			)
		)

		def _stream_thread():
			try:
				print(f"[voice:{self.source_name}] opening microphone with rate={self.sample_rate}, device={self.device_index}, mapping={self.channel_mapping}")
				mic = ChannelSelectMicrophoneStream(
					sample_rate=self.sample_rate,
					device_index=self.device_index,
					channel_mapping=self.channel_mapping
				)
				client.stream(mic)
			except Exception as exc:
				self._error = str(exc)
				print(f"[voice:{self.source_name}] stream error: {exc}")
			finally:
				try:
					client.disconnect(terminate=True)
				except Exception:
					pass
				self._running = False

		self._client = client
		self._thread = threading.Thread(target=_stream_thread, daemon=True)
		self._thread.start()
		self._running = True

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
	print("\nAudio Configuration Mode:")
	print("1. Dual Device (Two separate microphones)")
	print("2. Single Device (Stereo Split - Left=P1, Right=P2)")
	
	mode = "1"
	while True:
		try:
			mode = input("Select mode (1/2) [default: 1]: ").strip() or "1"
			if mode in ("1", "2"):
				break
			print("Invalid selection.")
		except KeyboardInterrupt:
			raise MicrophoneConfigurationCancelled

	configs: List[AudioInputConfig] = []

	if mode == "2":
		# Stereo Split Mode
		print("\n[Stereo Split Mode] Select the single device for both players.")
		device_index = _prompt_for_device_index("Stereo Input")
		
		if len(player_names) >= 1:
			# Player 1 -> Left Channel (1)
			p1_source = player_names[0]
			configs.append(AudioInputConfig(
				source=p1_source, 
				device_index=device_index, 
				channel_mapping=[1]
			))
			print(f"[voice] {p1_source} mapped to Left Channel of device {device_index}")

		if len(player_names) >= 2:
			# Player 2 -> Right Channel (2)
			p2_source = player_names[1]
			configs.append(AudioInputConfig(
				source=p2_source, 
				device_index=device_index, 
				channel_mapping=[2]
			))
			print(f"[voice] {p2_source} mapped to Right Channel of device {device_index}")

	else:
		# Dual Device Mode (Original)
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

