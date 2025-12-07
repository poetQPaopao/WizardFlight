from __future__ import annotations

import math

import pygame

from .core import SpellContext


class SpellBehavior:
    """Core spell behavior hook executed each frame."""

    def update(self, context: SpellContext, dt: float) -> None:  # pragma: no cover
        """Override to mutate spell state using the provided context."""

        raise NotImplementedError


class LinearMovementBehavior(SpellBehavior):
    """Advance the spell along its current velocity vector, aiming at the nearest opponent on spawn."""

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
        super().__init__()
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





class OscillatingMovementBehavior(LinearMovementBehavior):
    """Add a sinusoidal lateral wobble while moving forward."""

    def __init__(self, *, amplitude: float = 120.0, frequency: float = 2.5) -> None:
        super().__init__()
        self.amplitude = max(0.0, amplitude)
        self.frequency = max(0.0, frequency)
        self._phase = 0.0

    def update(self, context: SpellContext, dt: float) -> None:
        if dt > 0 and self.amplitude > 0 and self.frequency > 0:
            self._phase += dt * self.frequency * math.tau
            velocity = context.spell.velocity
            if velocity.length_squared() > 0:
                lateral = pygame.Vector2(-velocity.y, velocity.x)
                if lateral.length_squared() > 0:
                    lateral = lateral.normalize()
                    offset = math.sin(self._phase) * self.amplitude
                    context.spell.position += lateral * offset * dt
        super().update(context, dt)


class BoomerangBehavior(LinearMovementBehavior):
    """Send the spell out, then arc it back toward the caster."""

    def __init__(self, *, return_time: float = 0.6, turn_rate: float = 6.0) -> None:
        super().__init__()
        self.return_time = max(0.0, return_time)
        self.turn_rate = max(0.0, turn_rate)
        self._returning = False

    def update(self, context: SpellContext, dt: float) -> None:
        if not self._returning and context.spell.age >= self.return_time:
            self._returning = True
        if self._returning:
            caster_position = pygame.Vector2(context.spell.caster.rect.center)
            to_caster = caster_position - context.spell.position
            if to_caster.length_squared() > 0:
                desired_velocity = to_caster.normalize() * context.spell.stats.speed
                blend = 1.0 - math.exp(-self.turn_rate * max(0.0, dt))
                context.spell.velocity = context.spell.velocity.lerp(desired_velocity, blend)
        super().update(context, dt)


class PulsingRadiusBehavior(SpellBehavior):
    """Continuously scale the spell's radius for area effects."""

    def __init__(self, *, min_scale: float = 0.5, max_scale: float = 1.6, pulse_speed: float = 1.5) -> None:
        self.min_scale = min(min_scale, max_scale)
        self.max_scale = max(min_scale, max_scale)
        self.pulse_speed = max(0.0, pulse_speed)

    def update(self, context: SpellContext, dt: float) -> None:
        spell = context.spell
        if self.pulse_speed <= 0:
            return
        phase = spell.age * self.pulse_speed * math.tau
        scale = self.min_scale + (math.sin(phase) * 0.5 + 0.5) * (self.max_scale - self.min_scale)
        new_radius = max(2.0, spell.stats.radius * scale)
        if abs(new_radius - spell.radius) <= 0.01:
            return
        center = spell.rect.center
        spell.radius = new_radius
        diameter = int(new_radius * 2)
        spell.rect.size = (diameter, diameter)
        spell.rect.center = center


class AnchorToCasterBehavior(SpellBehavior):
    """Lock the spell to the caster (optionally offset in the aim direction)."""

    def __init__(self, *, forward_offset: float = 0.0) -> None:
        self.forward_offset = forward_offset

    def update(self, context: SpellContext, dt: float) -> None:
        caster = context.spell.caster
        position = pygame.Vector2(caster.rect.center)
        if self.forward_offset != 0 and hasattr(caster, "aim_direction"):
            direction = caster.aim_direction()
            position += direction * self.forward_offset
        context.spell.position = position
        context.spell.sync_geometry()


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
