"""Audio input helper using AssemblyAI streaming.

The `AudioListener` class can run continuously, mirroring the behaviour in
`test/whisperTest.py`. As streaming audio arrives, the latest transcript is kept
in the public `command` attribute so other subsystems can poll for updates.
"""
from __future__ import annotations

import os
import threading
from typing import Optional, Type

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


def _get_api_key() -> Optional[str]:
	"""Return the AssemblyAI API key, preferring the environment variable."""
	return os.getenv("ASSEMBLYAI_API_KEY", "995e19ff8cc5433787f017cd20f226c3")


class AudioListener:
	"""Streaming microphone listener that keeps the latest transcript."""

	def __init__(self, sample_rate: int = 16000) -> None:
		self.sample_rate = sample_rate
		self.api_key = _get_api_key()
		if not self.api_key:
			raise RuntimeError("ASSEMBLYAI_API_KEY is not set")

		self.command: str = ""
		self.command_stage: str = ""
		self._command_seq: int = 0
		self._command_consumed: int = 0

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
				mic = aai.extras.MicrophoneStream(sample_rate=self.sample_rate)
				client.stream(mic)
			except Exception as exc:
				self._error = str(exc)
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

	def consume_final(self) -> str:
		"""Return the newest final transcript once, or "" if nothing fresh."""

		with self._lock:
			if self.command_stage != "final" or not self.command:
				return ""
			if self._command_consumed == self._command_seq:
				return ""
			text = self.command
			self._command_consumed = self._command_seq
		return text

	@property
	def error(self) -> Optional[str]:
		"""Return the most recent streaming error, if any."""

		return self._error

	@property
	def running(self) -> bool:
		"""Return ``True`` while the microphone stream is active."""

		return self._running


__all__ = ["AudioListener"]

