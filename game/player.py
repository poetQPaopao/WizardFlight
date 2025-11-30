from __future__ import annotations

import math
from typing import Optional, Sequence, Tuple, Union

import pygame

from controller import ControlScheme
from spell_system.status_effects import StatusEffect

Color = Tuple[int, int, int]
Size = Tuple[int, int]
RectLike = Union[pygame.Rect, Tuple[int, int, int, int]]


class Player(pygame.sprite.Sprite):
    """
    Flying player entity that lightly floats and tilts for extra game feel.

    - Movement is omnidirectional (no gravity) and speed is normalized so
      diagonals are not faster.
    - Sine-wave bobbing and velocity-based tilting give the rectangle a
      hovercraft-like feel until a real sprite is plugged in.
    - Bounds can be provided to prevent flying off-screen.
    - Sprites can be swapped in later via :meth:`set_sprite`.
    """

    def __init__(
        self,
        *,
        name: str,
        position: Tuple[float, float],
        controls: ControlScheme,
        color: Color = (240, 240, 240),
        size: Size = (48, 32),
        speed: float = 320.0,
        bounds: Optional[RectLike] = None,
        sprite: Optional[pygame.Surface] = None,
        float_amplitude: float = 6.0,
        float_speed: float = 1.3,
        tilt_max: float = 12.0,
        tilt_response: float = 10.0,
        max_health: float = 120.0,
        max_mana: float = 100.0,
        mana_regen: float = 25.0,
        bar_color: Optional[Color] = None,
    ) -> None:
        super().__init__()
        self.name = name
        self.controls = controls
        self.speed = max(0.0, speed)
        self.bounds = self._rect_or_none(bounds)
        self.float_amplitude = max(0.0, float_amplitude)
        self.float_speed = max(0.0, float_speed)
        self.tilt_max = max(0.0, tilt_max)
        self.tilt_response = max(0.0, tilt_response)

        self._velocity = pygame.Vector2()
        self._knockback_velocity = pygame.Vector2()
        self._current_velocity = pygame.Vector2()
        self._position = pygame.Vector2(position)
        self._float_phase = 0.0
        self._tilt_angle = 0.0
        self._bob_offset = 0.0
        self._aim_direction = pygame.Vector2(1, 0)
        self._speed_multiplier = 1.0
        self._status_effects: list[StatusEffect] = []
        self.knockback_drag = 4.5
        self.alive = True

        self.max_health = max(0.0, max_health)
        self.health = self.max_health
        self.max_mana = max(0.0, max_mana)
        self.mana_regen = max(0.0, mana_regen)
        self.mana = self.max_mana
        self.bar_color = bar_color or color

        self._base_image = self._build_initial_sprite(sprite, size, color)
        self.image = self._base_image
        self.rect = self.image.get_rect(center=position)
        self._position = pygame.Vector2(self.rect.center)
        self._apply_visual_state(0.0)

    def _build_initial_sprite(
        self,
        sprite: Optional[pygame.Surface],
        size: Size,
        color: Color,
    ) -> pygame.Surface:
        """Return the placeholder surface until a real sprite is provided."""
        if sprite is not None:
            return self._convert_surface(sprite)
        surface = pygame.Surface(size, pygame.SRCALPHA)
        surface.fill(color)
        pygame.draw.rect(surface, (0, 0, 0), surface.get_rect(), 2)
        return surface

    @staticmethod
    def _convert_surface(surface: pygame.Surface) -> pygame.Surface:
        """Convert a surface if there is an active display, otherwise copy it."""
        if pygame.display.get_surface():
            return surface.convert_alpha()
        return surface.copy()

    def set_sprite(self, sprite: pygame.Surface, *, keep_size: bool = False) -> None:
        """
        Replace the placeholder rectangle with an arbitrary sprite surface.

        Args:
            sprite: Fully prepared pygame.Surface (use convert_alpha first if
                needed before passing in).
            keep_size: When true the new sprite is scaled to the old rect size.
        """
        new_sprite = self._convert_surface(sprite)
        if keep_size:
            new_sprite = pygame.transform.smoothscale(new_sprite, self.rect.size)
        self._base_image = new_sprite
        self._apply_visual_state(self._bob_offset)

    @staticmethod
    def _rect_or_none(bounds: Optional[RectLike]) -> Optional[pygame.Rect]:
        """Convert accepted rect inputs into a pygame.Rect when provided."""

        if bounds is None:
            return None
        return pygame.Rect(bounds)

    def set_bounds(self, bounds: Optional[RectLike]) -> None:
        """Update the playable area for the player."""
        self.bounds = self._rect_or_none(bounds)
        if self.bounds:
            self._apply_visual_state(self._bob_offset)

    def handle_input(self, pressed: Sequence[bool]) -> None:
        """Read the keyboard state and update velocity."""
        direction = pygame.Vector2(0, 0)
        if pressed[self.controls.up]:
            direction.y -= 1
        if pressed[self.controls.down]:
            direction.y += 1
        if pressed[self.controls.left]:
            direction.x -= 1
        if pressed[self.controls.right]:
            direction.x += 1

        if direction.length_squared() > 0:
            direction = direction.normalize()
            self._aim_direction = direction
        speed = self.speed * self._speed_multiplier
        self._velocity = direction * speed

    def update(self, dt: float, pressed: Optional[Sequence[bool]] = None) -> None:
        """Advance the player each frame, including bobbing and tilt."""
        if dt < 0:
            dt = 0.0

        if not self.alive:
            self._apply_visual_state(0.0)
            return

        self._update_status_effects(dt)
        self._regen_mana(dt)

        if pressed is not None:
            self.handle_input(pressed)
        self._clamp_velocity_to_speed()

        total_velocity = self._velocity + self._knockback_velocity
        self._current_velocity = total_velocity
        if total_velocity.length_squared() > 0:
            displacement = total_velocity * dt
            self._position += displacement
        self._apply_knockback_damping(dt)

        if self.float_speed > 0:
            self._float_phase = (self._float_phase + dt * self.float_speed * math.tau) % math.tau

        bob_offset = math.sin(self._float_phase) * self.float_amplitude if self.float_amplitude > 0 else 0.0
        self._update_tilt(dt)
        self._apply_visual_state(bob_offset)

    def _update_tilt(self, dt: float) -> None:
        """Ease the tilt angle toward the velocity-driven target."""
        if self.speed <= 0:
            target_angle = 0.0
        else:
            normalized = max(-1.0, min(1.0, self._current_velocity.x / max(1e-5, self.speed)))
            target_angle = -normalized * self.tilt_max

        if self.tilt_response <= 0 or dt <= 0:
            self._tilt_angle = target_angle
            return

        blend = 1.0 - math.exp(-self.tilt_response * dt)
        self._tilt_angle += (target_angle - self._tilt_angle) * blend

    def _apply_visual_state(self, bob_offset: float) -> None:
        """Update the rendered surface to include bobbing and tilting."""
        self._bob_offset = bob_offset

        if abs(self._tilt_angle) <= 0.1:
            image = self._base_image
        else:
            image = pygame.transform.rotozoom(self._base_image, self._tilt_angle, 1.0)

        desired_center = pygame.Vector2(self._position.x, self._position.y + bob_offset)
        rect = image.get_rect(center=desired_center)
        if self.bounds:
            original_center = pygame.Vector2(rect.center)
            rect.clamp_ip(self.bounds)
            if rect.center != original_center:
                self._position = pygame.Vector2(rect.centerx, rect.centery - bob_offset)

        self.image = image
        self.rect = rect

    def apply_damage(self, amount: float) -> None:
        """Reduce health by ``amount`` and trigger kill when depleted."""

        if amount <= 0 or not self.alive:
            return
        self.health = max(0.0, self.health - amount)
        if self.health <= 0 and self.alive:
            self.health = 0.0
            self.kill()

    def heal(self, amount: float) -> None:
        """Restore health without exceeding ``max_health``."""

        if amount <= 0 or not self.alive:
            return
        self.health = min(self.max_health, self.health + amount)

    def apply_knockback(self, impulse: pygame.Vector2) -> None:
        """Additive knockback impulse that decays via drag over time."""

        vector = pygame.Vector2(impulse)
        if vector.length_squared() <= 0:
            return
        self._knockback_velocity += vector * self.knockback_drag

    def apply_speed_multiplier(self, multiplier: float) -> None:
        """Clamp the active speed multiplier against the provided value."""

        self._speed_multiplier = min(self._speed_multiplier, max(0.0, multiplier))

    def add_status(self, effect: StatusEffect) -> None:
        """Queue a status effect so its ``tick`` method runs each update."""

        if not self.alive:
            return
        self._status_effects.append(effect)

    def mana_ratio(self) -> float:
        """Return the normalized mana value between 0 and 1."""

        if self.max_mana <= 0:
            return 0.0
        return max(0.0, min(1.0, self.mana / self.max_mana))

    def can_spend_mana(self, amount: float) -> bool:
        """Check whether the player currently holds enough mana."""

        if amount <= 0:
            return True
        return self.mana >= amount

    def spend_mana(self, amount: float) -> bool:
        """Attempt to deduct mana, returning ``True`` on success."""

        if not self.can_spend_mana(amount) or not self.alive:
            return False
        self.mana = max(0.0, self.mana - max(0.0, amount))
        return True

    def aim_direction(self) -> pygame.Vector2:
        """Return the normalized facing direction, defaulting forward."""

        direction = self._aim_direction.copy()
        if direction.length_squared() == 0:
            direction = pygame.Vector2(1, 0)
        else:
            direction = direction.normalize()
        return direction

    def spell_origin(self) -> pygame.Vector2:
        """Return the point in front of the player where spells spawn."""

        direction = self.aim_direction()
        offset = direction * (max(self.rect.width, self.rect.height) * 0.6)
        return pygame.Vector2(self._position.x, self._position.y + self._bob_offset) + offset

    def _regen_mana(self, dt: float) -> None:
        """Gradually restore mana over time when alive and below max."""

        if self.max_mana <= 0 or self.mana >= self.max_mana or dt <= 0 or not self.alive:
            return
        self.mana = min(self.max_mana, self.mana + self.mana_regen * dt)

    def _clamp_velocity_to_speed(self) -> None:
        """Ensure movement velocity never exceeds the configured speed."""

        if self._velocity.length_squared() == 0:
            return
        max_speed = self.speed * self._speed_multiplier
        if max_speed <= 0:
            self._velocity = pygame.Vector2()
            return
        current_speed = self._velocity.length()
        if current_speed > max_speed:
            self._velocity.scale_to_length(max_speed)

    def _update_status_effects(self, dt: float) -> None:
        """Tick active status effects and discard expired ones."""

        self._speed_multiplier = 1.0
        if not self._status_effects:
            return
        survivors: list[StatusEffect] = []
        for effect in self._status_effects:
            if effect.tick(self, dt):
                survivors.append(effect)
        self._status_effects = survivors

    def _apply_knockback_damping(self, dt: float) -> None:
        """Exponentially decay knockback velocity toward zero."""

        if self._knockback_velocity.length_squared() == 0 or dt <= 0:
            return
        decay = math.exp(-self.knockback_drag * dt)
        self._knockback_velocity *= decay
        if self._knockback_velocity.length_squared() < 1e-2:
            self._knockback_velocity = pygame.Vector2()

    @property
    def velocity(self) -> pygame.Vector2:
        """Read-only access to the current velocity."""
        return self._current_velocity.copy()

    def kill(self) -> None:
        """Mark the sprite as dead and clear motion state."""

        if not self.alive:
            return
        self.alive = False
        self._velocity = pygame.Vector2()
        self._knockback_velocity = pygame.Vector2()
        self._current_velocity = pygame.Vector2()
        self._status_effects.clear()
        self._float_phase = 0.0
        self._tilt_angle = 0.0
        self._apply_visual_state(0.0)

    @property
    def is_alive(self) -> bool:
        """Convenience flag mirroring ``alive`` for compatibility."""

        return self.alive
