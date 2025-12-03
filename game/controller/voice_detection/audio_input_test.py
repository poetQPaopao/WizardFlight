"""Manual microphone/AssemblyAI tester for the audio_input helpers.

Run this file to stream audio, view partial/final transcripts, and inspect
device/channel settings without launching the whole game:

    python -m controller.voice_detection.audio_input_test --list-devices
    python -m controller.voice_detection.audio_input_test --sample-rate 48000
    python -m controller.voice_detection.audio_input_test --live-words
"""

from __future__ import annotations

import argparse
import dataclasses
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
    from controller.voice_detection.audio_input import (
        AudioInputConfig,
        MicrophoneConfigurationCancelled,
        interactive_configure_microphones,
    )
except ImportError as exc:  # pragma: no cover - convenience for manual runs
    sys.exit(
        "Failed to import audio_input. Run from the project root or install dependencies "
        f"from requirements.txt. Details: {exc}"
    )

def _print_devices() -> None:
    devices = audio_input.AudioController.list_input_devices()
    if not devices:
        print("No input devices detected by sounddevice/PyAudio.")
        return
    print("Available input devices:")
    for idx, name in devices:
        print(f"  [{idx}] {name}")


def _start_controller_from_configs(configs: list[AudioInputConfig], args: argparse.Namespace):
    if args.sample_rate:
        configs = [dataclasses.replace(cfg, sample_rate=args.sample_rate) for cfg in configs]
    controller = audio_input.AudioController(configs)
    labels = ", ".join([cfg.label or f"source-{cfg.source_index}" for cfg in configs])
    print(f"[voice] starting controller for: {labels}")
    return controller


def _start_controller(args: argparse.Namespace):
    try:
        configs = interactive_configure_microphones(["Mic A", "Mic B"])
    except MicrophoneConfigurationCancelled:
        print("\n[voice] Microphone selection cancelled; exiting.")
        return None
    if not configs:
        print("\n[voice] No microphones selected; exiting.")
        return None

    controller = _start_controller_from_configs(configs, args)
    desc_label = ", ".join([cfg.label or f"source-{cfg.source_index}" for cfg in configs])
    device_desc = ", ".join(
        [
            f"device={cfg.device_index or 'default'}"
            + (f" channels={cfg.channel_mapping}" if cfg.channel_mapping else "")
            for cfg in configs
        ]
    )
    print(f"[voice:{desc_label}] starting stream(s): {device_desc or 'defaults'}")
    return controller


def _print_new_words(snapshot: audio_input.TranscriptEvent, cache: dict[int, tuple[int, list[str], str, list[str]]]) -> None:
    if not snapshot.text:
        return

    words = snapshot.text.split()
    norm_words = [w.strip(".,!?;:\"'`") for w in words]
    prev_seq, prev_words, prev_stage, prev_norm = cache.get(snapshot.source_index, (-1, [], "", []))

    if (
        snapshot.sequence < prev_seq
        or len(words) < len(prev_words)
        or (prev_stage == "final" and snapshot.stage == "partial")
    ):
        prev_words = []
        prev_norm = []

    common_prefix = 0
    while common_prefix < len(prev_norm) and common_prefix < len(norm_words):
        if prev_norm[common_prefix] != norm_words[common_prefix]:
            break
        common_prefix += 1

    new_words = words[common_prefix:]
    if new_words:
        print(f"[words {snapshot.source}] {' '.join(new_words)}")

    cache[snapshot.source_index] = (snapshot.sequence, words, snapshot.stage, norm_words)


def _run_listener(args: argparse.Namespace) -> int:
    try:
        controller = _start_controller(args)
        if controller is None:
            return 1
    except Exception as exc:
        print(f"Failed to start listener: {exc}")
        return 1

    last_final_seq: dict[int, int] = {}
    live_word_cache: dict[int, tuple[int, list[str], str, list[str]]] = {}
    print("Speak into the microphone. Final transcripts will appear below (Ctrl+C to stop).")
    try:
        while True:
            controller_errors = controller.errors()
            if controller_errors:
                for source_index, source_label, message in controller_errors:
                    print(f"[error:{source_label or source_index}] {message}")
                break

            events = controller.consume_final_events()
            for event in events:
                last_final_seq[event.source_index] = event.sequence
                print(f"[final #{event.sequence} {event.source}] {event.text}")

            snapshots = controller.snapshots()
            for snapshot in snapshots:
                if (
                    snapshot.stage == "final"
                    and snapshot.text
                    and last_final_seq.get(snapshot.source_index) != snapshot.sequence
                ):
                    last_final_seq[snapshot.source_index] = snapshot.sequence

                if args.live_words:
                    _print_new_words(snapshot, live_word_cache)

            if not controller.running:
                print("[voice] controller stopped unexpectedly.")
                break

            time.sleep(args.poll_interval)
    except KeyboardInterrupt:
        print("\nStopping listener…")
    finally:
        controller.stop()

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stream microphone audio and view AssemblyAI transcripts.")
    parser.add_argument("--list-devices", action="store_true", help="List available input devices and exit.")
    parser.add_argument("--sample-rate", type=int, default=48000, help="Sampling rate for the stream.")
    parser.add_argument("--poll-interval", type=float, default=0, help="Seconds between transcript polls.")
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="AssemblyAI API key (falls back to ASSEMBLYAI_API_KEY env var).",
    )
    parser.add_argument(
        "--live-words",
        action="store_true",
        help="Print individual words live as they are transcribed.",
    )

    args = parser.parse_args(argv)

    if args.list_devices:
        _print_devices()
        return 0

    return _run_listener(args)


if __name__ == "__main__":
    raise SystemExit(main())
