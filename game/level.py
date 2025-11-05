# -*- coding: utf-8 -*-
"""Level definition and wall generation"""
import pygame
from .constants import TILE_SIZE

# Map layout for obstacles (1 means a wall)
LEVEL_MAP = [
    [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
    [0,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
    [0,1,0,0,0,0,0,0,0,0,0,1,1,1,0,0,0,0,0,0],
    [0,1,0,0,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0],
    [0,1,0,1,1,1,0,0,0,0,0,0,0,0,0,1,1,1,1,0],
    [0,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
    [0,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
]

def build_walls(level_map=LEVEL_MAP):
    walls = []
    for y, row in enumerate(level_map):
        for x, tile in enumerate(row):
            if tile == 1:
                walls.append(pygame.Rect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE))
    return walls
