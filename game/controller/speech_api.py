"""
High-level microphone-to-text API for the game.

Quick start (single-utterance, backwards compatible):
        from game.controller.speech_api import transcribe_once
        text = transcribe_once(timeout_s=8)

Preferred for continuous input (persistent stream):
        from game.controller.speech_api import SpeechStream
        stream = SpeechStream(sample_rate=16000).start()
        while True:
                text = stream.get_next(timeout=0.1)
                if text:
                        print("final:", text)

Notes:
- Requires environment variable ASSEMBLYAI_API_KEY to be set, or the SDK will
    use any configured default key if present. On macOS, ensure mic permission
    for your terminal/editor (System Settings > Privacy & Security > Microphone).
- SpeechStream connects once and continuously yields final turns until stopped.
"""
from __future__ import annotations

import os
import queue
import threading
import time
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
    # Prefer environment variable; fall back to the inline key used in whisperTest.py
    # NOTE: For production, prefer setting ASSEMBLYAI_API_KEY instead of hard-coding.
    return os.getenv("ASSEMBLYAI_API_KEY", "995e19ff8cc5433787f017cd20f226c3")


class SpeechStream:
    """Long-lived microphone streaming session that yields final transcripts.

    Contract:
    - start(): begin streaming mic audio to the service (daemon thread).
    - get_next(timeout): return next final transcript (str) or None on timeout.
    - stop(): gracefully disconnect and stop background thread.
    """

    def __init__(self, sample_rate: int = 16000, format_turns: bool = True) -> None:
        self.sample_rate = sample_rate
        self.format_turns = format_turns
        self._queue: "queue.Queue[str]" = queue.Queue()
        self._client: Optional[StreamingClient] = None
        self._thread: Optional[threading.Thread] = None
        self._running = threading.Event()
        self._started = False
        self._latest: str = ""

    def _build_client(self) -> StreamingClient:
        api_key = _get_api_key()

        def on_begin(self_client: Type[StreamingClient], event: BeginEvent):
            # optionally: could log event.id
            pass

        def on_turn(self_client: Type[StreamingClient], event: TurnEvent):
            # Update latest on any transcript (partial or final)
            if event.transcript:
                self._latest = event.transcript
            # Enqueue only finals for consumers that prefer discrete commands
            if event.transcript and event.end_of_turn:
                # Ensure server formats turns if not already doing so
                if self.format_turns and not event.turn_is_formatted:
                    self_client.set_params(StreamingSessionParameters(format_turns=True))
                self._queue.put(event.transcript)

        def on_terminated(self_client: Type[StreamingClient], event: TerminationEvent):
            # Wake any waiters so get_next can return None when drained
            self._running.clear()

        def on_error(self_client: Type[StreamingClient], error: StreamingError):
            # You can push a sentinel or log; here we just stop the loop
            self._running.clear()

        client = StreamingClient(
            StreamingClientOptions(
                api_key=api_key,
                api_host="streaming.assemblyai.com",
            )
        )
        client.on(StreamingEvents.Begin, on_begin)
        client.on(StreamingEvents.Turn, on_turn)
        client.on(StreamingEvents.Termination, on_terminated)
        client.on(StreamingEvents.Error, on_error)
        return client

    def start(self) -> "SpeechStream":
        if self._started:
            return self
        self._started = True
        self._running.set()
        self._client = self._build_client()
        self._client.connect(
            StreamingParameters(
                sample_rate=self.sample_rate,
                format_turns=self.format_turns,
            )
        )

        def _runner():
            try:
                mic = aai.extras.MicrophoneStream(sample_rate=self.sample_rate)
                self._client.stream(mic)
            finally:
                try:
                    self._client.disconnect(terminate=True)
                except Exception:
                    pass
                self._running.clear()

        self._thread = threading.Thread(target=_runner, daemon=True)
        self._thread.start()
        return self

    def get_next(self, timeout: float | None = None) -> Optional[str]:
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def stop(self) -> None:
        self._running.clear()
        try:
            if self._client is not None:
                self._client.disconnect(terminate=True)
        except Exception:
            pass
        if self._thread is not None:
            self._thread.join(timeout=1.0)

    def latest(self) -> str:
        """Return the most recent transcript (partial or final), or empty string.

        Does not consume the internal queue; safe to call frequently.
        """
        return self._latest


def transcribe_once(timeout_s: float = 10.0, sample_rate: int = 16000) -> str:
    """Capture a single spoken utterance from the microphone and return text.

    - Waits until a 'final' turn is produced (end_of_turn True), then disconnects
      and returns that text.
    - If nothing is recognized before timeout_s, returns "" (empty string).
    - On SDK error, returns "" as well.
    """
    stream = SpeechStream(sample_rate=sample_rate).start()
    try:
        text = stream.get_next(timeout=timeout_s)
        return text or ""
    finally:
        stream.stop()
