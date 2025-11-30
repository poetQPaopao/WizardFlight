from __future__ import annotations

import argparse
from enum import Enum, auto
from typing import Optional, Sequence

import pygame
from controller import ControlScheme, PoseControlSystem, PoseKeyState, VoiceCommandManager
from player import Player
from spell_system import (
    SpellCaster, 
    SpellManager, 
    default_spellbook, 
    build_custom_spell,
    register_voice_command,
    SpellDefinition
)
from image_gen import generate_pixel_art_spell_icon
import os

SCREEN_SIZE = (1280, 720)
BACKGROUND = (18, 18, 28)
FPS = 60
BOUNDS_PADDING = 32

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


class GameState(Enum):
    """Enumeration describing the possible round states."""

    RUNNING = auto()
    GAME_OVER = auto()


class FlyingDemoGame:
    """Encapsulates the pygame setup, main loop, and pose input plumbing."""

    def __init__(self, *, use_pose_input: bool = True) -> None:
        """Initialize pygame surfaces, systems, and optional pose input."""

        pygame.init()
        self._screen = pygame.display.set_mode(SCREEN_SIZE)
        pygame.display.set_caption("Flying Player Demo")
        self._clock = pygame.time.Clock()
        self._font = pygame.font.SysFont("Inter", 20)
        self._world_bounds = self._screen.get_rect().inflate(-BOUNDS_PADDING * 2, -BOUNDS_PADDING * 2)
        self.players: list[Player] = []
        self._player_sprites = pygame.sprite.Group()
        self._player_spellcasters: list[SpellCaster] = []
        self._spell_manager: SpellManager = SpellManager(self._world_bounds)
        self._pose_system: Optional[PoseControlSystem] = None
        self._running = True
        self._pressed: Optional[Sequence[bool]] = None
        self.game_state = GameState.RUNNING
        self._winner_name: Optional[str] = None
        self._round_time = 0.0
        self._custom_spells: list[SpellDefinition] = []
        self._voice_manager = VoiceCommandManager()
        self._initialize_round()
        if use_pose_input:
            self._pose_system = PoseControlSystem(max_players=len(self.players))
            if hasattr(self._pose_system, "reset"):
                self._pose_system.reset()

    def _create_players(self) -> list[Player]:
        """Instantiate the default keyboard-controlled player roster."""

        return [
            Player(
                name="Player 1",
                position=(SCREEN_SIZE[0] * 0.25, SCREEN_SIZE[1] / 2),
                controls=ControlScheme.wasd(),
                color=(90, 200, 255),
                bounds=self._world_bounds,
            ),
            Player(
                name="Player 2",
                position=(SCREEN_SIZE[0] * 0.75, SCREEN_SIZE[1] / 2),
                controls=ControlScheme.arrow_keys(),
                color=(255, 180, 95),
                bounds=self._world_bounds,
            ),
        ]

    def _build_spellcasters(self) -> list[SpellCaster]:
        """Create per-player spellcasters with the active spell list."""

        spell_defs = default_spellbook() + self._custom_spells
        casters: list[SpellCaster] = []
        for _ in range(len(self.players)):
            # Give everyone the full spellbook so they can cast any spell
            casters.append(SpellCaster(spell_defs))
            
        return casters

    def run(self) -> None:
        """Drive the main game loop until the window closes or quits."""

        try:
            while self._running:
                dt = self._clock.tick(FPS) / 1000.0
                self._handle_events()
                if not self._running:
                    break
                self._update(dt)
                if not self._running:
                    break
                self._render()
        finally:
            self._shutdown()

    def _handle_events(self) -> None:
        """Process pygame events and capture the current keyboard state."""

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self._running = False
                elif event.key == pygame.K_r and self.game_state == GameState.GAME_OVER:
                    self._initialize_round()

        self._pressed = pygame.key.get_pressed()
        if self._pressed[pygame.K_ESCAPE]:
            self._running = False

    def _update(self, dt: float) -> None:
        """Advance controllers, players, spells, and voice casting."""

        if self._pressed is None or self.game_state != GameState.RUNNING:
            return

        self._round_time += dt

        if self._pose_system:
            self._pose_system.tick()
            if self._pose_system.quit_requested:
                self._running = False
                return

        self._voice_manager.process_audio(self.players, self._player_spellcasters)

        for idx, player in enumerate(self.players):
            overrides: dict[int, bool] = {}
            if self._pose_system:
                overrides = self._pose_system.build_overrides(idx, player.controls)
            pressed_for_player: Sequence[bool] = self._pressed
            if overrides:
                pressed_for_player = PoseKeyState(overrides, self._pressed)
            player.update(dt, pressed_for_player)
            caster = self._player_spellcasters[idx]
            caster.update(dt)
            pressed_cast = bool(pressed_for_player[player.controls.cast])

            cast_via_voice = self._voice_manager.try_cast_for_player(idx, caster, player, self._spell_manager)
            if not cast_via_voice:
                caster.handle_input(pressed_cast, player, self._spell_manager)

        self._spell_manager.update(dt, self.players)
        self._evaluate_round_outcome()

    def _render(self) -> None:
        """Draw arena bounds, sprites, spells, UI, and overlays."""

        self._screen.fill(BACKGROUND)
        pygame.draw.rect(self._screen, (40, 40, 70), self._world_bounds, width=2, border_radius=8)
        self._player_sprites.draw(self._screen)
        self._spell_manager.draw(self._screen)
        draw_health(self._screen, self.players, self._font)
        if self.game_state == GameState.GAME_OVER:
            self._render_game_over()
        pygame.display.flip()

    def _shutdown(self) -> None:
        """Release pose/audio controllers and close pygame."""

        if self._pose_system:
            self._pose_system.shutdown()
        self._voice_manager.shutdown()
        pygame.quit()

    def _initialize_round(self) -> None:
        """Reset players, controllers, and timers to start a new round."""

        first_setup = not self._voice_manager.configured
        self.players = self._create_players()
        self._player_sprites = pygame.sprite.Group(*self.players)
        self._spell_manager = SpellManager(self._world_bounds)
        self._player_spellcasters = self._build_spellcasters()
        if first_setup:
            if not self._voice_manager.setup_audio_inputs(self.players):
                self._running = False
                return
            if self._running:
                self._setup_custom_spells()
            if not self._running:
                return
        self._voice_manager.reset(len(self.players))
        self._winner_name = None
        self._round_time = 0.0
        self.game_state = GameState.RUNNING
        if self._pose_system and hasattr(self._pose_system, "reset"):
            self._pose_system.reset()

    def _evaluate_round_outcome(self) -> None:
        """Mark the round complete once zero or one players remain alive."""

        if self.game_state != GameState.RUNNING:
            return
        living_players = [player for player in self.players if getattr(player, "is_alive", True)]
        if len(living_players) > 1:
            return
        self.game_state = GameState.GAME_OVER
        self._winner_name = living_players[0].name if living_players else None
        self._voice_manager.reset(len(self.players))
        for caster in self._player_spellcasters:
            caster.reset_input_state()
        self._spell_manager.clear()
        outcome = self._winner_name or "No one"
        print(f"[game] round over: {outcome} wins")

    def _render_game_over(self) -> None:
        """Draw a translucent overlay announcing the round winner."""

        overlay = pygame.Surface(self._screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        self._screen.blit(overlay, (0, 0))

        lines = ["Game Over"]
        if self._winner_name:
            lines.append(f"{self._winner_name} wins!")
        else:
            lines.append("It's a draw!")
        lines.append("Press R to restart")

        center_x = self._screen.get_width() // 2
        center_y = self._screen.get_height() // 2
        for idx, text in enumerate(lines):
            label = self._font.render(text, True, (240, 240, 255))
            rect = label.get_rect(center=(center_x, center_y + idx * 28))
            self._screen.blit(label, rect)

    def _setup_custom_spells(self) -> None:
        """Offer an interactive prompt to build and register custom spells."""

        print("\n--- Custom Spell Creation ---")
        while True:
            try:
                choice = input("Do you want to create a custom spell? (y/n) [default: n]: ").strip().lower()
                if choice != 'y':
                    break
                
                name = input("Enter spell name (e.g. 'Lightning'): ").strip()
                if not name:
                    print("Name cannot be empty.")
                    continue
                
                description = input("Enter visual description for icon generation (e.g. 'yellow lightning bolt'): ").strip()
                if not description:
                    print("Description cannot be empty.")
                    continue
                
                # Generate icon
                filename = f"{name.lower().replace(' ', '_')}.png"
                output_path = os.path.join("assets", "custom_spells", filename)
                
                success = generate_pixel_art_spell_icon(description, output_path)
                
                if success:
                    # Create spell definition
                    spell_def = build_custom_spell(name, output_path)
                    self._custom_spells.append(spell_def)
                    
                    # Register voice command
                    # Use the name as the keyword
                    register_voice_command(name, name)
                    print(f"Successfully created spell '{name}'! You can cast it by saying '{name}'.")
                    
                    # Rebuild spellcasters to include new spell immediately
                    self._player_spellcasters = self._build_spellcasters()
                else:
                    print("Failed to generate spell icon. Spell creation aborted.")
                    
            except KeyboardInterrupt:
                print("\nSpell creation cancelled.")
                break


def run(*, use_pose_input: bool = True) -> None:
    """Convenience helper that instantiates and runs the game loop."""

    game = FlyingDemoGame(use_pose_input=use_pose_input)
    game.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Flying spell demo")
    parser.add_argument(
        "--disable-pose",
        action="store_true",
        help="Disable pose input so only keyboard controls are used.",
    )
    args = parser.parse_args()
    run(use_pose_input=not args.disable_pose)
