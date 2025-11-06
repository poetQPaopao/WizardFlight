from game.controller.speech_api import transcribe_once, SpeechStream
import pygame
"""Game controller module handling user input modes.
Input: keyboard or speech.
return: Command like "fire ball" or "Icebolt"
"""
CONTROL_MODE = "speech"

class controller:
    def __init__(self):
        self.mode = CONTROL_MODE
        self._speech_stream: SpeechStream | None = None
        self._last_text: str = ""
        if self.mode == "speech":
            # Start a persistent stream once
            self._speech_stream = SpeechStream(sample_rate=16000).start()

    def get_command(self) -> str:
        if self.mode == "keyboard":
            return self._get_keyboard_command()
        elif self.mode == "speech":
            return self._get_speech_command()
        else:
            raise ValueError(f"Unknown control mode: {self.mode}")

    def _get_keyboard_command(self) -> str:
        return pygame.key.name(pygame.key.get_pressed().index(1))
    
    def _get_speech_command(self) -> str:
        if not self._speech_stream:
            # Fallback: single-utterance mode if stream isn't available
            text = transcribe_once(timeout_s=8)
            return text.strip().lower()
        # Return new text when it changes (partials update frequently)
        current = self._speech_stream.latest()
        if current and current != self._last_text:
            self._last_text = current
            return current.strip().lower()
        return ""

    def stop(self):
        if self._speech_stream:
            self._speech_stream.stop()
            self._speech_stream = None

    def __del__(self):
        try:
            self.stop()
        except Exception:
            pass

