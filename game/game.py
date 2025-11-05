# -*- coding: utf-8 -*-
import sys
import math
import pygame

from .constants import (
    WIDTH, HEIGHT, TILE_SIZE,
    BLACK, BLUE, GRAY, RED, YELLOW, WHITE,
    ENEMY_COUNT,
    FIRE_COOLDOWN_MS,
)
from .level import build_walls
from .entities import Player, Enemy, Bullet
from .collision import move_entity


def draw_text(surface, text, size, x, y, color=WHITE):
    font = pygame.font.SysFont(None, size)
    surface.blit(font.render(text, True, color), (x, y))


def auto_target_enemy(enemies, player_rect):
    if not enemies:
        return None
    return min(enemies, key=lambda e: (e.rect.centerx - player_rect.centerx) ** 2 + (e.rect.centery - player_rect.centery) ** 2)


class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Block Shooter")
        self.clock = pygame.time.Clock()

        # Map & walls
        self.walls = build_walls()

        # Player & enemies
        self.player = Player(100, 100)
        self.enemies = [Enemy() for _ in range(ENEMY_COUNT)]

        # Bullets & cooldown
        self.bullets = []
        self.last_shot_time = 0

        self.game_over = False

    def reset(self):
        from .constants import PLAYER_HP
        self.player.hp = PLAYER_HP
        self.enemies = [Enemy() for _ in range(ENEMY_COUNT)]
        self.bullets.clear()
        self.game_over = False

    def shoot(self, target):
        now = pygame.time.get_ticks()
        if now - self.last_shot_time < FIRE_COOLDOWN_MS:
            return
        self.last_shot_time = now

        dx = target.rect.centerx - self.player.rect.centerx
        dy = target.rect.centery - self.player.rect.centery
        dist = math.hypot(dx, dy)
        if dist == 0:
            return
        vx, vy = dx / dist, dy / dist
        self.bullets.append(Bullet(self.player.rect.centerx, self.player.rect.centery, vx, vy))

    def update_bullets(self):
        from .constants import WIDTH, HEIGHT
        for b in self.bullets[:]:
            b.update()
            # Remove if out of bounds
            if b.rect.x < 0 or b.rect.x > WIDTH or b.rect.y < 0 or b.rect.y > HEIGHT:
                self.bullets.remove(b)
                continue
            # Remove if hits a wall
            hit_wall = False
            for wall in self.walls:
                if b.rect.colliderect(wall):
                    self.bullets.remove(b)
                    hit_wall = True
                    break
            if hit_wall:
                continue
            # Damage enemy on hit
            for e in self.enemies:
                if b.rect.colliderect(e.rect):
                    self.bullets.remove(b)
                    e.hp -= 20
                    if e.hp <= 0:
                        self.enemies.remove(e)
                    break

    def update_enemies(self):
        # Enemies chase player + collisions + damage
        for e in self.enemies:
            e.update(self.player.rect, self.walls)
            if e.rect.colliderect(self.player.rect):
                self.player.hp -= e.damage
                e.knockback_from(self.player.rect, self.walls)

        if self.player.hp <= 0:
            self.game_over = True

    def handle_input(self):
        keys = pygame.key.get_pressed()
        self.player.move(keys, self.walls)

        # Auto-shoot the nearest enemy
        target = auto_target_enemy(self.enemies, self.player.rect)
        if target:
            self.shoot(target)

    def draw(self):
        self.screen.fill(BLACK)
        for wall in self.walls:
            pygame.draw.rect(self.screen, GRAY, wall)
        for e in self.enemies:
            pygame.draw.rect(self.screen, RED, e.rect)
        for b in self.bullets:
            pygame.draw.rect(self.screen, YELLOW, b.rect)
        pygame.draw.rect(self.screen, BLUE, self.player.rect)
        draw_text(self.screen, f"HP: {self.player.hp}", 30, 10, 10)

        if self.game_over:
            draw_text(self.screen, "GAME OVER", 60, WIDTH // 2 - 150, HEIGHT // 2 - 30, RED)
            draw_text(self.screen, "Press R to restart", 30, WIDTH // 2 - 100, HEIGHT // 2 + 40, WHITE)

        pygame.display.flip()

    def run(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

            keys = pygame.key.get_pressed()
            if self.game_over:
                if keys[pygame.K_r]:
                    self.reset()
            else:
                self.handle_input()
                self.update_bullets()
                self.update_enemies()

            self.draw()
            self.clock.tick(60)
