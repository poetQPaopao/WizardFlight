from __future__ import annotations

from typing import Sequence

from .base_spell import BaseSpell
from .behaviors import BoundsBehavior, CollisionBehavior, HomingMovmentBehavior, TargetMovementBehavior, LifetimeBehavior
from .core import SpellDefinition, SpellStats
from .effects import BurnEffect, DamageEffect, KnockbackEffect, SlowEffect
from .visuals import SimpleOrbVisual, SpriteSpellVisual


def build_fire_bolt() -> SpellDefinition:
    """Construct the default Fire Bolt spell definition."""

    stats = SpellStats(damage=22.0, speed=520.0, cost=25.0, radius=50.0, lifetime=1.5, cooldown=0.45)
    base = BaseSpell(
        name="Fire Bolt",
        stats=stats,
        behavior_factory=lambda: [
            TargetMovementBehavior(),
            LifetimeBehavior(),
            BoundsBehavior(margin=stats.radius),
            CollisionBehavior(),
        ],
        effect_factory=lambda: [
            DamageEffect(stats.damage),
            BurnEffect(duration=2.5, dps=8.0),
            KnockbackEffect(force=180.0),
        ],
        visual_factory=lambda: SimpleOrbVisual(color=(255, 100, 23), trail_color=(255, 185, 150)),
        voice_triggers=("fire", "fire bolt", "fireball", "flame"),
    )
    return base.to_definition()


def build_frost_orb() -> SpellDefinition:
    """Return the Frost Orb definition featuring slow and knockback."""

    stats = SpellStats(damage=12.0, speed=360.0, cost=18.0, radius=14.0, lifetime=2.4, cooldown=0.6, max_targets=2)
    return SpellDefinition(
        name="Frost Orb",
        stats=stats,
        behavior_factory=lambda: [
            HomingMovmentBehavior(),
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
        voice_triggers=("frost", "frost orb", "freeze", "ice", "ice bolt"),
    )

def build_healing_wave() -> SpellDefinition:
    """Create a non-moving healing pulse that favors self-targeting."""

    # Healing Wave:
    # - Does not move (speed=0)
    # - Lasts for 1.0 second (lifetime=1.0)
    # - Heals the caster (or anyone in range)
    stats = SpellStats(damage=-30.0, speed=0.0, cost=20.0, radius=100.0, lifetime=1.0, cooldown=3.0, max_targets=10)
    return SpellDefinition(
        name="Healing Wave",
        stats=stats,
        behavior_factory=lambda: [
            LifetimeBehavior(), # Expires after lifetime
            CollisionBehavior(friendly_fire=True), # Must hit self to heal
        ],
        effect_factory=lambda: [
            DamageEffect(stats.damage),  # Negative damage for healing
        ],
        visual_factory=lambda: SimpleOrbVisual(color=(100, 255, 100), trail_color=(50, 200, 50)),
        voice_triggers=("heal", "healing", "healing wave"),
    )


def build_custom_spell(
    name: str,
    image_path: str,
    *,
    voice_triggers: Sequence[str] | None = None,
) -> SpellDefinition:
    """Create a custom spell definition using a sprite image."""
    # Default stats for custom spells
    stats = SpellStats(damage=25.0, speed=450.0, cost=20.0, radius=40.0, lifetime=2.0, cooldown=0.5)
    
    base = BaseSpell(
        name=name,
        stats=stats,
        effect_factory=lambda: [
            DamageEffect(stats.damage),
            KnockbackEffect(force=150.0),
        ],
        visual_factory=lambda: SpriteSpellVisual(image_path),
        voice_triggers=voice_triggers or (name,),
    )
    return base.to_definition()


def default_spellbook() -> list[SpellDefinition]:
    """Return the baseline trio of spells available to every caster."""

    return [build_fire_bolt(), build_frost_orb(), build_healing_wave()]
