from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Sequence

import pygame

from player import Player

if TYPE_CHECKING:  # pragma: no cover - typing helpers
    from .behaviors import SpellBehavior
    from .effects import SpellEffect
    from .visuals import SpellVisual


@dataclass(slots=True)
class SpellStats:
    damage: float
    speed: float
    cost: float
    radius: float
    lifetime: float
    cooldown: float
    max_targets: int = 1


@dataclass(slots=True)
class SpellContext:
    spell: "Spell"
    players: Sequence[Player]
    bounds: pygame.Rect


class Spell:
    """Runtime spell instance composed of stats, behaviors, effects, and visuals."""

    def __init__(
        self,
        *,
        name: str,
        stats: SpellStats,
        caster: Player,
        position: pygame.Vector2,
        direction: pygame.Vector2,
        behaviors: list["SpellBehavior"],
        effects: list["SpellEffect"],
        visual: "SpellVisual",
    ) -> None:
        self.name = name
        self.stats = stats
        self.caster = caster
        self.position = pygame.Vector2(position)
        self.radius = max(2.0, stats.radius)
        direction = pygame.Vector2(direction)
        if direction.length_squared() == 0:
            direction = pygame.Vector2(1, 0)
        self.velocity = direction.normalize() * stats.speed
        self.behaviors = behaviors
        self.effects = effects
        self.visual = visual
        self.alive = True
        self.age = 0.0
        self.targets_hit = 0
        self._hit_targets: set[Player] = set()
        diameter = int(self.radius * 2)
        self.rect = pygame.Rect(0, 0, diameter, diameter)
        self.sync_geometry()
        if self.visual:
            self.visual.on_spawn(self)

    def sync_geometry(self) -> None:
        self.rect.center = (int(self.position.x), int(self.position.y))

    def kill(self) -> None:
        self.alive = False

    def update(self, dt: float, players: Sequence[Player], bounds: pygame.Rect) -> None:
        if not self.alive:
            return
        if dt < 0:
            dt = 0.0
        self.age += dt
        context = SpellContext(spell=self, players=players, bounds=bounds)
        for behavior in self.behaviors:
            behavior.update(context, dt)
            if not self.alive:
                break
        if self.visual and self.alive:
            self.visual.update(self, dt)

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visual:
            pygame.draw.circle(surface, (255, 255, 255), self.rect.center, int(self.radius))
        else:
            self.visual.draw(surface, self)

    def apply_hit(self, target: Player) -> None:
        if target in self._hit_targets or not self.alive:
            return
        for effect in self.effects:
            effect.apply(self, target)
        self._hit_targets.add(target)
        self.targets_hit += 1
        if self.targets_hit >= self.stats.max_targets:
            self.kill()


@dataclass(slots=True)
class SpellDefinition:
    name: str
    stats: SpellStats
    behavior_factory: Callable[[], list["SpellBehavior"]]
    effect_factory: Callable[[], list["SpellEffect"]]
    visual_factory: Callable[[], "SpellVisual"]

    def create_spell(self, caster: Player, position: pygame.Vector2, direction: pygame.Vector2) -> Spell:
        return Spell(
            name=self.name,
            stats=self.stats,
            caster=caster,
            position=position,
            direction=direction,
            behaviors=self.behavior_factory(),
            effects=self.effect_factory(),
            visual=self.visual_factory(),
        )
