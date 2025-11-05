# -*- coding: utf-8 -*-
"""Generic collision movement and screen boundary clamping"""
from .constants import WIDTH, HEIGHT


def move_entity(rect, dx, dy, walls):
    """Axis-aligned collision resolution: move X, then Y; finally clamp to screen bounds."""
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
    if rect.left < 0:
        rect.left = 0
    if rect.right > WIDTH:
        rect.right = WIDTH
    if rect.top < 0:
        rect.top = 0
    if rect.bottom > HEIGHT:
        rect.bottom = HEIGHT
