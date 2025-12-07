from __future__ import annotations

import math
import random
from pathlib import Path

import pygame

from .core import Spell

ColorValue = tuple[int, int, int] | tuple[int, int, int, int] | pygame.Color


class SpellVisual:
    """Responsible for rendering and one-off audio/particle hooks."""

    def on_spawn(self, spell: Spell) -> None:  # pragma: no cover - optional override
        """Called once when the spell is created."""

        del spell

    def update(self, spell: Spell, dt: float) -> None:  # pragma: no cover - optional override
        """Advance any visual-only state associated with the spell."""

        del spell, dt

    def draw(self, surface: pygame.Surface, spell: Spell) -> None:  # pragma: no cover
        raise NotImplementedError


class SimpleOrbVisual(SpellVisual):
    """Draws a glowing orb with a simple fading trail."""

    def __init__(
        self,
        color: ColorValue,
        trail_color: ColorValue | None = None,
        outline_color: ColorValue | None = None,
        trail_length: int = 15,
    ) -> None:
        """Configure orb color, optional distinct trail color, and outline.

        Colors accept RGB or RGBA tuples so you can render translucent orbs.
        """

        self.color = pygame.Color(color)
        base_trail_color: ColorValue = color if trail_color is None else trail_color
        self.trail_color = pygame.Color(base_trail_color)
        self.outline_color = pygame.Color(outline_color) if outline_color is not None else None
        self._trail: list[pygame.Vector2] = []
        self._trail_length = trail_length

    @staticmethod
    def _scaled_color(color: pygame.Color, scale: float) -> pygame.Color:
        """Return a tinted copy with rgb/alpha scaled by ``scale``."""

        scaled = pygame.Color(color)
        scaled.r = int(scaled.r * scale)
        scaled.g = int(scaled.g * scale)
        scaled.b = int(scaled.b * scale)
        scaled.a = int(scaled.a * scale)
        return scaled

    @staticmethod
    def _blit_circle(
        surface: pygame.Surface, color: pygame.Color, center: tuple[int, int], radius: int, *, width: int = 0
    ) -> None:
        """Draw with per-pixel alpha even on opaque destinations."""

        if radius <= 0:
            return
        diameter = radius * 2 + 2  # pad to avoid edge clipping
        circle_surface = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        circle_surface.fill((0, 0, 0, 0))
        pygame.draw.circle(circle_surface, color, (diameter // 2, diameter // 2), radius, width)
        surface.blit(circle_surface, (center[0] - diameter // 2, center[1] - diameter // 2))

    def on_spawn(self, spell: Spell) -> None:
        """Seed the trail with the initial spell position."""

        self._trail = [pygame.Vector2(spell.rect.center)]

    def update(self, spell: Spell, dt: float) -> None:
        """Record the latest spell position while capping trail length."""

        current_pos = pygame.Vector2(spell.rect.center)
        if not self._trail or current_pos.distance_to(self._trail[0]) > 0.5:
            self._trail.insert(0, current_pos)
            if len(self._trail) > self._trail_length:
                self._trail.pop()

    def draw(self, surface: pygame.Surface, spell: Spell) -> None:
        """Render the fading trail followed by the orb itself."""

        for idx, pos in enumerate(self._trail):
            if idx == 0:
                continue
            alpha = max(0.1, 1.0 - idx / self._trail_length)
            radius = max(1, int(spell.radius * alpha))
            color = self._scaled_color(self.trail_color, alpha)
            self._blit_circle(surface, color, (int(pos.x), int(pos.y)), radius)

        radius = max(1, int(spell.radius))
        self._blit_circle(surface, self.color, spell.rect.center, radius)
        if self.outline_color:
            outline_width = min(radius, max(2, int(radius * 0.12)))
            self._blit_circle(surface, self.outline_color, spell.rect.center, radius, width=outline_width)


class LightningBoltVisual(SpellVisual):
    """Jagged bolt that jitters along the spell's heading."""

    def __init__(
        self,
        color: tuple[int, int, int] = (220, 240, 255),
        glow_color: tuple[int, int, int] = (90, 150, 255),
        *,
        segments: int = 7,
        jitter: float = 14.0,
        length_scale: float = 2.2,
    ) -> None:
        self.color = color
        self.glow_color = glow_color
        self.segments = max(2, int(segments))
        self.jitter = max(0.0, jitter)
        self.length_scale = max(0.5, length_scale)
        self._seed = random.random()
        self._time = 0.0

    def on_spawn(self, spell: Spell) -> None:
        self._seed = random.random()
        self._time = 0.0

    def update(self, spell: Spell, dt: float) -> None:
        self._time += max(0.0, dt)

    def _build_points(self, spell: Spell) -> list[pygame.Vector2]:
        direction = spell.velocity.normalize() if spell.velocity.length_squared() > 0 else pygame.Vector2(1, 0)
        length = max(spell.radius * self.length_scale * 2.0, spell.radius * 3.0)
        start = pygame.Vector2(spell.rect.center) - direction * length * 0.15
        perpendicular = pygame.Vector2(-direction.y, direction.x)
        rng = random.Random(self._seed)
        points: list[pygame.Vector2] = []
        for idx in range(self.segments + 1):
            t = idx / self.segments
            base = start + direction * (length * t)
            jitter = (rng.random() * 2.0 - 1.0) * self.jitter
            wave = math.sin(self._time * 10.0 + idx) * self.jitter * 0.35
            points.append(base + perpendicular * (jitter + wave))
        return points

    def draw(self, surface: pygame.Surface, spell: Spell) -> None:
        points = self._build_points(spell)
        if len(points) < 2:
            return
        glow_width = max(3, int(spell.radius * 0.4))
        bolt_width = max(2, int(spell.radius * 0.2))
        pygame.draw.lines(surface, self.glow_color, False, [(int(p.x), int(p.y)) for p in points], glow_width)
        pygame.draw.lines(surface, self.color, False, [(int(p.x), int(p.y)) for p in points], bolt_width)
        pygame.draw.circle(surface, self.color, spell.rect.center, max(1, int(spell.radius * 0.35)))


class SpriteSpellVisual(SpellVisual):
    """Renders the spell with a custom sprite instead of a primitive shape."""

    def __init__(
        self,
        image_path: str | Path,
        *,
        rotate_with_velocity: bool = True,
        scale_to_radius: bool = True,
        scale_multiplier: float = 1.0,
    ) -> None:
        """Describe how the sprite should be loaded, scaled, and rotated."""

        self.image_path = Path(image_path)
        self.rotate_with_velocity = rotate_with_velocity
        self.scale_to_radius = scale_to_radius
        self.scale_multiplier = scale_multiplier
        self._base_image: pygame.Surface | None = None
        self._scaled_image: pygame.Surface | None = None

    def _load_image(self) -> pygame.Surface:
        """Load the sprite from disk once, falling back to a placeholder."""

        if self._base_image is None:
            path = self.image_path
            # If path is relative, try resolving it relative to CWD first (where assets/ usually is)
            if not path.is_absolute():
                # Try CWD first
                cwd_path = Path.cwd() / path
                if cwd_path.exists():
                    path = cwd_path
                else:
                    # Fallback to relative to this file (legacy behavior)
                    rel_path = Path(__file__).resolve().parent / path
                    if rel_path.exists():
                        path = rel_path
            
            if not path.exists():
                # Create a fallback surface if image is missing to prevent crash
                print(f"[Visuals] Warning: Sprite not found at {path}, using fallback.")
                fallback = pygame.Surface((32, 32), pygame.SRCALPHA)
                pygame.draw.circle(fallback, (255, 0, 255), (16, 16), 16)
                self._base_image = fallback
            else:
                try:
                    self._base_image = pygame.image.load(str(path)).convert_alpha()
                except pygame.error as e:
                    print(f"[Visuals] Error loading image {path}: {e}")
                    fallback = pygame.Surface((32, 32), pygame.SRCALPHA)
                    pygame.draw.circle(fallback, (255, 0, 0), (16, 16), 16)
                    self._base_image = fallback
                    
        return self._base_image

    def _build_scaled_image(self, spell: Spell) -> pygame.Surface:
        """Return a scaled version of the sprite respecting spell radius."""

        base = self._load_image()
        if not self.scale_to_radius and self.scale_multiplier == 1.0:
            return base
        diameter = max(1, int(spell.radius * 2))
        width, height = base.get_size()
        if width == 0 or height == 0:
            return base
        scale = self.scale_multiplier
        if self.scale_to_radius:
            longest = max(width, height)
            scale *= diameter / longest
        new_size = (
            max(1, int(width * scale)),
            max(1, int(height * scale)),
        )
        if new_size == base.get_size():
            return base
        return pygame.transform.smoothscale(base, new_size)

    def on_spawn(self, spell: Spell) -> None:
        """Prepare a scaled sprite copy for reuse during drawing."""

        self._scaled_image = self._build_scaled_image(spell)

    def draw(self, surface: pygame.Surface, spell: Spell) -> None:
        """Blit the sprite, optionally rotated to match travel direction."""

        if self._scaled_image is None:
            self.on_spawn(spell)
        image = self._scaled_image
        if image is None:
            return
        sprite = image
        if self.rotate_with_velocity and spell.velocity.length_squared() > 0:
            angle = -spell.velocity.angle_to(pygame.Vector2(1, 0))
            sprite = pygame.transform.rotate(image, angle)
        rect = sprite.get_rect(center=spell.rect.center)
        surface.blit(sprite, rect)


class PulsingRingVisual(SpellVisual):
    """Soft, pulsing ring suited for area-of-effect spells."""

    def __init__(
        self,
        inner_color: tuple[int, int, int] = (200, 170, 255),
        outer_color: tuple[int, int, int] = (90, 60, 140),
    ) -> None:
        self.inner_color = inner_color
        self.outer_color = outer_color
        self._phase = 0.0

    def update(self, spell: Spell, dt: float) -> None:
        self._phase += max(0.0, dt)

    def draw(self, surface: pygame.Surface, spell: Spell) -> None:
        radius = max(1, int(spell.radius))
        pulse = math.sin((self._phase + spell.age) * 3.5) * 0.5 + 0.5
        halo_radius = int(radius * (1.2 + pulse * 0.6))
        halo_width = max(2, int(radius * 0.14))
        pygame.draw.circle(surface, self.outer_color, spell.rect.center, halo_radius, halo_width)
        core_radius = max(1, int(radius * 0.65))
        pygame.draw.circle(surface, self.inner_color, spell.rect.center, core_radius)


class ShardVisual(SpellVisual):
    """Angular shard with a short trailing streak."""

    def __init__(
        self,
        color: tuple[int, int, int] = (210, 195, 140),
        outline: tuple[int, int, int] = (120, 100, 70),
        trail_color: tuple[int, int, int] | None = None,
        spin_speed: float = 240.0,
    ) -> None:
        self.color = color
        self.outline = outline
        self.trail_color = trail_color or outline
        self.spin_speed = spin_speed
        self._angle = 0.0
        self._trail: list[pygame.Vector2] = []
        self._trail_length = 9

    def on_spawn(self, spell: Spell) -> None:
        self._trail = [pygame.Vector2(spell.rect.center)]
        self._angle = 0.0

    def update(self, spell: Spell, dt: float) -> None:
        self._angle = (self._angle + self.spin_speed * max(0.0, dt)) % 360
        self._trail.insert(0, pygame.Vector2(spell.rect.center))
        if len(self._trail) > self._trail_length:
            self._trail.pop()

    def draw(self, surface: pygame.Surface, spell: Spell) -> None:
        if len(self._trail) > 1:
            for idx, pos in enumerate(self._trail[1:], start=1):
                fade = max(0.1, 1.0 - idx / self._trail_length)
                tint = (
                    int(self.trail_color[0] * fade),
                    int(self.trail_color[1] * fade),
                    int(self.trail_color[2] * fade),
                )
                pygame.draw.line(surface, tint, spell.rect.center, (int(pos.x), int(pos.y)), width=2)

        center = pygame.Vector2(spell.rect.center)
        r = spell.radius
        points = [
            pygame.Vector2(r * 1.2, 0),
            pygame.Vector2(0, r * 0.7),
            pygame.Vector2(-r * 1.2, 0),
            pygame.Vector2(0, -r * 0.7),
        ]
        angle = math.radians(self._angle)
        sin_a = math.sin(angle)
        cos_a = math.cos(angle)
        rotated = [
            pygame.Vector2(p.x * cos_a - p.y * sin_a, p.x * sin_a + p.y * cos_a) + center
            for p in points
        ]
        poly_points = [(int(p.x), int(p.y)) for p in rotated]
        pygame.draw.polygon(surface, self.color, poly_points)
        pygame.draw.polygon(surface, self.outline, poly_points, width=2)
