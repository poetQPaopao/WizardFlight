from __future__ import annotations

from typing import Optional, Sequence, TYPE_CHECKING

import pygame

from player import Player

if TYPE_CHECKING:  # pragma: no cover - runtime import not required
    from spell_system import SpellManager

BACKGROUND = (18, 18, 28)


def render_frame(
    screen: pygame.Surface,
    *,
    world_bounds: pygame.Rect,
    spell_manager: "SpellManager",
    players: Sequence[Player],
    font: pygame.font.Font,
    game_over: bool,
    winner_name: Optional[str],
) -> None:
    """Draw arena bounds, sprites, spells, HUD, and overlays."""

    screen.fill(BACKGROUND)
    pygame.draw.rect(screen, (40, 40, 70), world_bounds, width=2, border_radius=8)
    spell_manager.draw(screen)
    for player in players:
        screen.blit(player.image, player.rect)
    draw_health(screen, players, font)
    if game_over:
        render_game_over_overlay(screen, font, winner_name)
    pygame.display.flip()


def draw_health(surface: pygame.Surface, players: Sequence[Player], font: pygame.font.Font) -> None:
    """Render health and mana bars for every player on the HUD surface."""

    bar_width = 220
    bar_height = 12
    spacing = 48
    base_y = 28
    left_x = 32
    right_x = surface.get_width() - bar_width - 32

    for idx, player in enumerate(players):
        column = idx % 2
        row = idx // 2
        x = left_x if column == 0 else right_x
        y = base_y + row * spacing

        health = max(0.0, player.health)
        max_health = max(player.max_health, 1.0)
        pct = max(0.0, min(1.0, health / max_health))
        pygame.draw.rect(surface, (35, 35, 55), (x, y, bar_width, bar_height), border_radius=6)
        pygame.draw.rect(surface, player.bar_color, (x, y, int(bar_width * pct), bar_height), border_radius=6)
        label = font.render(f"{player.name}: {health:05.1f} hp", True, (220, 220, 235))
        label_pos = (x, y - 20) if column == 0 else (x + bar_width - label.get_width(), y - 20)
        surface.blit(label, label_pos)

        mana_pct = player.mana_ratio()
        mana_y = y + bar_height + 6
        pygame.draw.rect(surface, (30, 30, 45), (x, mana_y, bar_width, bar_height), border_radius=6)
        pygame.draw.rect(surface, (90, 150, 255), (x, mana_y, int(bar_width * mana_pct), bar_height), border_radius=6)
        mana_label = font.render(f"{player.mana:05.1f} mp", True, (150, 190, 255))
        mana_pos = (x, mana_y + bar_height + 2) if column == 0 else (x + bar_width - mana_label.get_width(), mana_y + bar_height + 2)
        surface.blit(mana_label, mana_pos)


def render_game_over_overlay(surface: pygame.Surface, font: pygame.font.Font, winner_name: Optional[str]) -> None:
    """Draw a translucent overlay announcing the round winner."""

    overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 150))
    surface.blit(overlay, (0, 0))

    lines = ["Game Over"]
    if winner_name:
        lines.append(f"{winner_name} wins!")
    else:
        lines.append("It's a draw!")
    lines.append("Press R to restart")

    center_x = surface.get_width() // 2
    center_y = surface.get_height() // 2
    for idx, text in enumerate(lines):
        label = font.render(text, True, (240, 240, 255))
        rect = label.get_rect(center=(center_x, center_y + idx * 28))
        surface.blit(label, rect)
