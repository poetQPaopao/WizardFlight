# -*- coding: utf-8 -*-
"""Constant definitions for the game"""

WIDTH, HEIGHT = 800, 600
TILE_SIZE = 40

# Scrolling parameters
SCROLL_SPEED = 2
SCROLL_BUFFER_ROWS = 6  # how many extra tile rows exist above the top of the screen
WALL_DENSITY = 0.1     # probability that a tile in a row becomes an obstacle

# Color definitions (R, G, B)
BLACK = (0, 0, 0)
BLUE = (0, 150, 255)
GRAY = (100, 100, 100)
RED = (200, 50, 50)
YELLOW = (255, 220, 0)
WHITE = (255, 255, 255)

# Player and enemy parameters
PLAYER_SPEED = 5
PLAYER_HP = 100

ENEMY_COUNT = 2
ENEMY_HP = 20
ENEMY_SPEED = 1
ENEMY_DAMAGE = 2
ENEMY_SPAWN_MIN_Y = -600
ENEMY_SPAWN_MAX_Y = -TILE_SIZE

# Bullet parameters
BULLET_SPEED = 8
BULLET_SIZE = 8
FIRE_COOLDOWN_MS = 500

# Fire (burn) effect
BURN_DURATION_MS = 3000  # how long enemies stay on fire (ms)
BURN_DPS = 5.0           # damage per second while burning

# Ice (slow) effect
SLOW_DURATION_MS = 3000  # how long enemies are slowed (ms)
SLOW_FACTOR = 0.4        # multiplier applied to enemy speed while slowed

# Healing
HEAL_AMOUNT = 25         # HP restored per cast
HEAL_COOLDOWN_MS = 2000  # cooldown between heals (ms)
