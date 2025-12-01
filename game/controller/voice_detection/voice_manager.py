from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, TYPE_CHECKING

from .audio_input import (
    MicrophoneConfigurationCancelled,
    MultiMicAudioController,
    interactive_configure_microphones,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from player import Player
    from spell_system.casting import SpellManager


@dataclass
class VoiceSpellRequest:
    """Tracks a pending voice command targeted at a specific player."""

    spell_name: str
    player_index: int
    last_reason: str = ""


class VoiceCommandManager:
    """Owns microphone setup, transcript parsing, and queued spell casts."""

    def __init__(self) -> None:
        self._player_sources: dict[int, str] = {}
        self._source_to_player: dict[str, int] = {}
        self._pending_requests: list[VoiceSpellRequest] = []
        self._voice_last_errors: dict[str, str] = {}
        self._voice_processed_seq: dict[int, int] = {}
        self._voice_processed_count: dict[int, int] = {}
        self._audio_controller: Optional[MultiMicAudioController] = None

    @property
    def configured(self) -> bool:
        """Return ``True`` when microphones have been configured."""

        return self._audio_controller is not None

    def setup_audio_inputs(self, players: Sequence["Player"]) -> bool:
        """Interactively request microphone mappings for each player."""

        player_names = [player.name for player in players]
        try:
            configs = interactive_configure_microphones(player_names)
        except MicrophoneConfigurationCancelled:
            print("\n[voice] Microphone configuration cancelled. Exiting game.")
            return False

        self._player_sources.clear()
        self._source_to_player.clear()
        for config in configs:
            player_idx = next((i for i, player in enumerate(players) if player.name == config.source), None)
            if player_idx is not None:
                self._player_sources[player_idx] = config.source
                self._source_to_player[config.source] = player_idx

        self._audio_controller = MultiMicAudioController(configs)
        return True

    def shutdown(self) -> None:
        """Stop streaming audio and release controller resources."""

        if self._audio_controller:
            self._audio_controller.stop()
            self._audio_controller = None

    def reset(self, player_count: int) -> None:
        """Clear queued voice requests and transcript bookkeeping."""

        self._pending_requests.clear()
        self._voice_processed_seq = {idx: -1 for idx in range(player_count)}
        self._voice_processed_count = {idx: 0 for idx in range(player_count)}
        self._voice_last_errors.clear()

    def process_audio(
        self,
        players: Sequence["Player"],
    ) -> None:
        """Consume audio snapshots and enqueue new spell commands."""

        if not self._audio_controller:
            return

        controller_errors = self._audio_controller.errors()
        seen_sources = set()
        for source, message in controller_errors:
            seen_sources.add(source)
            last = self._voice_last_errors.get(source)
            if message != last:
                print(f"[voice:{source}] error: {message}")
                self._voice_last_errors[source] = message
        for source in list(self._voice_last_errors):
            if source not in seen_sources:
                del self._voice_last_errors[source]

        for snapshot in self._audio_controller.snapshots():
            player_idx = self._source_to_player.get(snapshot.source)
            if player_idx is None or player_idx >= len(players):
                continue
            player = players[player_idx]

            if player_idx not in self._voice_processed_seq:
                self._voice_processed_seq[player_idx] = -1
                self._voice_processed_count[player_idx] = 0

            if snapshot.sequence != self._voice_processed_seq[player_idx]:
                self._voice_processed_seq[player_idx] = snapshot.sequence
                self._voice_processed_count[player_idx] = 0

            if not snapshot.text:
                continue

            found_spells = player.match_voice_commands(snapshot.text)
            processed_count = self._voice_processed_count[player_idx]
            if len(found_spells) > processed_count:
                new_spells = found_spells[processed_count:]
                print(f"[voice:{snapshot.source}] new commands: {new_spells} (from '{snapshot.text}')")
                self._enqueue_voice_spells(
                    new_spells,
                    player_idx,
                    snapshot.source,
                    players,
                )
                self._voice_processed_count[player_idx] = len(found_spells)

    def try_cast_for_player(
        self,
        player_index: int,
        player: "Player",
        spell_manager: "SpellManager",
    ) -> bool:
        """Attempt to fire the next queued voice command for one player."""

        request = self.pending_request_for(player_index)
        if not request:
            return False

        if player.cast_spell_by_name(request.spell_name, spell_manager):
            print(f"[voice] cast spell: {request.spell_name}")
            self._remove_request(request)
            return True

        definition = player.get_spell_definition(request.spell_name)
        if not definition:
            self._remove_request(request)
            return False

        reason_message = ""
        cooldown = player.spell_cooldown(definition.name)
        if cooldown > 0:
            reason_message = f"[voice] waiting for {definition.name} (cooldown {cooldown:.2f}s)"
        elif not player.can_spend_mana(definition.stats.cost):
            reason_message = (
                f"[voice] waiting for {definition.name} (mana {player.mana:.1f}/{definition.stats.cost:.1f})"
            )

        if reason_message and reason_message != request.last_reason:
            print(reason_message)
            request.last_reason = reason_message
        if not reason_message:
            request.last_reason = ""

        return False

    def pending_request_for(self, player_index: int) -> Optional[VoiceSpellRequest]:
        """Return the next queued request for ``player_index`` if one exists."""

        return next((request for request in self._pending_requests if request.player_index == player_index), None)

    def _enqueue_voice_spells(
        self,
        spell_names: Sequence[str],
        player_index: int,
        source: str,
        players: Sequence["Player"],
    ) -> None:
        """Queue valid spells referenced in the transcript for a player."""

        if not spell_names:
            return
        if player_index >= len(players):
            print(f"[voice:{source}] no player configured for index {player_index}")
            return

        player = players[player_index]
        for spell_name in spell_names:
            if player.knows_spell(spell_name):
                self._pending_requests.append(VoiceSpellRequest(spell_name, player_index))
                print(f"[voice:{source}] matched spell: {spell_name}")
            else:
                print(f"[voice:{source}] no equipped spell matches '{spell_name}' for {player.name}")

    def _remove_request(self, request: VoiceSpellRequest) -> None:
        """Safely drop a processed voice request from the queue."""

        try:
            self._pending_requests.remove(request)
        except ValueError:
            pass