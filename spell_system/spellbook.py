from __future__ import annotations

from .base_spell import BaseSpell
from .behaviors import BoundsBehavior, CollisionBehavior, LinearMovementBehavior, LifetimeBehavior
from .core import SpellDefinition, SpellStats
from .effects import BurnEffect, DamageEffect, KnockbackEffect, SlowEffect, FrozenEffect
from .visuals import SimpleOrbVisual, SpriteSpellVisual


def build_fire_bolt() -> SpellDefinition:
    stats = SpellStats(damage=22.0, speed=520.0, cost=25.0, radius=50.0, lifetime=1.5, cooldown=0.45)
    base = BaseSpell(
        name="Fire Bolt",
        stats=stats,
        effect_factory=lambda: [
            DamageEffect(stats.damage),
            BurnEffect(duration=2.5, dps=8.0),
            KnockbackEffect(force=180.0),
            FrozenEffect(duration=1.0)
        ],
        visual_factory=lambda: SpriteSpellVisual("output.jpg"),
    )
    return base.to_definition()


def build_frost_orb() -> SpellDefinition:
    stats = SpellStats(damage=12.0, speed=360.0, cost=18.0, radius=14.0, lifetime=2.4, cooldown=0.6, max_targets=2)
    return SpellDefinition(
        name="Frost Orb",
        stats=stats,
        behavior_factory=lambda: [
            LinearMovementBehavior(),
            LifetimeBehavior(),
            BoundsBehavior(margin=stats.radius),
            CollisionBehavior(),
        ],
        effect_factory=lambda: [
            DamageEffect(stats.damage),
            SlowEffect(duration=2.2, slow_fraction=0.45),
            KnockbackEffect(force=140.0),
        ],
        visual_factory=lambda: SimpleOrbVisual(color=(150, 220, 255), trail_color=(90, 190, 255)),
    )


def default_spellbook() -> list[SpellDefinition]:
    return [build_fire_bolt()]
