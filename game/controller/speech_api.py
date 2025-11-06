"""
High-level microphone-to-text API for the game.

Usage:
    from game.controller.speech_api import transcribe_once
    text = transcribe_once(timeout_s=8)
    if text:
        # do something with text
        ...

Notes:
- Requires environment variable ASSEMBLYAI_API_KEY to be set, or the SDK will
  use any configured default key if present. On macOS, ensure mic permission
  for your terminal/editor (System Settings > Privacy & Security > Microphone).
- This captures one utterance: once a final turn is received, it disconnects
  and returns the text. If nothing is spoken before timeout, returns "".
"""
from __future__ import annotations

import os
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
    return os.getenv("ASSEMBLYAI_API_KEY")


def transcribe_once(timeout_s: float = 10.0, sample_rate: int = 16000) -> str:
    """Capture a single spoken utterance from the microphone and return text.

    - Waits until a 'final' turn is produced (end_of_turn True), then disconnects
      and returns that text.
    - If nothing is recognized before timeout_s, returns "" (empty string).
    - On SDK error, returns "" as well.
    """
    api_key = _get_api_key()

    final_event = threading.Event()
    latest_final_text: list[str] = [""]
    had_error: list[Optional[str]] = [None]

    def on_begin(self: Type[StreamingClient], event: BeginEvent):
        # no-op; could log event.id
        pass

    def on_turn(self: Type[StreamingClient], event: TurnEvent):
        # Only capture when we have text
        if event.transcript and event.end_of_turn:
            latest_final_text[0] = event.transcript
            # Ask the server to format turns (optional)
            if not event.turn_is_formatted:
                self.set_params(StreamingSessionParameters(format_turns=True))
            final_event.set()

    def on_terminated(self: Type[StreamingClient], event: TerminationEvent):
        # If we haven't set yet, ensure waiters can proceed
        final_event.set()

    def on_error(self: Type[StreamingClient], error: StreamingError):
        had_error[0] = str(error)
        final_event.set()

    client = StreamingClient(
        StreamingClientOptions(
            api_key=api_key,
            api_host="streaming.assemblyai.com",
        )
    )

    # Register handlers
    client.on(StreamingEvents.Begin, on_begin)
    client.on(StreamingEvents.Turn, on_turn)
    client.on(StreamingEvents.Termination, on_terminated)
    client.on(StreamingEvents.Error, on_error)

    # Connect and start streaming in a background thread so we can time out
    client.connect(
        StreamingParameters(
            sample_rate=sample_rate,
            format_turns=True,
        )
    )

    def _run_stream():
        try:
            mic = aai.extras.MicrophoneStream(sample_rate=sample_rate)
            client.stream(mic)
        finally:
            # Ensure we release server resources even if exiting early
            try:
                client.disconnect(terminate=True)
            except Exception:
                pass

    t = threading.Thread(target=_run_stream, daemon=True)
    t.start()

    # Wait until we receive a final turn or hit timeout
    done = final_event.wait(timeout=timeout_s)
    # Trigger disconnect if still connected (in case on_turn didn't fire)
    try:
        client.disconnect(terminate=True)
    except Exception:
        pass
    # Give the stream thread a moment to exit
    t.join(timeout=1.0)

    if not done:
        # Timed out with no final transcription
        return ""

    if had_error[0] is not None:
        # Error occurred; return empty string for simplicity
        return ""

    return latest_final_text[0] or ""
