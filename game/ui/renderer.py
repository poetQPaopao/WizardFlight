from __future__ import annotations

from typing import Optional, Sequence, TYPE_CHECKING

import pygame

from player import Player

if TYPE_CHECKING:  # pragma: no cover - runtime import not required
    from spell_system import SpellManager
    from background import ParallaxBackground

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
    draw_cooldowns(screen, players, font)

    if countdown_timer is not None:
        render_countdown(screen, title_font or font, countdown_timer)
    elif show_fight_label:
        render_fight_label(screen, title_font or font)

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


def draw_cooldowns(surface: pygame.Surface, players: Sequence[Player], font: pygame.font.Font) -> None:
    """Render spell icons and cooldown overlays."""
    
    bar_width = 280
    spacing = 70
    base_y = 35
    left_x = 40
    right_x = surface.get_width() - bar_width - 40
    
    icon_size = 32
    icon_spacing = 8

    for idx, player in enumerate(players):
        column = idx % 2
        row = idx // 2
        x = left_x if column == 0 else right_x
        y = base_y + row * spacing
        
        # Position icons below mana bar
        icons_y = y + 60
        
        current_x = x
        
        for spell_def in player.spellbook:
            if not spell_def.icon:
                continue
                
            # Draw icon
            surface.blit(spell_def.icon, (current_x, icons_y))
            
            # Draw cooldown overlay
            cooldown = player.spell_cooldown(spell_def.name)
            max_cooldown = spell_def.stats.cooldown
            
            if cooldown > 0 and max_cooldown > 0:
                ratio = cooldown / max_cooldown
                h = int(icon_size * ratio)
                if h > 0:
                    overlay = pygame.Surface((icon_size, h), pygame.SRCALPHA)
                    overlay.fill((0, 0, 0, 180))
                    surface.blit(overlay, (current_x, icons_y + icon_size - h))
                
                # Draw cooldown text if > 0.5s
                if cooldown > 0.5:
                    text = font.render(f"{cooldown:.1f}", True, (255, 255, 255))
                    text_rect = text.get_rect(center=(current_x + icon_size // 2, icons_y + icon_size // 2))
                    surface.blit(text, text_rect)
            
            # Highlight selected spell
            if player.current_spell_name() == spell_def.name:
                pygame.draw.rect(surface, (255, 255, 200), (current_x - 2, icons_y - 2, icon_size + 4, icon_size + 4), 2)
            
            current_x += icon_size + icon_spacing


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
