from __future__ import annotations

from typing import Sequence

from .base_spell import BaseSpell
from .behaviors import *
from .core import SpellDefinition, SpellStats
from .effects import BurnEffect, DamageEffect, KnockbackEffect, SlowEffect
from .visuals import (
    LightningBoltVisual,
    PulsingRingVisual,
    ShardVisual,
    SimpleOrbVisual,
    SpriteSpellVisual,
)

from google import genai
import pygame


def build_fire_bolt() -> SpellDefinition:
    """Construct the default Fire Bolt spell definition."""

    stats = SpellStats(damage=20.0, speed=300.0, cost=25.0, radius=40.0, lifetime=5.0, cooldown=0.45)
    base = BaseSpell(
        name="Fire Bolt",
        stats=stats,
        behavior_factory=lambda: [
            LinearMovementBehavior(),
            LifetimeBehavior(),
            CollisionBehavior(),
        ],
        effect_factory=lambda: [
            DamageEffect(stats.damage),
            BurnEffect(duration=2, dps=5.0),
            KnockbackEffect(force=200.0),
        ],
        visual_factory=lambda: SimpleOrbVisual(color=(255, 100, 23), trail_color=(255, 185, 150)),
        voice_triggers=("fire", "fire bolt", "fireball", "flame"),
    )
    definition = base.to_definition()
    definition.icon = _create_spell_icon("Fire Bolt", (255, 100, 23))
    return definition


def build_frost_orb() -> SpellDefinition:
    """Return the Frost Orb definition featuring slow and knockback."""

    stats = SpellStats(damage=10.0, speed=500.0, cost=18.0, radius=14.0, lifetime=2.0, cooldown=0.6)
    return SpellDefinition(
        name="Frost Orb",
        stats=stats,
        behavior_factory=lambda: [
            HomingMovmentBehavior(),
            LifetimeBehavior(),
            CollisionBehavior(),
        ],
        effect_factory=lambda: [
            DamageEffect(stats.damage),
            SlowEffect(duration=2.2, slow_fraction=0.7),
        ],
        visual_factory=lambda: SimpleOrbVisual(color=(150, 220, 255), trail_color=(90, 190, 255)),
        voice_triggers=("frost", "frost orb", "freeze", "ice", "ice bolt"),
        icon=_create_spell_icon("Frost Orb", (150, 220, 255)),
    )


def build_storm_spear() -> SpellDefinition:
    """Fast, jittery lightning bolt that slows on hit."""

    stats = SpellStats(damage=18.0, speed=520.0, cost=22.0, radius=16.0, lifetime=2.2, cooldown=0.55)
    return SpellDefinition(
        name="Storm Spear",
        stats=stats,
        behavior_factory=lambda: [
            OscillatingMovementBehavior(amplitude=140.0, frequency=3.4),
            LifetimeBehavior(),
            CollisionBehavior(),
        ],
        effect_factory=lambda: [
            DamageEffect(stats.damage),
            SlowEffect(duration=1.1, slow_fraction=0.3),
            KnockbackEffect(force=120.0),
        ],
        visual_factory=lambda: LightningBoltVisual(color=(210, 235, 255), glow_color=(120, 170, 255)),
        voice_triggers=("lightning", "storm", "storm spear", "thunder", "zap"),
        icon=_create_spell_icon("Storm Spear", (255, 255, 100)),
    )


def build_arcane_nova() -> SpellDefinition:
    """Area pulse centered on the caster that swells and slows enemies."""

    stats = SpellStats(
        damage=14.0,
        speed=0.0,
        cost=28.0,
        radius=48.0,
        lifetime=1.4,
        cooldown=2.5,
        max_hits=12,
    )
    return SpellDefinition(
        name="Arcane Nova",
        stats=stats,
        behavior_factory=lambda: [
            AnchorToCasterBehavior(forward_offset=10.0),
            PulsingRadiusBehavior(min_scale=0.85, max_scale=2.1, pulse_speed=2.2),
            LifetimeBehavior(),
            CollisionBehavior(),
        ],
        effect_factory=lambda: [
            DamageEffect(stats.damage),
            SlowEffect(duration=1.3, slow_fraction=0.35),
        ],
        visual_factory=lambda: PulsingRingVisual(inner_color=(195, 175, 255), outer_color=(120, 95, 160)),
        voice_triggers=("arcane", "nova", "pulse", "burst"),
        icon=_create_spell_icon("Arcane Nova", (195, 175, 255)),
    )


def build_earth_boomerang() -> SpellDefinition:
    """Boomerangs back to the caster, knocking foes away on each pass."""

    stats = SpellStats(
        damage=16.0,
        speed=380.0,
        cost=17.0,
        radius=18.0,
        lifetime=2.4,
        cooldown=0.65,
        max_hits=3,
    )
    return SpellDefinition(
        name="Earth Boomerang",
        stats=stats,
        behavior_factory=lambda: [
            BoomerangBehavior(return_time=0.6, turn_rate=6.5),
            LifetimeBehavior(),
            CollisionBehavior(),
        ],
        effect_factory=lambda: [
            DamageEffect(stats.damage),
            KnockbackEffect(force=200.0),
        ],
        visual_factory=lambda: ShardVisual(
            color=(185, 155, 105),
            outline=(110, 85, 60),
            trail_color=(215, 185, 125),
            spin_speed=280.0,
        ),
        voice_triggers=("earth", "boomerang", "stone", "return"),
        icon=_create_spell_icon("Earth Boomerang", (185, 155, 105)),
    )


def build_healing_wave() -> SpellDefinition:
    """Create a non-moving healing pulse that favors self-targeting."""

    # Healing Wave:
    # - Does not move (speed=0)
    # - Lasts for 1.0 second (lifetime=1.0)
    # - Heals the caster (or anyone in range)
    stats = SpellStats(damage=-5.0, speed=0.0, cost=20.0, radius=100.0, lifetime=1.0, cooldown=3.0, max_hits=5)
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
        visual_factory=lambda: SimpleOrbVisual(
            color=(100, 255, 100, 125),
            outline_color=(40, 120, 40)
        ),
        voice_triggers=("heal", "healing", "healing wave"),
        icon=_create_spell_icon("Healing Wave", (100, 255, 100)),
    )


def build_custom_spell(
    name: str,
    image_path: str,
    *,
    voice_triggers: Sequence[str] | None = None,
) -> SpellDefinition:
    """Create a custom spell definition using a sprite image."""
    # Default stats for custom spells
    params = generate_parameters(name)
    stats = SpellStats(
        damage=params.get("damage", 25.0),
        speed=params.get("speed", 450.0),
        cost=params.get("cost", 20.0),
        radius=params.get("radius", 40.0),
        lifetime=params.get("lifetime", 2.0),
        cooldown=params.get("cooldown", 0.5),
    )
    
    base = BaseSpell(
        name=name,
        stats=stats,
        behavior_factory=lambda: [
            HomingMovmentBehavior(),
            LifetimeBehavior(),
            CollisionBehavior(),
        ],
        effect_factory=lambda: [
            DamageEffect(stats.damage),
            KnockbackEffect(force=150.0),
        ],
        visual_factory=lambda: SpriteSpellVisual(image_path),
        voice_triggers=voice_triggers or (name,),
    )
    definition = base.to_definition()
    definition.icon = _load_icon(image_path)
    return definition

def generate_parameters(description: str) -> dict[str, float]:
    """Generate spell parameters based on the description."""
    # Simple heuristic-based parameter generation
    description = description.lower()
    params = {
        "damage": 20.0,
        "speed": 400.0,
        "cost": 20.0,
        "radius": 40.0,
        "lifetime": 2.0,
        "cooldown": 0.5,
    }

    # client = genai.Client(api_key='AIzaSyCorUATvMRJ7VO0aFWJeRj8Jjyk8wqt_Fw')
    client  = genai.Client()

    content = (f"parameters for fire ball: stats = SpellStats(damage=12.0, speed=360.0, cost=18.0, radius=14.0, lifetime=2.4, cooldown=0.6, max_hits=2). Parameters for ice bolt: stats = SpellStats(damage=12.0, speed=360.0, cost=18.0, radius=14.0, lifetime=2.4, cooldown=0.6, max_hits=2). Generate spell parameters based on the previous format and the following description: {description}")
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=content,
    )

    print(response.text)

    try:
        params = parse_generated_parameters(response.text)
    except Exception:
        print("Failed to parse generated parameters, using defaults.")
    return params

def parse_generated_parameters(response_text: str) -> dict[str, float]:
    """Parse the generated parameters from the response text."""
    params = {}
    for line in response_text.splitlines():
        if '=' in line:
            key, value = line.split('=', 1)
            key = key.strip()
            try:
                value = float(value.strip())
                params[key] = value
            except ValueError:
                continue
    return params


def default_spellbook() -> list[SpellDefinition]:
    """Return the baseline suite of spells available to every caster."""
    return [
        build_fire_bolt(),
        build_frost_orb(),
        build_storm_spear(),
        build_earth_boomerang(),
        build_arcane_nova(),
        build_healing_wave(),
    ]


def _load_icon(path: str) -> pygame.Surface:
    try:
        surf = pygame.image.load(path).convert_alpha()
        return pygame.transform.smoothscale(surf, (32, 32))
    except Exception:
        s = pygame.Surface((32, 32), pygame.SRCALPHA)
        s.fill((100, 100, 100))
        return s


def _create_spell_icon(name: str, color: tuple) -> pygame.Surface:
    s = pygame.Surface((32, 32), pygame.SRCALPHA)
    
    if name == "Fire Bolt":
        # Draw fire
        pygame.draw.circle(s, color, (16, 16), 14)
        pygame.draw.circle(s, (255, 200, 50), (16, 16), 8)
    elif name == "Frost Orb":
        # Draw snowflake-ish
        pygame.draw.circle(s, color, (16, 16), 14)
        pygame.draw.line(s, (255, 255, 255), (8, 16), (24, 16), 2)
        pygame.draw.line(s, (255, 255, 255), (16, 8), (16, 24), 2)
    elif name == "Storm Spear":
        # Draw lightning
        points = [(16, 2), (10, 16), (16, 16), (14, 30), (22, 14), (16, 14)]
        pygame.draw.polygon(s, color, points)
        pygame.draw.polygon(s, (255, 255, 255), points, 1)
    elif name == "Arcane Nova":
        # Draw ring
        pygame.draw.circle(s, color, (16, 16), 14, 4)
        pygame.draw.circle(s, (255, 255, 255), (16, 16), 6)
    elif name == "Earth Boomerang":
        # Draw boomerang
        # A simple V shape or arc
        points = [(8, 24), (16, 8), (24, 24), (16, 18)]
        pygame.draw.polygon(s, color, points)
    elif name == "Healing Wave":
        # Draw cross
        pygame.draw.rect(s, color, (12, 4, 8, 24))
        pygame.draw.rect(s, color, (4, 12, 24, 8))
    else:
        # Default circle
        pygame.draw.circle(s, color, (16, 16), 14)
        
    return s
