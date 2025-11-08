# -*- coding: utf-8 -*-
"""Instances of entities: Player, Enemy, Bullet"""
import math
import random
import pygame
from .constants import (
    WIDTH,
    TILE_SIZE,
    PLAYER_SPEED,
    PLAYER_HP,
    ENEMY_HP,
    ENEMY_SPEED,
    ENEMY_DAMAGE,
    ENEMY_SPAWN_MIN_Y,
    ENEMY_SPAWN_MAX_Y,
    BULLET_SIZE,
    BULLET_SPEED,
    BURN_DURATION_MS,
    BURN_DPS,
    SLOW_DURATION_MS,
    SLOW_FACTOR,
)
from .collision import move_entity


class Player:
    def __init__(self, x=100, y=100):
        self.rect = pygame.Rect(x, y, TILE_SIZE, TILE_SIZE)
        self.speed = PLAYER_SPEED
        self.hp = PLAYER_HP

    def move(self, keys, walls):
        dx = dy = 0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            dx -= self.speed
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            dx += self.speed
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            dy -= self.speed
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            dy += self.speed
        move_entity(self.rect, dx, dy, walls)


class Enemy:
    def __init__(self, x=None, y=None):
        if x is None:
            x = random.randint(TILE_SIZE, WIDTH - TILE_SIZE)
        if y is None:
            y = random.randint(ENEMY_SPAWN_MIN_Y, ENEMY_SPAWN_MAX_Y)
        self.rect = pygame.Rect(x, y, TILE_SIZE, TILE_SIZE)
        self.hp = float(ENEMY_HP)
        self.speed = ENEMY_SPEED
        self.damage = ENEMY_DAMAGE
        # Burn status
        self.burn_until_ms = 0
        self._burn_last_ms = 0
        self.burn_dps = 0.0
        # Slow status
        self.slow_until_ms = 0
        self.slow_factor = 1.0

    def update(self, player_rect, walls):
        dx = player_rect.centerx - self.rect.centerx
        dy = player_rect.centery - self.rect.centery
        dist = math.hypot(dx, dy)
        if dist > 0:
            spd = self.get_speed()
            step_x = spd * dx / dist
            step_y = spd * dy / dist
            move_entity(self.rect, step_x, step_y, walls, clamp_vertical=False)
        # Tick burn damage over time
        self._tick_burn()

    def knockback_from(self, player_rect, walls):
        dx = player_rect.centerx - self.rect.centerx
        dy = player_rect.centery - self.rect.centery
        dist = math.hypot(dx, dy)
        if dist > 0:
            back_x = -self.speed * dx / dist
            back_y = -self.speed * dy / dist
            move_entity(self.rect, back_x, back_y, walls, clamp_vertical=False)

    # --- Burn mechanics ---
    def ignite(self, duration_ms: int = BURN_DURATION_MS, dps: float = BURN_DPS):
        """Apply or refresh burn on this enemy."""
        now = pygame.time.get_ticks()
        self.burn_until_ms = max(self.burn_until_ms, now + duration_ms)
        # If multiple ignites occur, keep the higher DPS
        self.burn_dps = max(self.burn_dps, dps)
        if self._burn_last_ms == 0:
            self._burn_last_ms = now

    def is_burning(self) -> bool:
        return self.burn_until_ms > pygame.time.get_ticks()

    def _tick_burn(self):
        if self.burn_until_ms <= 0:
            return
        now = pygame.time.get_ticks()
        if self._burn_last_ms == 0:
            self._burn_last_ms = now
            return
        # Determine the window to apply damage for
        end_ms = min(now, self.burn_until_ms)
        elapsed = end_ms - self._burn_last_ms
        if elapsed > 0 and self.burn_dps > 0:
            self.hp -= self.burn_dps * (elapsed / 1000.0)
            self._burn_last_ms = end_ms
        # Clear burn if expired
        if now >= self.burn_until_ms:
            self.burn_until_ms = 0
            self._burn_last_ms = 0
            self.burn_dps = 0.0

    # --- Slow mechanics ---
    def slow(self, factor: float = SLOW_FACTOR, duration_ms: int = SLOW_DURATION_MS):
        """Apply or refresh a slow effect (speed multiplier reduced)."""
        now = pygame.time.get_ticks()
        self.slow_until_ms = max(self.slow_until_ms, now + duration_ms)
        # Keep the stronger slow (lower factor)
        self.slow_factor = min(self.slow_factor, factor)
        if self.slow_factor <= 0:
            self.slow_factor = 0.05

    def is_slowed(self) -> bool:
        return self.slow_until_ms > pygame.time.get_ticks()

    def get_speed(self) -> float:
        if self.is_slowed():
            return self.speed * self.slow_factor
        # Reset slow_factor when not slowed so future slows can apply correctly
        self.slow_factor = 1.0
        return self.speed


class Bullet:
    def __init__(self, x, y, vx, vy, damage=10):
        self.rect = pygame.Rect(x, y, BULLET_SIZE, BULLET_SIZE)
        self.vx = vx
        self.vy = vy
        self.damage = damage

    def update(self):
        self.rect.x += self.vx * BULLET_SPEED
        self.rect.y += self.vy * BULLET_SPEED

class Fireball(Bullet):
    def __init__(self, x, y, vx, vy, damage=10):
        super().__init__(x, y, vx, vy, damage)
        self.effect = "burn"

class Icebolt(Bullet):
    def __init__(self, x, y, vx, vy, damage=8):
        super().__init__(x, y, vx, vy, damage)
        self.effect = "slow"

