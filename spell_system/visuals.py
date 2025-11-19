from __future__ import annotations

from pathlib import Path

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
        self.image_path = Path(image_path)
        self.rotate_with_velocity = rotate_with_velocity
        self.scale_to_radius = scale_to_radius
        self.scale_multiplier = scale_multiplier
        self._base_image: pygame.Surface | None = None
        self._scaled_image: pygame.Surface | None = None

    def _load_image(self) -> pygame.Surface:
        if self._base_image is None:
            path = self.image_path
            if not path.is_absolute():
                path = Path(__file__).resolve().parent / path
            if not path.exists():
                raise FileNotFoundError(f"Sprite for spell visual not found: {path}")
            self._base_image = pygame.image.load(str(path)).convert_alpha()
        return self._base_image

    def _build_scaled_image(self, spell: Spell) -> pygame.Surface:
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
        self._scaled_image = self._build_scaled_image(spell)

    def draw(self, surface: pygame.Surface, spell: Spell) -> None:
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
