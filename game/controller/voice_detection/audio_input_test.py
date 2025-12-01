"""Manual microphone/AssemblyAI tester for the audio_input helpers.

Run this file to stream audio, view partial/final transcripts, and inspect
device/channel settings without launching the whole game:

    python -m controller.voice_detection.audio_input_test --list-devices
    python -m controller.voice_detection.audio_input_test --device-index 1 --sample-rate 48000
    python -m controller.voice_detection.audio_input_test --channel-mapping 1,2
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def _bootstrap_path() -> None:
    """Allow running the file directly (adds ``game`` folder to sys.path)."""

    base = Path(__file__).resolve().parents[2]
    if str(base) not in sys.path:
        sys.path.insert(0, str(base))


_bootstrap_path()

try:
    from controller.voice_detection import audio_input
except ImportError as exc:  # pragma: no cover - convenience for manual runs
    sys.exit(
        "Failed to import audio_input. Run from the project root or install dependencies "
        f"from requirements.txt. Details: {exc}"
    )


def _parse_channel_mapping(raw: str | None) -> list[int] | None:
    if not raw:
        return None
    try:
        return [int(part) for part in raw.split(",") if part.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid channel mapping '{raw}'") from exc


def _print_devices() -> None:
    devices = audio_input.MultiMicAudioController.list_input_devices()
    if not devices:
        print("No input devices detected by sounddevice/PyAudio.")
        return
    print("Available input devices:")
    for idx, name in devices:
        print(f"  [{idx}] {name}")


def _run_listener(args: argparse.Namespace) -> int:
    mapping = _parse_channel_mapping(args.channel_mapping)
    listener = audio_input.AudioListener(
        sample_rate=args.sample_rate,
        device_index=args.device_index,
        channel_mapping=mapping,
        source_name=args.source_name,
        api_key=args.api_key,
    )

    print(
        f"[voice:{listener.source}] starting stream (rate={listener.sample_rate}, "
        f"device={listener.device_index}, mapping={mapping or 'mono'})"
    )
    try:
        listener.start()
    except Exception as exc:
        print(f"Failed to start listener: {exc}")
        return 1

    last_partial = ""
    last_final_seq = -1
    print("Speak into the microphone. Partial and final transcripts will appear below (Ctrl+C to stop).")
    try:
        while True:
            if listener.error:
                print(f"[error:{listener.source}] {listener.error}")
                break

            event = listener.consume_final_event()
            if event:
                last_final_seq = event.sequence
                print(f"[final #{event.sequence} {event.source}] {event.text}")

            snapshot = listener.snapshot()
            if snapshot.stage == "partial" and snapshot.text and snapshot.text != last_partial:
                last_partial = snapshot.text
                print(f"[partial {snapshot.source}] {snapshot.text}")
            elif snapshot.stage == "final" and snapshot.text and snapshot.sequence != last_final_seq:
                last_final_seq = snapshot.sequence
                print(f"[final {snapshot.source}] {snapshot.text}")

            if not listener.running:
                print("[voice] listener stopped unexpectedly.")
                break

            time.sleep(args.poll_interval)
    except KeyboardInterrupt:
        print("\nStopping listener…")
    finally:
        listener.stop()

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stream microphone audio and view AssemblyAI transcripts.")
    parser.add_argument("--list-devices", action="store_true", help="List available input devices and exit.")
    parser.add_argument("--device-index", type=int, default=None, help="PyAudio/sounddevice input index.")
    parser.add_argument("--sample-rate", type=int, default=48000, help="Sampling rate for the stream.")
    parser.add_argument(
        "--channel-mapping",
        type=str,
        default=None,
        help="Comma-separated channel numbers to capture (e.g., '1' for left, '1,2' for stereo).",
    )
    parser.add_argument("--source-name", type=str, default="mic-test", help="Label used in printed output.")
    parser.add_argument("--poll-interval", type=float, default=0.1, help="Seconds between transcript polls.")
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="AssemblyAI API key (falls back to ASSEMBLYAI_API_KEY env var).",
    )

    args = parser.parse_args(argv)

    if args.list_devices:
        _print_devices()
        return 0

    return _run_listener(args)


if __name__ == "__main__":
    raise SystemExit(main())
