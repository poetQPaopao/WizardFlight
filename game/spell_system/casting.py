from __future__ import annotations

from typing import Sequence, TYPE_CHECKING

import pygame

from .core import Spell, SpellDefinition

if TYPE_CHECKING:  # pragma: no cover - typing only
    from player import Player

class SpellCaster:
    """Handles cooldowns and input for multiple equipped spells."""

    def __init__(self, definitions: Sequence[SpellDefinition]) -> None:
        """Store equipped spell definitions and initialize cooldown timers."""

        self.definitions = list(definitions)
        self.cooldowns: dict[str, float] = {d.name: 0.0 for d in definitions}
        self._was_pressed = False
        self._voice_lookup = self._build_voice_lookup()

    @property
    def definition(self) -> SpellDefinition:
        """Return the primary spell definition (for backward compatibility)."""
        return self.definitions[0] if self.definitions else None

    @property
    def cooldown_timer(self) -> float:
        """Return primary spell cooldown (compatibility)."""
        return self.cooldowns.get(self.definition.name, 0.0) if self.definition else 0.0

    def update(self, dt: float) -> None:
        """Reduce running cooldown timers using the supplied delta time."""

        if dt <= 0:
            return
        for name in self.cooldowns:
            self.cooldowns[name] = max(0.0, self.cooldowns[name] - dt)

    def handle_input(self, pressed: bool, player: Player, manager: "SpellManager", spell_name: str | None = None) -> bool:
        """Handle button edges or explicit spell names to trigger casts."""

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
            manual_spell = self._selected_spell_for_player(player)
            if manual_spell:
                cast = self._attempt_cast(player, manager, manual_spell)
        
        self._was_pressed = pressed
        return cast

    def reset_input_state(self) -> None:
        """Clear button state so edge detection works after interruptions."""

        self._was_pressed = False

    def _attempt_cast(self, player: Player, manager: "SpellManager", spell_name: str) -> bool:
        """Validate mana/cooldown rules and spawn a spell when possible."""

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
        if hasattr(definition, "play_sound"):
            definition.play_sound()
        self.cooldowns[spell_name] = definition.stats.cooldown
        return True

    def match_voice_commands(self, transcript: str) -> list[str]:
        """Return spell names mentioned in ``transcript`` for this caster."""

        if not transcript or not self._voice_lookup:
            return []
        lowered = transcript.lower()
        matches: list[tuple[int, str, str]] = []
        for keyword, spell_name in self._voice_lookup.items():
            index = lowered.find(keyword)
            if index == -1:
                continue
            matches.append((index, keyword, spell_name))
        if not matches:
            return []
        matches.sort(key=lambda item: (item[0], -len(item[1])))
        ordered: list[str] = []
        seen: set[str] = set()
        for _, _, spell_name in matches:
            if spell_name in seen:
                continue
            ordered.append(spell_name)
            seen.add(spell_name)
        return ordered

    def _build_voice_lookup(self) -> dict[str, str]:
        """Map normalized voice triggers to spell names for quick matching."""

        lookup: dict[str, str] = {}
        for definition in self.definitions:
            for trigger in getattr(definition, "voice_triggers", ()):
                if trigger and trigger not in lookup:
                    lookup[trigger] = definition.name
        return lookup

    def _selected_spell_for_player(self, player: Player) -> str | None:
        """Return the player's active spell or fall back to the first slot."""

        if hasattr(player, "current_spell_name"):
            selected = player.current_spell_name()
            if selected:
                return selected
        return self.definition.name if self.definition else None


class SpellManager:
    """Own spell entities, updating and drawing them each frame."""

    def __init__(self, bounds: pygame.Rect) -> None:
        """Store arena bounds used for culling and collision checks."""

        self.bounds = bounds
        self._spells: list[Spell] = []

    def spawn(self, spell: Spell) -> None:
        """Add a spell to the active list."""

        self._spells.append(spell)

    def update(self, dt: float, players: Sequence[Player]) -> None:
        """Advance every spell and drop any that are no longer alive."""

        survivors: list[Spell] = []
        for spell in self._spells:
            spell.update(dt, players, self.bounds)
            if spell.alive:
                survivors.append(spell)
        self._spells = survivors

    def set_bounds(self, bounds: pygame.Rect) -> None:
        """Refresh the arena bounds without dropping active spells."""

        self.bounds = pygame.Rect(bounds)

    def draw(self, surface: pygame.Surface) -> None:
        """Render every spell to the supplied surface."""

        for spell in self._spells:
            spell.draw(surface)

    def clear(self) -> None:
        """Remove all active spells (e.g., between rounds)."""

        self._spells.clear()
