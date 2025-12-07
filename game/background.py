from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence, Tuple

import pygame

Size = Tuple[int, int]


@dataclass
class _Layer:
    image: pygame.Surface
    speed: float
    drift_amplitude: float
    drift_speed: float
    offset: float = 0.0
    phase: float = 0.0


class ParallaxBackground:
    """Layered background built from the four supplied assets."""

    def __init__(self, screen_size: Size, *, asset_names: Sequence[str] | None = None) -> None:
        self._screen_size = screen_size
        base_dir = Path(__file__).resolve().parent.parent / "assets" / "background"
        names = list(asset_names) if asset_names else ["1.png", "2.png", "4.png"]

        speeds = [0.0, 12.0, 18.0]
        drift_amplitudes = [0.0, 3.5, 4.5]
        drift_speeds = [0.0, 0.15, 0.18]

        self._layers: list[_Layer] = []
        self._layer_sources: list[pygame.Surface] = []
        for idx, name in enumerate(names):
            path = base_dir / name
            image = pygame.image.load(str(path)).convert_alpha()
            self._layer_sources.append(image)
            scaled = pygame.transform.smoothscale(image, screen_size)
            speed = speeds[idx] if idx < len(speeds) else speeds[-1]
            drift = drift_amplitudes[idx] if idx < len(drift_amplitudes) else drift_amplitudes[-1]
            drift_speed = drift_speeds[idx] if idx < len(drift_speeds) else drift_speeds[-1]
            self._layers.append(
                _Layer(
                    image=scaled,
                    speed=speed,
                    drift_amplitude=drift,
                    drift_speed=drift_speed,
                )
            )

    def update(self, dt: float) -> None:
        if dt <= 0:
            return
        for layer in self._layers:
            if layer.speed:
                layer.offset = (layer.offset + layer.speed * dt) % layer.image.get_width()
            if layer.drift_amplitude and layer.drift_speed:
                layer.phase = (layer.phase + dt * layer.drift_speed) % math.tau

    def resize(self, screen_size: Size) -> None:
        """Scale every layer to match the resized display surface."""

        if screen_size == self._screen_size:
            return
        self._screen_size = screen_size
        for source, layer in zip(self._layer_sources, self._layers):
            layer.image = pygame.transform.smoothscale(source, screen_size)

    def draw(self, surface: pygame.Surface) -> None:
        width, height = surface.get_size()
        for layer in self._layers:
            vertical = math.sin(layer.phase) * layer.drift_amplitude if layer.drift_amplitude else 0.0
            y_positions = [vertical]
            image_height = layer.image.get_height()
            if vertical > 0:
                y_positions.append(vertical - image_height)
            elif vertical < 0:
                y_positions.append(vertical + image_height)

            if layer.speed == 0:
                for y in y_positions:
                    surface.blit(layer.image, (0, int(round(y))))
                continue

            offset = layer.offset
            start_x = -offset
            image_width = layer.image.get_width()
            for y in y_positions:
                x = start_x
                while x < width:
                    surface.blit(layer.image, (int(round(x)), int(round(y))))
                    x += image_width
