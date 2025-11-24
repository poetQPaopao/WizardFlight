from __future__ import annotations

from typing import Sequence

import pygame

from player import Player

from .core import Spell, SpellDefinition

class SpellCaster:
    """Handles cooldowns and input for a single equipped spell."""

    def __init__(self, definition: SpellDefinition) -> None:
        self.definition = definition
        self.cooldown_timer = 0.0
        self._was_pressed = False

    def update(self, dt: float) -> None:
        if dt <= 0:
            return
        self.cooldown_timer = max(0.0, self.cooldown_timer - dt)

    def handle_input(self, pressed: bool, player: Player, manager: "SpellManager") -> bool:
        if hasattr(player, "is_alive") and not player.is_alive:
            self._was_pressed = pressed
            return False
        cast = False
        if pressed and not self._was_pressed:
            cast = self._attempt_cast(player, manager)
        self._was_pressed = pressed
        return cast

    def reset_input_state(self) -> None:
        self._was_pressed = False

    def _attempt_cast(self, player: Player, manager: "SpellManager") -> bool:
        if hasattr(player, "is_alive") and not player.is_alive:
            return False
        if self.cooldown_timer > 0:
            return False
        if not player.can_spend_mana(self.definition.stats.cost):
            return False
        position = player.spell_origin()
        direction = player.aim_direction()
        spell = self.definition.create_spell(player, position, direction)
        if not player.spend_mana(self.definition.stats.cost):
            return False
        manager.spawn(spell)
        self.cooldown_timer = self.definition.stats.cooldown
        return True


class SpellManager:
    def __init__(self, bounds: pygame.Rect) -> None:
        self.bounds = bounds
        self._spells: list[Spell] = []

    def spawn(self, spell: Spell) -> None:
        self._spells.append(spell)

    def update(self, dt: float, players: Sequence[Player]) -> None:
        survivors: list[Spell] = []
        for spell in self._spells:
            spell.update(dt, players, self.bounds)
            if spell.alive:
                survivors.append(spell)
        self._spells = survivors

    def draw(self, surface: pygame.Surface) -> None:
        for spell in self._spells:
            spell.draw(surface)

    def clear(self) -> None:
        self._spells.clear()

    def clear(self) -> None:
        self._spells.clear()
