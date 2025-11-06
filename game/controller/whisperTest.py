import os
import threading
import time
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
import logging
from typing import Type

# Prefer environment variable; falls back to the inline key if not set
# export ASSEMBLYAI_API_KEY=your_key
api_key = os.getenv("ASSEMBLYAI_API_KEY", "995e19ff8cc5433787f017cd20f226c3")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Heartbeat to reassure the user while waiting for speech
last_transcript_time: float = 0.0

def on_begin(self: Type[StreamingClient], event: BeginEvent):
	print(f"Session started: {event.id}")

def on_turn(self: Type[StreamingClient], event: TurnEvent):
	# Print only when we have text; label partial vs final
	if event.transcript:
		stage = "final" if event.end_of_turn else "partial"
		print(f"[{stage}] {event.transcript}")
		global last_transcript_time
		last_transcript_time = time.time()

	# Ensure server formats turns once a final is received
	if event.end_of_turn and not event.turn_is_formatted:
		params = StreamingSessionParameters(
			format_turns=True,
		)
		self.set_params(params)

def on_terminated(self: Type[StreamingClient], event: TerminationEvent):
	print(
		f"Session terminated: {event.audio_duration_seconds} seconds of audio processed"
	)

def on_error(self: Type[StreamingClient], error: StreamingError):
	print(f"Error occurred: {error}")

def main():
	print("Connecting to AssemblyAI streaming…")
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

	client.connect(
		StreamingParameters(
			sample_rate = 16000,
			format_turns = True
		)
	)

	# Start a small heartbeat thread that prints 'listening…' if no text yet
	def heartbeat():
		printed_hint = False
		while True:
			time.sleep(5)
			since = time.time() - last_transcript_time if last_transcript_time else 999
			if since >= 5 and not printed_hint:
				print("listening… (grant microphone access if prompted; speak to see partial text)")
				printed_hint = True
			# keep it lightweight; we don't spam output

	hb_thread = threading.Thread(target=heartbeat, daemon=True)
	hb_thread.start()

	try:
		client.stream(
			aai.extras.MicrophoneStream(sample_rate=16000)
		)
	finally:
		client.disconnect(terminate=True)

if __name__ == "__main__":
	main()
