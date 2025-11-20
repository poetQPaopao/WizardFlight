from __future__ import annotations

import argparse
from typing import Optional, Sequence

import pygame
from controls import ControlScheme, PoseControlSystem, PoseKeyState
from player import Player
from spell_system import SpellCaster, SpellManager, default_spellbook, match_voice_command
from audio import AudioListener

SCREEN_SIZE = (1280, 720)
BACKGROUND = (18, 18, 28)
FPS = 60
BOUNDS_PADDING = 32

def draw_health(surface: pygame.Surface, players: Sequence[Player], font: pygame.font.Font) -> None:
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


class FlyingDemoGame:
    """Encapsulates the pygame setup, main loop, and pose input plumbing."""

    def __init__(self, *, use_pose_input: bool = True) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode(SCREEN_SIZE)
        pygame.display.set_caption("Flying Player Demo")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Inter", 20)
        self.world_bounds = self.screen.get_rect().inflate(-BOUNDS_PADDING * 2, -BOUNDS_PADDING * 2)
        self.players = self._create_players()
        self.player_sprites = pygame.sprite.Group(*self.players)
        self.spell_manager = SpellManager(self.world_bounds)
        self.player_spellcasters = self._build_spellcasters()
        self.pose_system = PoseControlSystem(max_players=len(self.players)) if use_pose_input else None
        self.running = True
        self._pressed: Optional[Sequence[bool]] = None
        self.AudioListener = AudioListener()
        self.AudioListener.start()
        self._pending_voice_spell: Optional[str] = None
        self._voice_blocked = False
        self._voice_last_partial = ""
        self._voice_prev_stage = ""

    def _create_players(self) -> list[Player]:
        return [
            Player(
                name="Player 1",
                position=(SCREEN_SIZE[0] * 0.25, SCREEN_SIZE[1] / 2),
                controls=ControlScheme.wasd(),
                color=(90, 200, 255),
                bounds=self.world_bounds,
            ),
            Player(
                name="Player 2",
                position=(SCREEN_SIZE[0] * 0.75, SCREEN_SIZE[1] / 2),
                controls=ControlScheme.arrow_keys(),
                color=(255, 180, 95),
                bounds=self.world_bounds,
            ),
        ]

    def _build_spellcasters(self) -> list[SpellCaster]:
        spell_defs = default_spellbook()
        casters: list[SpellCaster] = []
        for idx in range(len(self.players)):
            definition = spell_defs[idx % len(spell_defs)]
            casters.append(SpellCaster(definition))
            
        return casters

    def run(self) -> None:
        try:
            while self.running:
                dt = self.clock.tick(FPS) / 1000.0
                self._handle_events()
                if not self.running:
                    break
                self._update(dt)
                if not self.running:
                    break
                self._render()
        finally:
            self._shutdown()

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

        self._pressed = pygame.key.get_pressed()
        if self._pressed[pygame.K_ESCAPE]:
            self.running = False

    def _update(self, dt: float) -> None:
        if self._pressed is None:
            return

        if self.pose_system:
            self.pose_system.tick()
            if self.pose_system.quit_requested:
                self.running = False
                return
        if self.AudioListener:
            final_text = self.AudioListener.consume_final()
            if final_text:
                print(f"[voice] transcript: {final_text}")
                if not self._voice_blocked:
                    spell_name = match_voice_command(final_text)
                    if spell_name:
                        print(f"[voice] matched spell: {spell_name}")
                        self._pending_voice_spell = spell_name
                        self._voice_blocked = True

            partial_text = self.AudioListener.command
            stage = self.AudioListener.command_stage or ""
            if stage != "final" and self._voice_prev_stage == "final":
                self._voice_blocked = False
                self._voice_last_partial = ""
            if stage != "final" and partial_text:
                if partial_text != self._voice_last_partial:
                    print(f"[voice] partial: {partial_text}")
                    self._voice_last_partial = partial_text
                    if not self._voice_blocked:
                        spell_name = match_voice_command(partial_text)
                        if spell_name:
                            print(f"[voice] matched spell: {spell_name}")
                            self._pending_voice_spell = spell_name
                            self._voice_blocked = True
            elif not partial_text and stage != "final":
                self._voice_last_partial = ""
                self._voice_blocked = False
            self._voice_prev_stage = stage


        for idx, player in enumerate(self.players):
            overrides: dict[int, bool] = {}
            if self.pose_system:
                overrides = self.pose_system.build_overrides(idx, player.controls)
            pressed_for_player: Sequence[bool] = self._pressed
            if overrides:
                pressed_for_player = PoseKeyState(overrides, self._pressed)
            player.update(dt, pressed_for_player)
            caster = self.player_spellcasters[idx]
            caster.update(dt)
            pressed_cast = bool(pressed_for_player[player.controls.cast])
            if self._pending_voice_spell and caster.definition.name.lower() == self._pending_voice_spell.lower():
                pressed_cast = True
                # consume after applying to allow one cast per detection
                self._pending_voice_spell = None
            caster.handle_input(pressed_cast, player, self.spell_manager)

        self.spell_manager.update(dt, self.players)

    def _render(self) -> None:
        self.screen.fill(BACKGROUND)
        pygame.draw.rect(self.screen, (40, 40, 70), self.world_bounds, width=2, border_radius=8)
        self.player_sprites.draw(self.screen)
        self.spell_manager.draw(self.screen)
        draw_health(self.screen, self.players, self.font)
        pygame.display.flip()

    def _shutdown(self) -> None:
        if self.pose_system:
            self.pose_system.shutdown()
        if self.AudioListener and self.AudioListener.running:
            self.AudioListener.stop()
        pygame.quit()


def run(*, use_pose_input: bool = True) -> None:
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
