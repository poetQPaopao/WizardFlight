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


class SlowStatus(StatusEffect):
    """Temporarily reduces the player's movement speed."""

    def __init__(self, duration: float, slow_fraction: float) -> None:
        super().__init__(duration)
        # Clamp to [0, 0.95] so the player never completely freezes.
        self.slow_fraction = max(0.0, min(0.95, slow_fraction))

    def apply(self, player: "Player", dt: float) -> None:  # pragma: no cover - dt unused
        """Halve player speed by applying a multiplicative slow multiplier."""

        del dt
        multiplier = max(0.05, 1.0 - self.slow_fraction)
        player.apply_speed_multiplier(multiplier)


class FrozenStatus(StatusEffect):
    """Completely immobilizes the player for the duration."""

    def __init__(self, duration: float) -> None:
        super().__init__(duration)

    def apply(self, player: "Player", dt: float) -> None:  # pragma: no cover - dt unused
        """Stop all movement until the effect expires."""

        del dt
        player.apply_speed_multiplier(0.0)


if TYPE_CHECKING:  # pragma: no cover - typing only
    from player import Player
