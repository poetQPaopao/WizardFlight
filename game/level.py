# -*- coding: utf-8 -*-
"""Level definition and wall generation"""
import pygame
from .constants import TILE_SIZE
import random

# Map layout for obstacles (1 means a wall)
object_Count = 0.15
LEVEL_MAP = [[1 if random.random() < object_Count else 0 for x in range(20)] for y in range(15)]

def build_walls(level_map=LEVEL_MAP):
    walls = []
    for y, row in enumerate(level_map):
        for x, tile in enumerate(row):
            if tile == 1:
                walls.append(pygame.Rect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE))
    return walls
