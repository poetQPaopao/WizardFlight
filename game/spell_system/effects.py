from __future__ import annotations

import pygame

from player import Player
from .status_effects import BurningStatus, SlowStatus, FrozenStatus

from .core import Spell


class SpellEffect:
    """Base class for on-hit effects."""

    def apply(self, spell: Spell, target: Player) -> None:  # pragma: no cover - interface hook
        """Override with the concrete on-hit behavior."""

        raise NotImplementedError


class DamageEffect(SpellEffect):
    def __init__(self, amount: float) -> None:
        """Store the signed damage amount (negative heals)."""

        # Allow negative amount for healing
        self.amount = amount

    def apply(self, spell: Spell, target: Player) -> None:
        """Deal or heal damage based on the configured amount."""

        if self.amount < 0:
            target.heal(-self.amount)
        else:
            target.apply_damage(self.amount)



class KnockbackEffect(SpellEffect):
    def __init__(self, force: float) -> None:
        """Store the knockback magnitude applied in spell direction."""

        self.force = max(0.0, force)

    def apply(self, spell: Spell, target: Player) -> None:
        """Push the player along the spell's travel direction."""

        if self.force <= 0:
            return
        direction = spell.velocity.normalize() if spell.velocity.length_squared() > 0 else pygame.Vector2(1, 0)
        target.apply_knockback(direction * self.force)


class BurnEffect(SpellEffect):
    def __init__(self, duration: float, dps: float) -> None:
        """Persist burn stats used when creating ``BurningStatus``."""

        self.duration = max(0.0, duration)
        self.dps = max(0.0, dps)

    def apply(self, spell: Spell, target: Player) -> None:
        """Attach a burning status effect if the parameters are valid."""

        if self.duration <= 0 or self.dps <= 0:
            return
        target.add_status(BurningStatus(self.duration, self.dps))


class SlowEffect(SpellEffect):
    def __init__(self, duration: float, slow_fraction: float) -> None:
        """Store the slow duration and fractional reduction."""

        self.duration = max(0.0, duration)
        self.slow_fraction = max(0.0, slow_fraction)

    def apply(self, spell: Spell, target: Player) -> None:
        """Apply a ``SlowStatus`` if configured with non-zero values."""

        if self.duration <= 0 or self.slow_fraction <= 0:
            return
        target.add_status(SlowStatus(self.duration, self.slow_fraction))

class FrozenEffect(SpellEffect):
    def __init__(self, duration: float) -> None:
        """Store the freeze duration."""

        self.duration = max(0.0, duration)

    def apply(self, spell: Spell, target: Player) -> None:
        """Stop target movement by applying ``FrozenStatus``."""

        if self.duration <= 0:
            return
        target.add_status(FrozenStatus(self.duration))