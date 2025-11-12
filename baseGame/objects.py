import random
import pygame


class Player(pygame.sprite.Sprite):
    """Simple rectangle controlled by external input."""

    def __init__(self, bounds: pygame.Rect, size: tuple[int, int] = (48, 48), color: tuple[int, int, int] = (255, 220, 120)) -> None:
        super().__init__()
        self.bounds = bounds
        self.speed = 520
        self.image = pygame.Surface(size, pygame.SRCALPHA)
        pygame.draw.rect(self.image, color, self.image.get_rect(), border_radius=12)
        self.rect = self.image.get_rect()
        self.rect.midbottom = (bounds.width // 2, bounds.height - 30)

    def center(self) -> tuple[int, int]:
        return self.rect.center

    def reset(self) -> None:
        self.rect.midbottom = (self.bounds.width // 2, self.bounds.height - 30)

    def update(self, target_x: float | None, dt: float, vertical_input: float = 0.0) -> None:
        if target_x is not None:
            # Smooth follow instead of teleport to keep motion readable.
            delta = target_x - self.rect.centerx
            max_step = self.speed * dt
            if abs(delta) <= max_step:
                self.rect.centerx = int(target_x)
            else:
                self.rect.centerx += int(max_step if delta > 0 else -max_step)

        if abs(vertical_input) > 1e-3:
            vertical = max(-1.0, min(1.0, vertical_input))
            vertical_speed = self.speed * 0.65
            delta_y = vertical * vertical_speed * dt
            if 0 < abs(delta_y) < 1:
                delta_y = 1 if delta_y > 0 else -1
            self.rect.centery += int(round(delta_y))

        self.rect.clamp_ip(self.bounds)


class Obstacle(pygame.sprite.Sprite):
    def __init__(self, x: int, width: int, height: int, speed: float, color: tuple[int, int, int]) -> None:
        super().__init__()
        self.image = pygame.Surface((width, height), pygame.SRCALPHA)
        pygame.draw.rect(self.image, color, self.image.get_rect(), border_radius=10)
        self.rect = self.image.get_rect(midtop=(x, -height))
        self.speed = speed

    def update(self, dt: float) -> None:
        self.rect.y += int(self.speed * dt)


class ObstacleManager:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.obstacles = pygame.sprite.Group()
        self.spawn_delay = 0.9
        self.time_since_spawn = 0.0
        self.scroll_speed = 260
        self.difficulty = 0.0

    def reset(self) -> None:
        self.obstacles.empty()
        self.spawn_delay = 0.9
        self.time_since_spawn = 0.0
        self.difficulty = 0.0

    def update(self, dt: float, score: float) -> None:
        self.time_since_spawn += dt
        self.difficulty = min(1.0, score / 500.0)
        adaptive_delay = max(0.35, self.spawn_delay - self.difficulty * 0.45)
        while self.time_since_spawn >= adaptive_delay:
            self.time_since_spawn -= adaptive_delay
            self._spawn()

        for obstacle in list(self.obstacles):
            obstacle.update(dt)
            if obstacle.rect.top > self.height:
                self.obstacles.remove(obstacle)

    def _spawn(self) -> None:
        width = random.randint(60, 160)
        lane_margin = 20
        x = random.randint(lane_margin + width // 2, self.width - lane_margin - width // 2)
        height = random.randint(30, 120)
        color = random.choice([(255, 99, 71), (64, 199, 255), (255, 191, 0)])
        speed = self.scroll_speed + random.uniform(-20, 90)
        self.obstacles.add(Obstacle(x, width, height, speed, color))

    def draw(self, surface: pygame.Surface) -> None:
        self.obstacles.draw(surface)

    def collides_with(self, sprite: pygame.sprite.Sprite) -> bool:
        return pygame.sprite.spritecollideany(sprite, self.obstacles) is not None


class StarField:
    def __init__(self, width: int, height: int, count: int = 80) -> None:
        self.width = width
        self.height = height
        self.stars = [self._spawn_star(random.random() * height) for _ in range(count)]

    def _spawn_star(self, y: float = 0.0) -> list[float]:
        return [random.random() * self.width, y, random.uniform(40, 160), random.randint(1, 3)]

    def update(self, dt: float) -> None:
        for star in self.stars:
            star[1] += star[2] * dt
            if star[1] > self.height:
                new = self._spawn_star(0.0)
                star[0], star[1], star[2], star[3] = new

    def draw(self, surface: pygame.Surface) -> None:
        for x, y, _, radius in self.stars:
            pygame.draw.circle(surface, (240, 240, 255), (int(x), int(y)), radius)
