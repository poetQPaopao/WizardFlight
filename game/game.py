# -*- coding: utf-8 -*-
import sys
import math
import random
import pygame

from .constants import (
    WIDTH, HEIGHT, TILE_SIZE,
    BLACK, BLUE, GRAY, RED, YELLOW, WHITE,
    ENEMY_COUNT,
    FIRE_COOLDOWN_MS,
    SCROLL_SPEED,
)
from .level import build_walls, create_row
from .entities import Player, Enemy, Bullet, Fireball, Icebolt
from .controller import Controller


def draw_text(surface, text, size, x, y, color=WHITE):
    font = pygame.font.SysFont(None, size)
    surface.blit(font.render(text, True, color), (x, y))


def auto_target_enemy(enemies, player_rect):
    if not enemies:
        return None
    visible = [e for e in enemies if e.rect.bottom > 0]
    candidates = visible if visible else enemies
    return min(candidates, key=lambda e: (e.rect.centerx - player_rect.centerx) ** 2 + (e.rect.centery - player_rect.centery) ** 2)


class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Wizard Flight")
        self.clock = pygame.time.Clock()

        # Map & walls
        self.walls = build_walls()
        self.next_row_y = min((wall.y for wall in self.walls), default=0) - TILE_SIZE

        # Player & enemies
        self.player = Player(WIDTH // 2 - TILE_SIZE // 2, HEIGHT - TILE_SIZE * 2)
        self.enemies = []
        self._seed_enemies()

        # Bullets & cooldown
        self.bullets = []
        self.last_shot_time = 0

        # Scrolling state
        self.scroll_speed = SCROLL_SPEED
        self.scroll_accumulator = 0
        self.distance = 0

        self.game_over = False
        self.controller = Controller()

    def reset(self):
        from .constants import PLAYER_HP
        self.player.hp = PLAYER_HP
        self.player.rect.x = WIDTH // 2 - TILE_SIZE // 2
        self.player.rect.y = HEIGHT - TILE_SIZE * 2
        self.walls = build_walls()
        self.next_row_y = min((wall.y for wall in self.walls), default=0) - TILE_SIZE
        self.enemies.clear()
        self._seed_enemies()
        self.bullets.clear()
        self.scroll_accumulator = 0
        self.distance = 0
        self.last_shot_time = 0
        self.game_over = False

    def _shoot_toward(self, target, make_bullet_fn):
        """Create a projectile toward target if any."""
        if not target:
            return
        dx = target.rect.centerx - self.player.rect.centerx
        dy = target.rect.centery - self.player.rect.centery
        dist = math.hypot(dx, dy)
        if dist == 0:
            return
        vx, vy = dx / dist, dy / dist
        self.bullets.append(make_bullet_fn(self.player.rect.centerx, self.player.rect.centery, vx, vy))

    def _spawn_enemy(self, *, in_view=False):
        enemy = Enemy()
        if in_view:
            enemy.rect.y = random.randint(TILE_SIZE, HEIGHT // 2)
        return enemy

    def _seed_enemies(self):
        visible_count = max(1, ENEMY_COUNT // 2)
        for idx in range(ENEMY_COUNT):
            self.enemies.append(self._spawn_enemy(in_view=idx < visible_count))

    def ensure_enemy_count(self):
        while len(self.enemies) < ENEMY_COUNT:
            self.enemies.append(self._spawn_enemy())

    def spawn_wall_row(self):
        row = create_row(self.next_row_y)
        self.walls.extend(row)
        self.next_row_y -= TILE_SIZE

    def scroll_world(self):
        """Push the entire world downward to create the vertical scrolling effect."""
        self.distance += self.scroll_speed
        self.scroll_accumulator += self.scroll_speed

        for wall in self.walls:
            wall.y += self.scroll_speed
        for enemy in self.enemies:
            enemy.rect.y += self.scroll_speed
        for bullet in self.bullets:
            bullet.rect.y += self.scroll_speed

        # After shifting walls downward they may now overlap the player/enemies.
        # Because the scroll is conceptually the world moving down (as if the
        # player is flying upward), any new overlaps should push entities UP.
        self._resolve_scroll_collisions()

        self.walls = [wall for wall in self.walls if wall.y < HEIGHT]
        self.enemies = [enemy for enemy in self.enemies if enemy.rect.top < HEIGHT]
        self.bullets = [bullet for bullet in self.bullets if bullet.rect.bottom > 0]

        while self.scroll_accumulator >= TILE_SIZE:
            self.scroll_accumulator -= TILE_SIZE
            self.spawn_wall_row()

        self.ensure_enemy_count()

    def _resolve_scroll_collisions(self):
        """Resolve wall overlaps introduced by vertical scrolling.

        Scrolling moves static geometry (walls) downward without using the
        normal collision resolution path, so walls can end up overlapping the
        player or enemies. We separate them by pushing dynamic entities upward
        (opposite scroll direction) until no longer colliding for that wall.
        This preserves the expected solid-wall behavior so the player cannot
        be engulfed by a descending wall row.
        """
        # Player first
        for wall in self.walls:
            if self.player.rect.colliderect(wall):
                # Wall came from above (moved down). Place player just above it.
                if self.player.rect.centery <= wall.centery:
                    self.player.rect.bottom = wall.top
                else:
                    # If somehow wall is below (rare), put player on bottom side.
                    self.player.rect.top = wall.bottom
        # Enemies
        for enemy in self.enemies:
            for wall in self.walls:
                if enemy.rect.colliderect(wall):
                    if enemy.rect.centery <= wall.centery:
                        enemy.rect.bottom = wall.top
                    else:
                        enemy.rect.top = wall.bottom

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
                    # Immediate impact damage
                    e.hp -= getattr(b, "damage", 20)
                    # Apply projectile-specific status effects
                    if isinstance(b, Fireball):
                        e.ignite()
                    elif isinstance(b, Icebolt):
                        e.slow()
                    if e.hp <= 0:
                        self.enemies.remove(e)
                    break

    def update_enemies(self):
        # Enemies chase player + collisions + damage
        for e in self.enemies[:]:
            e.update(self.player.rect, self.walls)
            if e.hp <= 0:
                self.enemies.remove(e)
                continue
            if e.rect.colliderect(self.player.rect):
                self.player.hp -= e.damage
                e.knockback_from(self.player.rect, self.walls)

        if self.player.hp <= 0:
            self.game_over = True

    def handle_input(self, command: str = ""):
        from .constants import HEAL_AMOUNT, HEAL_COOLDOWN_MS, PLAYER_HP
        keys = pygame.key.get_pressed()
        self.player.move(keys, self.walls)

        # Auto-aim only (no auto-fire)
        target = auto_target_enemy(self.enemies, self.player.rect)

        # Manual fire: j=normal bullet, k=fireball, l=icebolt
        def cd_ready():
            now = pygame.time.get_ticks()
            return (now - self.last_shot_time) >= FIRE_COOLDOWN_MS

        if keys[pygame.K_j] and cd_ready():
            self.last_shot_time = pygame.time.get_ticks()
            self._shoot_toward(target, lambda x, y, vx, vy: Bullet(x, y, vx, vy, damage=12))

        if keys[pygame.K_k] and cd_ready():
            self.last_shot_time = pygame.time.get_ticks()
            self._shoot_toward(target, lambda x, y, vx, vy: Fireball(x, y, vx, vy, damage=8))

        if keys[pygame.K_l] and cd_ready():
            self.last_shot_time = pygame.time.get_ticks()
            self._shoot_toward(target, lambda x, y, vx, vy: Icebolt(x, y, vx, vy, damage=6))

        if keys[pygame.K_h]:
            now = pygame.time.get_ticks()
            if not hasattr(self, 'last_heal_time'):
                self.last_heal_time = 0
            if (now - self.last_heal_time) >= HEAL_COOLDOWN_MS and self.player.hp > 0:
                self.player.hp = min(PLAYER_HP, self.player.hp + HEAL_AMOUNT)
                self.last_heal_time = now

        # Voice commands mapping (if any): fire -> Fireball, freeze -> Icebolt, heal -> heal
        if command:
            cmd = command.strip().lower()
            # Shoot spells respect the same cooldown
            if ("fire" in cmd) and cd_ready():
                self.last_shot_time = pygame.time.get_ticks()
                self._shoot_toward(target, lambda x, y, vx, vy: Fireball(x, y, vx, vy, damage=8))
            elif ("freeze" in cmd) and cd_ready():
                self.last_shot_time = pygame.time.get_ticks()
                self._shoot_toward(target, lambda x, y, vx, vy: Icebolt(x, y, vx, vy, damage=6))
            if "heal" in cmd:
                now = pygame.time.get_ticks()
                if not hasattr(self, 'last_heal_time'):
                    self.last_heal_time = 0
                if (now - self.last_heal_time) >= HEAL_COOLDOWN_MS and self.player.hp > 0:
                    self.player.hp = min(PLAYER_HP, self.player.hp + HEAL_AMOUNT)
                    self.last_heal_time = now

    def draw(self):
        self.screen.fill(BLACK)
        lane_color = (30, 30, 30)
        offset = int(self.scroll_accumulator)
        for y in range(-TILE_SIZE, HEIGHT + TILE_SIZE, TILE_SIZE):
            line_y = y + offset
            pygame.draw.line(self.screen, lane_color, (0, line_y), (WIDTH, line_y), 1)
        for wall in self.walls:
            pygame.draw.rect(self.screen, GRAY, wall)
        for e in self.enemies:
            pygame.draw.rect(self.screen, RED, e.rect)
            # Simple burn visual: a small yellow overlay if burning
            try:
                if e.is_burning():
                    inner = e.rect.inflate(-e.rect.width * 0.4, -e.rect.height * 0.4)
                    pygame.draw.rect(self.screen, YELLOW, inner)
            except AttributeError:
                pass
            # Slow visual: thin blue outline if slowed
            try:
                if e.is_slowed():
                    pygame.draw.rect(self.screen, BLUE, e.rect, width=2)
            except AttributeError:
                pass
        for b in self.bullets:
            pygame.draw.rect(self.screen, YELLOW, b.rect)
        pygame.draw.rect(self.screen, BLUE, self.player.rect)
        draw_text(self.screen, f"HP: {self.player.hp}", 30, 10, 10)
        draw_text(self.screen, f"Distance: {self.distance // TILE_SIZE}", 24, 10, 40)

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
            controller = self.controller
            if controller:
                command = controller.get_command()
                print(f"Command received: {command}")
            if self.game_over:
                if keys[pygame.K_r]:
                    self.reset()
            else:
                self.scroll_world()
                self.handle_input(command)
                self.update_bullets()
                self.update_enemies()

            self.draw()
            self.clock.tick(60)
