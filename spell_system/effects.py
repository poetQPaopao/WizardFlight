from __future__ import annotations

import pygame

from player import Player
from status_effects import BurningStatus, SlowStatus

from .core import Spell


class SpellEffect:
    """Base class for on-hit effects."""

    def apply(self, spell: Spell, target: Player) -> None:  # pragma: no cover - interface hook
        raise NotImplementedError


class DamageEffect(SpellEffect):
    def __init__(self, amount: float) -> None:
        self.amount = max(0.0, amount)

    def apply(self, spell: Spell, target: Player) -> None:
        target.apply_damage(self.amount)


class KnockbackEffect(SpellEffect):
    def __init__(self, force: float) -> None:
        self.force = max(0.0, force)

    def apply(self, spell: Spell, target: Player) -> None:
        if self.force <= 0:
            return
        direction = spell.velocity.normalize() if spell.velocity.length_squared() > 0 else pygame.Vector2(1, 0)
        target.apply_knockback(direction * self.force)


class BurnEffect(SpellEffect):
    def __init__(self, duration: float, dps: float) -> None:
        self.duration = max(0.0, duration)
        self.dps = max(0.0, dps)

    def apply(self, spell: Spell, target: Player) -> None:
        if self.duration <= 0 or self.dps <= 0:
            return
        target.add_status(BurningStatus(self.duration, self.dps))


class SlowEffect(SpellEffect):
    def __init__(self, duration: float, slow_fraction: float) -> None:
        self.duration = max(0.0, duration)
        self.slow_fraction = max(0.0, slow_fraction)

    def apply(self, spell: Spell, target: Player) -> None:
        if self.duration <= 0 or self.slow_fraction <= 0:
            return
        target.add_status(SlowStatus(self.duration, self.slow_fraction))
