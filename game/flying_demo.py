from __future__ import annotations

import argparse
from enum import Enum, auto
from typing import Optional, Sequence

import pygame
from background import ParallaxBackground
from controller import ControlScheme, PoseControlSystem, PoseKeyState, VoiceCommandManager
from custom_spells import CustomSpellCreator
from player import Player
from spell_system import (
    SpellManager,
    default_spellbook,
    SpellDefinition,
)
from ui import render_frame

SCREEN_SIZE = (1280, 720)
FPS = 60
BOUNDS_PADDING = 8
PLAYER_SPRITE_SIZE = (64, 64)


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
        self._title_font = pygame.font.SysFont("Inter", 64, bold=True)
        self._world_bounds = self._screen.get_rect().inflate(-BOUNDS_PADDING * 2, -BOUNDS_PADDING * 2)
        self.players: list[Player] = []
        self._spell_manager: SpellManager = SpellManager(self._world_bounds)
        self._background = ParallaxBackground(SCREEN_SIZE)
        self._pose_system: Optional[PoseControlSystem] = None
        self._running = True
        self._pressed: Optional[Sequence[bool]] = None
        self.game_state = GameState.RUNNING
        self._winner_name: Optional[str] = None
        self._round_time = 0.0
        self._spell_library: dict[str, SpellDefinition] = {
            spell.name: spell for spell in default_spellbook()
        }
        self._custom_spell_creator: Optional[CustomSpellCreator] = None
        self._voice_manager = VoiceCommandManager()
        self._initialize_round()
        if use_pose_input:
            self._pose_system = PoseControlSystem(max_players=len(self.players))
            if hasattr(self._pose_system, "reset"):
                self._pose_system.reset()

    @staticmethod
    def _load_player_sprite(path: str) -> pygame.Surface:
        """Load and scale player sprites down to the desired on-screen size."""

        sprite = pygame.image.load(path).convert_alpha()
        return pygame.transform.scale(sprite, PLAYER_SPRITE_SIZE)

    def _create_players(self) -> list[Player]:
        """Instantiate the default keyboard-controlled player roster."""

        return [
            Player(
                name="Player 1",
                position=(SCREEN_SIZE[0] * 0.25, SCREEN_SIZE[1] / 2),
                controls=ControlScheme.wasd(),
                spellbook=default_spellbook(),
                color=(90, 200, 255),
                bounds=self._world_bounds,
                sprite=self._load_player_sprite("assets/wizard1.png"),
            ),
            Player(
                name="Player 2",
                position=(SCREEN_SIZE[0] * 0.75, SCREEN_SIZE[1] / 2),
                controls=ControlScheme.arrow_keys(),
                spellbook=default_spellbook(),
                color=(255, 180, 95),
                bounds=self._world_bounds,
                sprite=self._load_player_sprite("assets/wizard2.png"),
            ),
        ]

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

        self._background.update(dt)
        if self._pressed is None or self.game_state != GameState.RUNNING:
            return

        self._round_time += dt

        if self._handle_pose_input():
            return

        self._voice_manager.process_audio(self.players)
        self._update_players(dt)
        self._update_player_facing()
        self._spell_manager.update(dt, self.players)
        self._evaluate_round_outcome()

    def _handle_pose_input(self) -> bool:
        if not self._pose_system:
            return False

        self._pose_system.tick()
        if self._pose_system.quit_requested:
            self._running = False
            return True
        return False

    def _update_players(self, dt: float) -> None:
        for idx, player in enumerate(self.players):
            pressed_for_player = self._controls_for_player(idx, player)
            player.update(dt, pressed_for_player)
            player.update_spellcasting(dt)
            self._handle_spellcasting(idx, player, pressed_for_player)

    def _update_player_facing(self) -> None:
        """Flip sprites so players face each other based on x-position."""

        if len(self.players) < 2:
            return
        p1, p2 = self.players[0], self.players[1]
        if p1.rect.centerx > p2.rect.centerx:
            p1.set_facing_left(True)
            p2.set_facing_left(False)
        elif p1.rect.centerx < p2.rect.centerx:
            p1.set_facing_left(False)
            p2.set_facing_left(True)

    def _controls_for_player(self, idx: int, player: Player) -> Sequence[bool]:
        pressed_for_player: Sequence[bool] = self._pressed or []
        if not self._pose_system:
            return pressed_for_player

        overrides = self._pose_system.build_overrides(idx, player.controls)
        if overrides:
            return PoseKeyState(overrides, self._pressed)
        return pressed_for_player

    def _handle_spellcasting(self, idx: int, player: Player, pressed_for_player: Sequence[bool]) -> None:
        pressed_cast = bool(pressed_for_player[player.controls.cast])
        cast_via_voice = self._voice_manager.try_cast_for_player(idx, player, self._spell_manager)
        if not cast_via_voice:
            player.handle_cast_input(pressed_cast, self._spell_manager)

    def _render(self) -> None:
        """Draw arena bounds, sprites, spells, UI, and overlays."""

        render_frame(
            screen=self._screen,
            world_bounds=self._world_bounds,
            spell_manager=self._spell_manager,
            players=self.players,
            font=self._font,
            title_font=self._title_font,
            game_over=self.game_state == GameState.GAME_OVER,
            winner_name=self._winner_name,
            background=self._background,
        )

    def _shutdown(self) -> None:
        """Release pose/audio controllers and close pygame."""

        if self._pose_system:
            self._pose_system.shutdown()
        self._voice_manager.shutdown()
        pygame.quit()

    def _initialize_round(self) -> None:
        """Reset players, controllers, and timers to start a new round."""

        first_setup = not self._voice_manager.configured
        self._reset_round_objects()
        if first_setup and not self._prepare_voice_setup():
            return
        self._voice_manager.reset(len(self.players))
        self._reset_round_state()

    def _reset_round_objects(self) -> None:
        self.players = self._create_players()
        self._spell_manager = SpellManager(self._world_bounds)

    def _prepare_voice_setup(self) -> bool:
        if not self._voice_manager.setup_audio_inputs(self.players):
            self._running = False
            return False
        if self._running:
            self._custom_spell_creator = CustomSpellCreator(
                players=self.players,
                spell_library=self._spell_library,
            )
            self._custom_spell_creator.run()
        return self._running

    def _reset_round_state(self) -> None:
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
        for player in self.players:
            player.reset_spellcasting_state()
        self._spell_manager.clear()
        outcome = self._winner_name or "No one"
        print(f"[game] round over: {outcome} wins")


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
