from __future__ import annotations

import pygame

from .core import SpellContext


class SpellBehavior:
    """Core spell behavior hook executed each frame."""

    def update(self, context: SpellContext, dt: float) -> None:  # pragma: no cover
        """Override to mutate spell state using the provided context."""

        raise NotImplementedError


class LinearMovementBehavior(SpellBehavior):
    """Advance the spell along its current velocity vector."""

    def update(self, context: SpellContext, dt: float) -> None:
        """Apply displacement and sync pygame geometry."""

        context.spell.position += context.spell.velocity * dt
        context.spell.sync_geometry()


def _nearest_opponent(spell, players):
    """Return the closest living opponent to ``spell``."""

    position = spell.position
    closest = None
    closest_distance_sq = float("inf")
    for player in players:
        if player is spell.caster:
            continue
        if hasattr(player, "is_alive") and not player.is_alive:
            continue
        delta = pygame.Vector2(player.rect.center) - position
        distance_sq = delta.length_squared()
        if distance_sq == 0:
            continue
        if distance_sq < closest_distance_sq:
            closest = player
            closest_distance_sq = distance_sq
    return closest


class HomingMovmentBehavior(LinearMovementBehavior):
    """Aim the spell at the nearest non-caster player before moving."""

    def __init__(self, *, retarget_each_frame: bool = True, homing_strength: float = 0.05) -> None:
        """Control steering persistence and how aggressively we turn toward targets."""

        self.retarget_each_frame = retarget_each_frame
        self.homing_strength = max(0.0, homing_strength)
        self._has_lock = False

    def update(self, context: SpellContext, dt: float) -> None:
        """Steer toward the closest opponent using the configured strength, then move."""

        if self.retarget_each_frame or not self._has_lock:
            target = _nearest_opponent(context.spell, context.players)
            if target is not None:
                offset = pygame.Vector2(target.rect.center) - context.spell.position
                if offset.length_squared() > 0:
                    desired_dir = offset.normalize()
                    current_velocity = context.spell.velocity
                    if current_velocity.length_squared() == 0 or self.homing_strength >= 1.0:
                        new_dir = desired_dir
                    else:
                        current_dir = current_velocity.normalize()
                        blend = min(1.0, self.homing_strength)
                        new_dir = current_dir.lerp(desired_dir, blend)
                    context.spell.velocity = new_dir.normalize() * context.spell.stats.speed
                    self._has_lock = True
        super().update(context, dt)


class TargetMovementBehavior(LinearMovementBehavior):
    """Aim once at the nearest opponent, then fly straight without further steering."""

    def __init__(self) -> None:
        self._aimed = False

    def update(self, context: SpellContext, dt: float) -> None:
        """Lock direction toward the closest opponent on first update, then move linearly."""

        if not self._aimed:
            target = _nearest_opponent(context.spell, context.players)
            if target is not None:
                offset = pygame.Vector2(target.rect.center) - context.spell.position
                if offset.length_squared() > 0:
                    context.spell.velocity = offset.normalize() * context.spell.stats.speed
            self._aimed = True
        super().update(context, dt)


class LifetimeBehavior(SpellBehavior):
    """Destroy the spell once it exceeds its lifetime."""

    def update(self, context: SpellContext, dt: float) -> None:
        """Kill the spell when age surpasses configured lifetime."""

        if context.spell.age >= context.spell.stats.lifetime:
            context.spell.kill()


class BoundsBehavior(SpellBehavior):
    def __init__(self, margin: float = 0.0) -> None:
        """Trim the playable bounds by ``margin`` before culling spells."""

        self.margin = margin

    def update(self, context: SpellContext, dt: float) -> None:
        """Cull spells when they leave the world bounds."""

        inflated = context.bounds.inflate(-self.margin * 2, -self.margin * 2)
        if not inflated.contains(context.spell.rect):
            context.spell.kill()


def _circle_rect_collision(center: pygame.Vector2, radius: float, rect: pygame.Rect) -> bool:
    """Return True when the circle centered at ``center`` overlaps ``rect``."""

    closest_x = max(rect.left, min(center.x, rect.right))
    closest_y = max(rect.top, min(center.y, rect.bottom))
    dx = center.x - closest_x
    dy = center.y - closest_y
    return dx * dx + dy * dy <= radius * radius


class CollisionBehavior(SpellBehavior):
    def __init__(self, friendly_fire: bool = False) -> None:
        """Configure whether spells can damage their caster."""

        self.friendly_fire = friendly_fire

    def update(self, context: SpellContext, dt: float) -> None:
        """Apply spell effects to players intersecting the spell volume."""

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
