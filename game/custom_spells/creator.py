from __future__ import annotations

import os
from typing import Optional, Sequence, TYPE_CHECKING

from image_gen import generate_pixel_art_spell_icon
from spell_system import SpellDefinition, build_custom_spell, generate_parameters

if TYPE_CHECKING:  # pragma: no cover - typing helpers
    from player import Player


class CustomSpellCreator:
    """Interactive helper to build custom spells and assign them to players."""

    def __init__(
        self,
        *,
        players: Sequence["Player"],
        spell_library: dict[str, SpellDefinition],
        assets_dir: str = "assets/custom_spells",
    ) -> None:
        self._players = players
        self._spell_library = spell_library
        self._assets_dir = assets_dir

    def run(self) -> None:
        """Entry point for the interactive custom spell creation flow."""

        print("\n--- Custom Spell Creation ---")
        while self._prompt_should_continue():
            try:
                spell_input = self._collect_custom_spell_input()
            except KeyboardInterrupt:
                print("\nSpell creation cancelled.")
                break
            if not spell_input:
                continue
            name, description, voice_triggers = spell_input
            self._create_and_assign_spell(name, description, voice_triggers)

    def _prompt_should_continue(self) -> bool:
        try:
            choice = input("Do you want to create a custom spell? (y/n) [default: n]: ").strip().lower()
        except KeyboardInterrupt:
            print("\nSpell creation cancelled.")
            return False
        return choice == "y"

    def _collect_custom_spell_input(self) -> Optional[tuple[str, str, list[str]]]:
        name = input("Enter spell name (e.g. 'Lightning'): ").strip()
        if not name:
            print("Name cannot be empty.")
            return None

        description = input("Enter visual description for icon generation (e.g. 'yellow lightning bolt'): ").strip()
        if not description:
            print("Description cannot be empty.")
            return None

        voice_triggers = self._parse_voice_triggers(name)
        return name, description, voice_triggers

    def _parse_voice_triggers(self, default_name: str) -> list[str]:
        voice_text = input("Enter comma-separated voice keywords (default uses spell name): ").strip()
        voice_triggers = [token.strip() for token in voice_text.split(",") if token.strip()]
        return voice_triggers or [default_name]

    def _create_and_assign_spell(self, name: str, description: str, voice_triggers: list[str]) -> None:
        output_path = self._build_output_path(name)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        success = generate_pixel_art_spell_icon(description, output_path)
        spell_parameters = generate_parameters(description)
        if not success:
            print("Failed to generate spell icon. Spell creation aborted.")
            return

        spell_def = build_custom_spell(name, output_path, voice_triggers=voice_triggers)
        self._spell_library[spell_def.name] = spell_def
        self._assign_custom_spell_to_players(spell_def)
        print(f"Successfully created spell '{name}'! Voice keywords: {', '.join(voice_triggers)}")

    def _build_output_path(self, name: str) -> str:
        filename = f"{name.lower().replace(' ', '_')}.png"
        return os.path.join(self._assets_dir, filename)

    def _assign_custom_spell_to_players(self, spell_def: SpellDefinition) -> None:
        if not self._players:
            return

        prompt = (
            "Assign this spell to players by name or number (comma separated, 'all' for everyone) [default: all]: "
        )
        selection = input(prompt).strip().lower()
        if selection in ("", "all"):
            indices = list(range(len(self._players)))
        else:
            indices = self._parse_player_selection(selection)
            if not indices:
                print("No valid players selected. Assigning to everyone by default.")
                indices = list(range(len(self._players)))

        for idx in indices:
            self._add_spell_to_player(self._players[idx], spell_def)

    def _parse_player_selection(self, selection: str) -> list[int]:
        lookup = {player.name.lower(): idx for idx, player in enumerate(self._players)}
        indices: list[int] = []
        for token in selection.split(","):
            candidate = token.strip()
            if not candidate:
                continue
            if candidate.isdigit():
                idx = int(candidate) - 1
                if 0 <= idx < len(self._players):
                    indices.append(idx)
                continue
            idx = lookup.get(candidate.lower())
            if idx is not None:
                indices.append(idx)
        return self._dedupe_preserve_order(indices)

    @staticmethod
    def _dedupe_preserve_order(indices: list[int]) -> list[int]:
        seen: set[int] = set()
        ordered: list[int] = []
        for idx in indices:
            if idx in seen:
                continue
            seen.add(idx)
            ordered.append(idx)
        return ordered

    def _add_spell_to_player(self, player: "Player", spell_def: SpellDefinition) -> None:
        """Add ``spell_def`` to ``player`` if not already known."""

        if player.knows_spell(spell_def.name):
            return
        updated_book = list(player.spellbook) + [spell_def]
        player.set_spellbook(updated_book)
