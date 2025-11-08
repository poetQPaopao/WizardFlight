# -*- coding: utf-8 -*-
"""Procedural wall generation for the endless vertical level."""
import random
import pygame

from .constants import (
    TILE_SIZE,
    WIDTH,
    HEIGHT,
    SCROLL_BUFFER_ROWS,
    WALL_DENSITY,
)


def create_row(y: int, density: float = WALL_DENSITY):
    """Create a horizontal row of walls positioned at world coordinate y."""
    walls = []
    columns = WIDTH // TILE_SIZE
    for col in range(columns):
        if random.random() < density:
            walls.append(pygame.Rect(col * TILE_SIZE, y, TILE_SIZE, TILE_SIZE))
    return walls


def build_walls(buffer_rows: int = SCROLL_BUFFER_ROWS):
    """Build the initial set of walls covering the screen plus an off-screen buffer."""
    walls = []
    y = -buffer_rows * TILE_SIZE
    while y < HEIGHT:
        walls.extend(create_row(y))
        y += TILE_SIZE
    return walls
