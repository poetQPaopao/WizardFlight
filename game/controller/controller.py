from game.controller.speech_api import transcribe_once
import pygame
"""Game controller module handling user input modes.
Input: keyboard or speech.
return: Command like "fire ball" or "Icebolt"
"""
CONTROL_MODE = "speech"

class controller:
    def __init__(self):
        self.mode = CONTROL_MODE

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
        text = transcribe_once(timeout_s=8)
        print(f"Recognized command: {text}")
        return text.strip().lower()

