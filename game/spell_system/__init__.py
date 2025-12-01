from __future__ import annotations

from .base_spell import BaseSpell
from .behaviors import BoundsBehavior, CollisionBehavior, LinearMovementBehavior, LifetimeBehavior, SpellBehavior
from .casting import SpellCaster, SpellManager
from .core import Spell, SpellContext, SpellDefinition, SpellStats
from .effects import BurnEffect, DamageEffect, KnockbackEffect, SlowEffect, SpellEffect
from .spellbook import (
    build_custom_spell,
    build_fire_bolt,
    build_frost_orb,
    default_spellbook,
)
from .status_effects import StatusEffect, BurningStatus, SlowStatus, FrozenStatus
from .visuals import SimpleOrbVisual, SpellVisual

__all__ = [
    "Spell",
    "SpellStats",
    "SpellContext",
    "SpellDefinition",
    "BaseSpell",
    "SpellBehavior",
    "SpellVisual",
    "SpellEffect",
    "LinearMovementBehavior",
    "LifetimeBehavior",
    "BoundsBehavior",
    "CollisionBehavior",
    "SimpleOrbVisual",
    "DamageEffect",
    "BurnEffect",
    "SlowEffect",
    "KnockbackEffect",
    "StatusEffect",
    "BurningStatus",
    "SlowStatus",
    "FrozenStatus",
    "SpellCaster",
    "SpellManager",
    "build_custom_spell",
    "build_fire_bolt",
    "build_frost_orb",
    "default_spellbook",
]
