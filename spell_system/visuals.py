from __future__ import annotations

import pygame

from .core import Spell


class SpellVisual:
    """Responsible for rendering and one-off audio/particle hooks."""

    def on_spawn(self, spell: Spell) -> None:  # pragma: no cover - optional override
        del spell

    def update(self, spell: Spell, dt: float) -> None:  # pragma: no cover - optional override
        del spell, dt

    def draw(self, surface: pygame.Surface, spell: Spell) -> None:  # pragma: no cover
        raise NotImplementedError


class SimpleOrbVisual(SpellVisual):
    def __init__(self, color: tuple[int, int, int], trail_color: tuple[int, int, int] | None = None) -> None:
        self.color = color
        self.trail_color = trail_color or color
        self._trail: list[pygame.Vector2] = []
        self._trail_length = 12

    def on_spawn(self, spell: Spell) -> None:
        self._trail = [pygame.Vector2(spell.rect.center)]

    def update(self, spell: Spell, dt: float) -> None:
        self._trail.insert(0, pygame.Vector2(spell.rect.center))
        if len(self._trail) > self._trail_length:
            self._trail.pop()

    def draw(self, surface: pygame.Surface, spell: Spell) -> None:
        for idx, pos in enumerate(self._trail):
            if idx == 0:
                continue
            alpha = max(0.1, 1.0 - idx / self._trail_length)
            radius = max(1, int(spell.radius * alpha))
            color = (
                int(self.trail_color[0] * alpha),
                int(self.trail_color[1] * alpha),
                int(self.trail_color[2] * alpha),
            )
            pygame.draw.circle(surface, color, (int(pos.x), int(pos.y)), radius)
        pygame.draw.circle(surface, self.color, spell.rect.center, int(spell.radius))
