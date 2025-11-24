from __future__ import annotations

from typing import Dict

from .base_spell import BaseSpell
from .behaviors import BoundsBehavior, CollisionBehavior, LinearMovementBehavior, LifetimeBehavior
from .core import SpellDefinition, SpellStats
from .effects import BurnEffect, DamageEffect, KnockbackEffect, SlowEffect
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

def build_healing_wave() -> SpellDefinition:
    stats = SpellStats(damage=-30.0, speed=0.0, cost=20.0, radius=100.0, lifetime=0.0, cooldown=3.0)
    return SpellDefinition(
        name="Healing Wave",
        stats=stats,
        behavior_factory=lambda: [],
        effect_factory=lambda: [
            DamageEffect(stats.damage),  # Negative damage for healing
        ],
        visual_factory=lambda: SimpleOrbVisual(color=(100, 255, 100), trail_color=(50, 200, 50)),
    )


def default_spellbook() -> list[SpellDefinition]:
    return [build_fire_bolt(), build_frost_orb(), build_healing_wave()]


_VOICE_COMMAND_MAP: Dict[str, str] = {
    "fire": "Fire Bolt",
    "fireball": "Fire Bolt",
    "flame": "Fire Bolt",
    "freeze": "Frost Orb",
    "ice": "Frost Orb",
    "icebolt": "Frost Orb",
    "heal": "Healing Wave",
    "healing": "Healing Wave",
}


def voice_command_map() -> Dict[str, str]:
    """Return a copy of the keyword-to-spell mapping for voice control."""

    return dict(_VOICE_COMMAND_MAP)


def match_voice_command(transcript: str) -> str | None:
    """Return the spell name that matches ``transcript``, if any."""

    if not transcript:
        return None
    lowered = transcript.lower()
    for keyword, spell_name in _VOICE_COMMAND_MAP.items():
        if keyword in lowered:
            return spell_name
    return None