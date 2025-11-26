from __future__ import annotations

from typing import Sequence

import pygame

from player import Player

from .core import Spell, SpellDefinition

class SpellCaster:
    """Handles cooldowns and input for multiple equipped spells."""

    def __init__(self, definitions: Sequence[SpellDefinition]) -> None:
        self.definitions = list(definitions)
        self.cooldowns: dict[str, float] = {d.name: 0.0 for d in definitions}
        self._was_pressed = False

    @property
    def definition(self) -> SpellDefinition:
        """Return the primary spell definition (for backward compatibility)."""
        return self.definitions[0] if self.definitions else None

    @property
    def cooldown_timer(self) -> float:
        """Return primary spell cooldown (compatibility)."""
        return self.cooldowns.get(self.definition.name, 0.0) if self.definition else 0.0

    def update(self, dt: float) -> None:
        if dt <= 0:
            return
        for name in self.cooldowns:
            self.cooldowns[name] = max(0.0, self.cooldowns[name] - dt)

    def handle_input(self, pressed: bool, player: Player, manager: "SpellManager", spell_name: str | None = None) -> bool:
        if hasattr(player, "is_alive") and not player.is_alive:
            self._was_pressed = pressed
            return False
        
        cast = False
        # If a specific spell is requested (e.g. via voice), we ignore the button 'pressed' edge detection
        # because voice commands are discrete events, not held buttons.
        if spell_name:
            cast = self._attempt_cast(player, manager, spell_name)
        
        # Otherwise, check for button press (primary spell)
        elif pressed and not self._was_pressed:
            if self.definition:
                cast = self._attempt_cast(player, manager, self.definition.name)
        
        self._was_pressed = pressed
        return cast

    def reset_input_state(self) -> None:
        self._was_pressed = False

    def _attempt_cast(self, player: Player, manager: "SpellManager", spell_name: str) -> bool:
        definition = next((d for d in self.definitions if d.name == spell_name), None)
        if not definition:
            return False

        if hasattr(player, "is_alive") and not player.is_alive:
            return False
        
        current_cooldown = self.cooldowns.get(spell_name, 0.0)
        if current_cooldown > 0:
            return False
            
        if not player.can_spend_mana(definition.stats.cost):
            return False
            
        position = player.spell_origin()
        direction = player.aim_direction()
        spell = definition.create_spell(player, position, direction)
        
        if not player.spend_mana(definition.stats.cost):
            return False
            
        manager.spawn(spell)
        self.cooldowns[spell_name] = definition.stats.cooldown
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
