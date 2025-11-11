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
        if self.mode == "speech":
            # Start a persistent stream once
            self._speech_stream = SpeechStream(sample_rate=16000).start()
        # Low-latency keyword trigger: arm once per utterance
        self._armed = {"fire": True, "freeze": True, "heal": True}
        # Partial tracking for inactivity-based rearm (no need to wait for final)
        self._last_partial: str = ""
        self._last_partial_time_ms: int = 0
        self._utterance_active: bool = False
        self._rearm_timeout_ms: int = 0  # silence/no-change window to re-arm

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
        now = pygame.time.get_ticks()
        # 1) If any final result arrived, re-arm all commands for the next utterance
        final_text = self._speech_stream.get_next(timeout=0.0)
        if final_text is not None:
            self._armed = {k: True for k in self._armed}
            self._utterance_active = False
            self._last_partial = ""
            self._last_partial_time_ms = now
            # We return nothing on final here; Game sees commands via partial gating below
            return ""

        # 2) Low-latency: react to partials as soon as a keyword appears, once per utterance
        latest = (self._speech_stream.latest() or "").strip().lower()
        if not latest:
            # If no partial and we've been inactive long enough, ensure re-armed
            if self._utterance_active and (now - self._last_partial_time_ms >= self._rearm_timeout_ms):
                self._armed = {k: True for k in self._armed}
                self._utterance_active = False
            return ""

        # Track partial changes to establish an inactivity window
        if latest != self._last_partial:
            self._last_partial = latest
            self._last_partial_time_ms = now
            self._utterance_active = True
        else:
            # No change for a while => treat as utterance boundary; re-arm
            if self._utterance_active and (now - self._last_partial_time_ms >= self._rearm_timeout_ms):
                self._armed = {k: True for k in self._armed}
                self._utterance_active = False

        if "fire" in latest and self._armed.get("fire", True):
            self._armed["fire"] = False
            return "fire"
        if "freeze" in latest and self._armed.get("freeze", True):
            self._armed["freeze"] = False
            return "freeze"
        if "heal" in latest and self._armed.get("heal", True):
            self._armed["heal"] = False
            return "heal"
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

