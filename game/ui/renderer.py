from __future__ import annotations

from typing import Optional, Sequence, TYPE_CHECKING

import pygame

from player import Player

if TYPE_CHECKING:  # pragma: no cover - runtime import not required
    from spell_system import SpellManager
    from background import ParallaxBackground

BACKGROUND = (18, 18, 28)
SPELL_CARD_BG = (24, 26, 40)
SPELL_CARD_BORDER = (70, 70, 95)
SPELL_CARD_ACTIVE = (255, 210, 125)
SPELL_CARD_TEXT = (225, 225, 235)
SPELL_CARD_SECONDARY = (160, 190, 255)
SPELL_READY = (120, 220, 170)
SPELL_COOLDOWN = (255, 140, 110)


def render_frame(
    screen: pygame.Surface,
    *,
    world_bounds: pygame.Rect,
    spell_manager: "SpellManager",
    players: Sequence[Player],
    font: pygame.font.Font,
    game_over: bool,
    winner_name: Optional[str],
    background: Optional["ParallaxBackground"] = None,
    title_font: Optional[pygame.font.Font] = None,
    countdown_timer: Optional[float] = None,
    show_fight_label: bool = False,
) -> None:
    """Draw arena bounds, sprites, spells, HUD, and overlays."""

    if background:
        background.draw(screen)
    else:
        screen.fill(BACKGROUND)
    pygame.draw.rect(screen, (40, 40, 70), world_bounds, width=2, border_radius=8)
    spell_manager.draw(screen)
    for player in players:
        screen.blit(player.image, player.rect)
    draw_health(screen, players, font)
    draw_spell_loadouts(screen, players, font)
    if game_over:
        render_game_over_overlay(screen, font, winner_name, title_font)
    pygame.display.flip()


def draw_health(surface: pygame.Surface, players: Sequence[Player], font: pygame.font.Font) -> None:
    """Render health and mana bars for every player on the HUD surface."""

    bar_width = 280
    bar_height = 20
    spacing = 70
    base_y = 35
    left_x = 40
    right_x = surface.get_width() - bar_width - 40

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
        pygame.draw.rect(surface, (120, 50, 200), (x, mana_y, int(bar_width * mana_pct), bar_height), border_radius=6)
        mana_label = font.render(f"{player.mana:05.1f} mp", True, (220, 220, 235))
        mana_pos = (x, mana_y + bar_height + 2) if column == 0 else (x + bar_width - mana_label.get_width(), mana_y + bar_height + 2)
        surface.blit(mana_label, mana_pos)


def draw_spell_loadouts(surface: pygame.Surface, players: Sequence[Player], font: pygame.font.Font) -> None:
    """Render the equipped spells for each player with cooldown feedback."""

    if not players:
        return

    margin = 26
    card_height = 46
    gap = 10
    half_width = surface.get_width() // 2
    panel_width = half_width - margin * 2
    panel_bottom = surface.get_height() - 24

    layouts = []
    for idx, player in enumerate(players):
        spell_defs = list(getattr(player, "spellbook", ()))
        if not spell_defs:
            continue

        column = idx % 2
        cards_per_row = min(3, len(spell_defs))
        available_width = panel_width - gap * (cards_per_row - 1)
        card_width = max(120, int(available_width / max(1, cards_per_row)))
        row_height = card_height + gap
        rows = (len(spell_defs) + cards_per_row - 1) // cards_per_row
        panel_height = rows * row_height - gap
        layouts.append(
            {
                "player": player,
                "spells": spell_defs,
                "column": column,
                "row_index": idx // 2,
                "cards_per_row": cards_per_row,
                "card_width": card_width,
                "row_height": row_height,
                "rows": rows,
                "panel_height": panel_height,
            }
        )

    if not layouts:
        return

    row_gap = 18
    row_count = 1 + max(layout["row_index"] for layout in layouts)
    row_heights = [
        max(layout["panel_height"] for layout in layouts if layout["row_index"] == row) for row in range(row_count)
    ]

    current_bottom = panel_bottom
    for row_idx in range(row_count):
        row_bottom = current_bottom
        for layout in (layout for layout in layouts if layout["row_index"] == row_idx):
            x_origin = margin if layout["column"] == 0 else half_width + margin
            y_origin = row_bottom - layout["panel_height"]
            player = layout["player"]
            active_name = player.current_spell_name() if hasattr(player, "current_spell_name") else None
            cooldown_lookup = getattr(player, "spell_cooldown", lambda name: 0.0)

            for spell_idx, definition in enumerate(layout["spells"]):
                row = spell_idx // layout["cards_per_row"]
                col = spell_idx % layout["cards_per_row"]
                x = x_origin + col * (layout["card_width"] + gap)
                y = y_origin + row * layout["row_height"]
                card_rect = pygame.Rect(int(x), int(y), int(layout["card_width"]), card_height)

                pygame.draw.rect(surface, SPELL_CARD_BG, card_rect, border_radius=8)
                border_color = SPELL_CARD_ACTIVE if definition.name == active_name else SPELL_CARD_BORDER
                pygame.draw.rect(surface, border_color, card_rect, width=2, border_radius=8)

                cooldown = float(cooldown_lookup(definition.name))
                stats = getattr(definition, "stats", None)
                max_cooldown = max(0.001, getattr(stats, "cooldown", 0.0))
                cooldown_ratio = max(0.0, min(1.0, cooldown / max_cooldown))

                if cooldown > 0:
                    overlay_width = max(1, int(card_rect.width * cooldown_ratio))
                    overlay = pygame.Surface((overlay_width, card_rect.height), pygame.SRCALPHA)
                    overlay.fill((SPELL_COOLDOWN[0], SPELL_COOLDOWN[1], SPELL_COOLDOWN[2], 70))
                    surface.blit(overlay, card_rect.topleft)

                name_label = font.render(definition.name, True, SPELL_CARD_TEXT)
                surface.blit(name_label, (card_rect.x + 10, card_rect.y + 4))

                cooldown_text = f"{cooldown:.1f}s" if cooldown > 0 else "Ready"
                cooldown_color = SPELL_COOLDOWN if cooldown > 0 else SPELL_READY
                cooldown_label = font.render(cooldown_text, True, cooldown_color)
                cooldown_pos = cooldown_label.get_rect()
                cooldown_pos.top = card_rect.y + 4
                cooldown_pos.right = card_rect.right - 10
                surface.blit(cooldown_label, cooldown_pos)

                cost_label = font.render(f"{definition.stats.cost:.0f} mp", True, SPELL_CARD_SECONDARY)
                cost_pos = cost_label.get_rect()
                cost_pos.left = card_rect.x + 10
                cost_pos.top = card_rect.y + 22
                surface.blit(cost_label, cost_pos)

                bar_rect = pygame.Rect(card_rect.x + 8, card_rect.bottom - 10, card_rect.width - 16, 6)
                pygame.draw.rect(surface, (38, 38, 55), bar_rect, border_radius=3)
                if cooldown > 0:
                    fill_width = max(1, int(bar_rect.width * cooldown_ratio))
                    cooldown_fill = pygame.Rect(bar_rect.x, bar_rect.y, fill_width, bar_rect.height)
                    pygame.draw.rect(surface, SPELL_COOLDOWN, cooldown_fill, border_radius=3)
                else:
                    ready_fill = pygame.Rect(bar_rect.x, bar_rect.y, bar_rect.width, bar_rect.height)
                    pygame.draw.rect(surface, SPELL_READY, ready_fill, border_radius=3)

        current_bottom = row_bottom - row_heights[row_idx] - row_gap


def render_game_over_overlay(
    surface: pygame.Surface,
    font: pygame.font.Font,
    winner_name: Optional[str],
    title_font: Optional[pygame.font.Font] = None,
) -> None:
    """Draw a translucent overlay announcing the round winner."""

    overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 150))
    surface.blit(overlay, (0, 0))

    center_x = surface.get_width() // 2
    center_y = surface.get_height() // 2
    
    # Use title font if available, otherwise fallback to regular font
    main_font = title_font or font

    # Draw "Game Over"
    game_over_label = main_font.render("Game Over", True, (255, 100, 100))
    game_over_rect = game_over_label.get_rect(center=(center_x, center_y - 60))
    surface.blit(game_over_label, game_over_rect)

    # Draw Winner
    if winner_name:
        winner_text = f"{winner_name} wins!"
        color = (100, 255, 100)
    else:
        winner_text = "It's a draw!"
        color = (255, 255, 100)
    
    winner_label = main_font.render(winner_text, True, color)
    winner_rect = winner_label.get_rect(center=(center_x, center_y + 10))
    surface.blit(winner_label, winner_rect)

    # Draw Restart Instruction (smaller font)
    restart_label = font.render("Press R to restart", True, (200, 200, 200))
    restart_rect = restart_label.get_rect(center=(center_x, center_y + 80))
    surface.blit(restart_label, restart_rect)


def render_countdown(surface: pygame.Surface, font: pygame.font.Font, timer: float) -> None:
    import math
    count = math.ceil(timer)
    if count < 1:
        count = 1
    
    # Create a larger font for the countdown if possible, or scale the surface
    # Since we can't easily create a new font here without init, we'll scale the rendered text
    text = str(count)
    label = font.render(text, True, (255, 220, 100))
    
    # Scale up by 2x for impact
    scaled_size = (label.get_width() * 2, label.get_height() * 2)
    label = pygame.transform.scale(label, scaled_size)
    
    # Add a shadow/outline
    shadow = font.render(text, True, (0, 0, 0))
    shadow = pygame.transform.scale(shadow, scaled_size)
    
    center_x = surface.get_width() // 2
    center_y = surface.get_height() // 2
    
    surface.blit(shadow, shadow.get_rect(center=(center_x + 4, center_y + 4)))
    surface.blit(label, label.get_rect(center=(center_x, center_y)))


def render_fight_label(surface: pygame.Surface, font: pygame.font.Font) -> None:
    text = "FIGHT!!"
    label = font.render(text, True, (255, 50, 50))
    
    # Scale up
    scaled_size = (label.get_width() * 1.5, label.get_height() * 1.5)
    label = pygame.transform.scale(label, scaled_size)
    
    shadow = font.render(text, True, (0, 0, 0))
    shadow = pygame.transform.scale(shadow, scaled_size)
    
    center_x = surface.get_width() // 2
    center_y = surface.get_height() // 2
    
    surface.blit(shadow, shadow.get_rect(center=(center_x + 4, center_y + 4)))
    surface.blit(label, label.get_rect(center=(center_x, center_y)))
