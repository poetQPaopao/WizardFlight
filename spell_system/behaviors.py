from __future__ import annotations

import pygame

from .core import SpellContext


class SpellBehavior:
    """Core spell behavior hook executed each frame."""

    def update(self, context: SpellContext, dt: float) -> None:  # pragma: no cover
        raise NotImplementedError


class LinearMovementBehavior(SpellBehavior):
    def update(self, context: SpellContext, dt: float) -> None:
        context.spell.position += context.spell.velocity * dt
        context.spell.sync_geometry()


class LifetimeBehavior(SpellBehavior):
    def update(self, context: SpellContext, dt: float) -> None:
        if context.spell.age >= context.spell.stats.lifetime:
            context.spell.kill()


class BoundsBehavior(SpellBehavior):
    def __init__(self, margin: float = 0.0) -> None:
        self.margin = margin

    def update(self, context: SpellContext, dt: float) -> None:
        inflated = context.bounds.inflate(-self.margin * 2, -self.margin * 2)
        if not inflated.contains(context.spell.rect):
            context.spell.kill()


def _circle_rect_collision(center: pygame.Vector2, radius: float, rect: pygame.Rect) -> bool:
    closest_x = max(rect.left, min(center.x, rect.right))
    closest_y = max(rect.top, min(center.y, rect.bottom))
    dx = center.x - closest_x
    dy = center.y - closest_y
    return dx * dx + dy * dy <= radius * radius


class CollisionBehavior(SpellBehavior):
    def __init__(self, friendly_fire: bool = False) -> None:
        self.friendly_fire = friendly_fire

    def update(self, context: SpellContext, dt: float) -> None:
        spell = context.spell
        if not spell.alive:
            return
        for player in context.players:
            if not self.friendly_fire and player is spell.caster:
                continue
            if hasattr(player, "is_alive") and not player.is_alive:
                continue
            if _circle_rect_collision(pygame.Vector2(spell.rect.center), spell.radius, player.rect):
                spell.apply_hit(player)
                if not spell.alive:
                    return
