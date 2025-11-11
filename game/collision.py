# -*- coding: utf-8 -*-
"""Generic collision movement and screen boundary clamping"""
from .constants import WIDTH, HEIGHT, TILE_SIZE


def move_entity(rect, dx, dy, walls, clamp_horizontal=True, clamp_vertical=True):
    """Axis-aligned movement with collision resolution and optional screen clamping.

    Optimization: walls are tile-aligned; we can early exit scans by localizing
    candidate walls. For now keep the simple loop but document potential future
    improvements (spatial hashing / uniform grid) in comments.
    """
    # X-axis movement
    rect.x += dx
    for wall in walls:
        if rect.colliderect(wall):
            if dx > 0:
                rect.right = wall.left
            elif dx < 0:
                rect.left = wall.right

    # Y-axis movement
    rect.y += dy
    for wall in walls:
        if rect.colliderect(wall):
            if dy > 0:
                rect.bottom = wall.top
            elif dy < 0:
                rect.top = wall.bottom
    
    # Screen boundary clamp
    if clamp_horizontal:
        if rect.left < 0:
            rect.left = 0
        if rect.right > WIDTH:
            rect.right = WIDTH
    if clamp_vertical:
        if rect.top < 0:
            rect.top = 0
        if rect.bottom > HEIGHT:
            rect.bottom = HEIGHT
