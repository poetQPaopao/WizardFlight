from __future__ import annotations

from typing import TYPE_CHECKING


class StatusEffect:
    """Base class for temporary player modifiers such as burn or slow."""

    def __init__(self, duration: float) -> None:
        self.remaining = max(0.0, duration)

    def tick(self, player: "Player", dt: float) -> bool:
        """Apply the effect for this frame. Returns True while still active."""
        if dt <= 0 or self.remaining <= 0:
            self.remaining = 0.0
            return False
        self.remaining = max(0.0, self.remaining - dt)
        self.apply(player, dt)
        return self.remaining > 0

    def apply(self, player: "Player", dt: float) -> None:  # pragma: no cover - interface hook
        """Override in subclasses to implement per-frame behavior."""

        raise NotImplementedError


class BurningStatus(StatusEffect):
    """Damage over time that chips away at the target's health."""

    def __init__(self, duration: float, damage_per_second: float) -> None:
        super().__init__(duration)
        self.damage_per_second = max(0.0, damage_per_second)

    def apply(self, player: "Player", dt: float) -> None:
        """Deal damage over the supplied time slice."""

        player.apply_damage(self.damage_per_second * dt)


class FrozenStatus(StatusEffect):
    """Temporarily stops the player from moving."""

    def __init__(self, duration: float) -> None:
        super().__init__(duration)

    def apply(self, player: "Player", dt: float) -> None:  # pragma: no cover - dt unused
        """Freeze movement entirely for the remaining duration."""

        del dt
        player.apply_speed_multiplier(0.0)
        player.apply_status_tint((120, 210, 255), intensity=0.85)


class ElectrocutedStatus(StatusEffect):
    """Rapid pulses of immobilization that blink movement on and off."""

    def __init__(self, duration: float, pulse_interval: float = 0.3, stun_ratio: float = 0.65) -> None:
        """
        Args:
            duration: Total time the effect should persist.
            pulse_interval: Length of a full on/off cycle in seconds.
            stun_ratio: Fraction of each cycle spent fully immobilized.
        """
        super().__init__(duration)
        self.pulse_interval = max(0.05, pulse_interval)
        self.stun_ratio = max(0.0, min(1.0, stun_ratio))
        self._elapsed_in_cycle = 0.0

    def apply(self, player: "Player", dt: float) -> None:
        """Blink the player's movement: stunned for part of each pulse."""

        if dt < 0:
            dt = 0.0

        self._elapsed_in_cycle = (self._elapsed_in_cycle + dt) % self.pulse_interval
        stunned_window = self.pulse_interval * self.stun_ratio
        stunned = self.stun_ratio > 0 and self._elapsed_in_cycle <= stunned_window

        if stunned:
            player.apply_speed_multiplier(0.0)
            tint_intensity = 0.85
        else:
            tint_intensity = 0.4

        # Keep a faint tint even while movement is allowed to telegraph the debuff.
        player.apply_status_tint((250, 225, 90), intensity=tint_intensity)


if TYPE_CHECKING:  # pragma: no cover - typing only
    from player import Player
