import math

import pygame

from objects import ObstacleManager, Player, StarField
from controller.pose_detection.pose_input import PoseController, PoseState
from controller.pose_detection.pose_input_test import draw_overlay

import cv2

CAMERA_WINDOW = "Pose Camera"
WIDTH, HEIGHT = 480, 720
FPS = 60


def keyboard_control(player: Player, dt: float) -> tuple[float | None, float]:
    keys = pygame.key.get_pressed()
    movement = 0.0
    if keys[pygame.K_LEFT] or keys[pygame.K_a]:
        movement -= player.speed * dt
    if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
        movement += player.speed * dt
    vertical = 0.0
    if keys[pygame.K_UP] or keys[pygame.K_w]:
        vertical -= 1.0
    if keys[pygame.K_DOWN] or keys[pygame.K_s]:
        vertical += 1.0
    movement = max(-player.speed, min(player.speed, movement))
    target = player.rect.centerx + movement if abs(movement) > 1e-3 else None
    return target, max(-1.0, min(1.0, vertical))


def slope_target(width: int, slope: float) -> float:
    normalized = math.tanh(slope)
    range_pixels = width * 0.45
    center = width / 2
    return max(0.0, min(width, center + range_pixels * normalized))


def state_to_vertical_input(state: PoseState) -> float:
    if state == PoseState.HANDS_UP:
        return -1.0
    if state == PoseState.HANDS_DOWN:
        return 1.0
    return 0.0


def show_camera_view(pose: PoseController, state: PoseState, pose_active: bool) -> None:
    control = pose.read()
    # Use last stable control when detection drops momentarily.
    control = control or pose.control
    state = pose.state or PoseState.NO_POSE
    slope = pose.turn_slope

    frame = pose.frame
    overlay = draw_overlay(
        frame,
        pose.landmarks,
        state,
        control.x,
        control.y,
        control.confidence,
        slope,
    )
    if overlay is not None:
        cv2.imshow(CAMERA_WINDOW, overlay)
        cv2.waitKey(1)


def main() -> None:
    pygame.init()
    pygame.display.set_caption("Wizard Flight")
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()
    font_small = pygame.font.SysFont("Menlo", 20)
    font_large = pygame.font.SysFont("Menlo", 48)

    bounds = pygame.Rect(0, 0, WIDTH, HEIGHT)
    player = Player(bounds)
    background = StarField(WIDTH, HEIGHT)
    obstacles = ObstacleManager(WIDTH, HEIGHT)
    pose = PoseController()

    score = 0.0
    running = True
    game_over = False

    try:
        while running:
            dt = clock.tick(FPS) / 1000
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    if game_over and event.key == pygame.K_SPACE:
                        game_over = False
                        score = 0.0
                        obstacles.reset()
                        player.reset()

            target_x = None
            vertical_input = 0.0
            control = pose.read()
            pose_state = pose.state
            pose_available = (
                control is not None
                and control.confidence > 0.25
                and pose_state in {PoseState.T_POSE, PoseState.HANDS_UP, PoseState.HANDS_DOWN}
            )
            show_camera_view(pose, pose_state, pose_available)
            if not game_over:
                if pose_available:
                    target_x = slope_target(WIDTH, pose.turn_slope)
                    vertical_input = state_to_vertical_input(pose_state)
                else:
                    target_x, vertical_input = keyboard_control(player, dt)
                player.update(target_x, dt, vertical_input)
                background.update(dt)
                obstacles.update(dt, score)
                score += dt * 25
                if obstacles.collides_with(player):
                    game_over = True

            screen.fill((8, 8, 18))
            background.draw(screen)
            obstacles.draw(screen)
            screen.blit(player.image, player.rect)

            score_text = font_small.render(f"Score: {int(score):05d}", True, (255, 255, 255))
            pose_label = pose_state.name.replace("_", " ").title()
            pose_text = font_small.render(
                f"Pose: {pose_label if pose_available else 'Calibrating'}",
                True,
                (120, 255, 180) if pose_available else (255, 120, 120),
            )
            screen.blit(score_text, (16, 12))
            screen.blit(pose_text, (16, 36))

            if not pose_available:
                hint = font_small.render(
                    "Use arrow/WASD while pose calibrates", True, (180, 180, 200)
                )
                screen.blit(hint, (16, HEIGHT - 40))

            if game_over:
                overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 160))
                screen.blit(overlay, (0, 0))
                text = font_large.render("Crashed!", True, (255, 255, 255))
                prompt = font_small.render("Press space to try again", True, (255, 255, 255))
                screen.blit(text, text.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 20)))
                screen.blit(prompt, prompt.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 24)))

            pygame.display.flip()
    finally:
        pose.shutdown()
        cv2.destroyWindow(CAMERA_WINDOW)
        pygame.quit()


if __name__ == "__main__":
    main()
