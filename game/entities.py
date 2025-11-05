# -*- coding: utf-8 -*-
"""Instances of entities: Player, Enemy, Bullet"""
import math
import random
import pygame
from .constants import (
    TILE_SIZE,
    PLAYER_SPEED,
    PLAYER_HP,
    ENEMY_HP,
    ENEMY_SPEED,
    ENEMY_DAMAGE,
    BULLET_SIZE,
    BULLET_SPEED,
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
            x = random.randint(200, 700)
        if y is None:
            y = random.randint(100, 500)
        self.rect = pygame.Rect(x, y, TILE_SIZE, TILE_SIZE)
        self.hp = ENEMY_HP
        self.speed = ENEMY_SPEED
        self.damage = ENEMY_DAMAGE

    def update(self, player_rect, walls):
        dx = player_rect.centerx - self.rect.centerx
        dy = player_rect.centery - self.rect.centery
        dist = math.hypot(dx, dy)
        if dist > 0:
            step_x = self.speed * dx / dist
            step_y = self.speed * dy / dist
            move_entity(self.rect, step_x, step_y, walls)

    def knockback_from(self, player_rect, walls):
        dx = player_rect.centerx - self.rect.centerx
        dy = player_rect.centery - self.rect.centery
        dist = math.hypot(dx, dy)
        if dist > 0:
            back_x = -self.speed * dx / dist
            back_y = -self.speed * dy / dist
            move_entity(self.rect, back_x, back_y, walls)


class Bullet:
    def __init__(self, x, y, vx, vy):
        self.rect = pygame.Rect(x, y, BULLET_SIZE, BULLET_SIZE)
        self.vx = vx
        self.vy = vy

    def update(self):
        self.rect.x += self.vx * BULLET_SPEED
        self.rect.y += self.vy * BULLET_SPEED
