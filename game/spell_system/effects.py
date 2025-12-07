from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from .status_effects import BurningStatus, FrozenStatus, ElectrocutedStatus
from .core import Spell

if TYPE_CHECKING:  # pragma: no cover - typing only
    from player import Player


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


class FrozenEffect(SpellEffect):
    def __init__(self, duration: float) -> None:
        """Store how long the target should be frozen in place."""

        self.duration = max(0.0, duration)

    def apply(self, spell: Spell, target: Player) -> None:
        """Apply a movement-stopping ``FrozenStatus`` if duration is valid."""

        if self.duration <= 0:
            return
        target.add_status(FrozenStatus(self.duration))

class ElectrocutedEffect(SpellEffect):
    def __init__(self, duration: float, *, pulse_interval: float = 0.3, stun_ratio: float = 0.65) -> None:
        """Blinking immobilization that toggles movement on and off."""

        self.duration = max(0.0, duration)
        self.pulse_interval = max(0.05, pulse_interval)
        self.stun_ratio = max(0.0, min(1.0, stun_ratio))

    def apply(self, spell: Spell, target: Player) -> None:
        """Apply an ``ElectrocutedStatus`` with pulsed movement locks."""

        if self.duration <= 0:
            return
        target.add_status(ElectrocutedStatus(self.duration, self.pulse_interval, self.stun_ratio))
