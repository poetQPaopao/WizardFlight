from __future__ import annotations

from .base_spell import BaseSpell
from .behaviors import (
    AnchorToCasterBehavior,
    BoomerangBehavior,
    BoundsBehavior,
    CollisionBehavior,
    LinearMovementBehavior,
    LifetimeBehavior,
    OscillatingMovementBehavior,
    PulsingRadiusBehavior,
    SpellBehavior,
    HomingMovmentBehavior
)
from .casting import SpellCaster, SpellManager
from .core import Spell, SpellContext, SpellDefinition, SpellStats
from .effects import BurnEffect, DamageEffect, KnockbackEffect, SlowEffect, SpellEffect
from .spellbook import (
    build_custom_spell,
    build_arcane_nova,
    build_earth_boomerang,
    build_fire_bolt,
    build_frost_orb,
    build_healing_wave,
    build_storm_spear,
    default_spellbook,
    generate_parameters,
)
from .status_effects import StatusEffect, BurningStatus, SlowStatus, FrozenStatus
from .visuals import (
    LightningBoltVisual,
    PulsingRingVisual,
    ShardVisual,
    SimpleOrbVisual,
    SpellVisual,
)

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
    "OscillatingMovementBehavior",
    "BoomerangBehavior",
    "PulsingRadiusBehavior",
    "AnchorToCasterBehavior",
    "HomingMovmentBehavior",
    "LifetimeBehavior",
    "BoundsBehavior",
    "CollisionBehavior",
    "SimpleOrbVisual",
    "LightningBoltVisual",
    "PulsingRingVisual",
    "ShardVisual",
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
    "build_arcane_nova",
    "build_earth_boomerang",
    "build_fire_bolt",
    "build_frost_orb",
    "build_healing_wave",
    "build_storm_spear",
    "default_spellbook",
    "generate_parameters",
]
