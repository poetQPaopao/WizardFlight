from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, TYPE_CHECKING

from .audio_input import (
    AudioController,
    MicrophoneConfigurationCancelled,
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
        self._player_sources: dict[int, int] = {}
        self._source_to_player: dict[int, int] = {}
        self._source_labels: dict[int, str] = {}
        self._pending_requests: list[VoiceSpellRequest] = []
        self._voice_last_errors: dict[int, str] = {}
        self._live_word_cache: dict[int, tuple[int, list[str], str, list[str]]] = {}
        self._shared_source_index: Optional[int] = None
        self._audio_controller: Optional[AudioController] = None

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
        if not configs:
            print("\n[voice] No microphones selected; voice control disabled.")
            return False

        self._player_sources.clear()
        self._source_to_player.clear()
        self._source_labels = {config.source_index: (config.label or f"source-{config.source_index}") for config in configs}
        self._shared_source_index = configs[0].source_index if len(configs) == 1 else None

        if self._shared_source_index is not None:
            for idx in range(len(players)):
                self._player_sources[idx] = self._shared_source_index
        else:
            for config in configs:
                player_idx: Optional[int] = config.source_index if 0 <= config.source_index < len(players) else None
                if player_idx is None and config.label:
                    player_idx = next((i for i, player in enumerate(players) if player.name == config.label), None)
                if player_idx is not None:
                    self._player_sources[player_idx] = config.source_index
                    self._source_to_player[config.source_index] = player_idx

        self._audio_controller = AudioController(configs)
        return True

    def shutdown(self) -> None:
        """Stop streaming audio and release controller resources."""

        if self._audio_controller:
            self._audio_controller.stop()
            self._audio_controller = None

    def reset(self, player_count: int) -> None:
        """Clear queued voice requests and transcript bookkeeping."""

        self._pending_requests.clear()
        self._voice_last_errors.clear()
        self._live_word_cache.clear()

    def process_audio(
        self,
        players: Sequence["Player"],
    ) -> None:
        """Consume live transcripts and enqueue spell commands as words arrive."""

        if not self._audio_controller:
            return

        controller_errors = self._audio_controller.errors()
        seen_sources: set[int] = set()
        for source_index, source_label, message in controller_errors:
            seen_sources.add(source_index)
            last = self._voice_last_errors.get(source_index)
            if message != last:
                label = source_label or self._source_labels.get(source_index, f"source-{source_index}")
                print(f"[voice:{label}] error: {message}")
                self._voice_last_errors[source_index] = message
        for source_index in list(self._voice_last_errors):
            if source_index not in seen_sources:
                del self._voice_last_errors[source_index]

        for snapshot in self._audio_controller.snapshots():
            self._handle_snapshot(snapshot, players)

    def _handle_snapshot(self, snapshot: "TranscriptEvent", players: Sequence["Player"]) -> None:
        state = self._snapshot_word_state(snapshot)
        if not state:
            return

        words, norm_words, new_start = state
        if new_start >= len(words):
            return

        label = snapshot.source or self._source_labels.get(snapshot.source_index, f"source-{snapshot.source_index}")
        if self._shared_source_index is not None and snapshot.source_index == self._shared_source_index:
            for idx, player in enumerate(players):
                self._process_live_transcript(idx, player, words, norm_words, new_start, label, players)
            return

        player_idx = self._source_to_player.get(snapshot.source_index)
        if player_idx is None or player_idx >= len(players):
            return

        self._process_live_transcript(player_idx, players[player_idx], words, norm_words, new_start, label, players)

    def _snapshot_word_state(
        self, snapshot: "TranscriptEvent"
    ) -> Optional[tuple[list[str], list[str], int]]:
        """Return words, normalized words, and prefix length shared with previous snapshot."""

        if not snapshot.text:
            return None

        words = snapshot.text.split()
        norm_words = [w.strip(".,!?;:\"'`").lower() for w in words]
        prev_seq, prev_words, prev_stage, prev_norm = self._live_word_cache.get(snapshot.source_index, (-1, [], "", []))

        if (
            snapshot.sequence < prev_seq
            or len(words) < len(prev_words)
            or (prev_stage == "final" and snapshot.stage == "partial")
        ):
            prev_norm = []

        common_prefix = 0
        while common_prefix < len(prev_norm) and common_prefix < len(norm_words):
            if prev_norm[common_prefix] != norm_words[common_prefix]:
                break
            common_prefix += 1

        self._live_word_cache[snapshot.source_index] = (snapshot.sequence, words, snapshot.stage, norm_words)
        return words, norm_words, common_prefix

    def _process_live_transcript(
        self,
        player_idx: int,
        player: "Player",
        words: list[str],
        norm_words: list[str],
        new_start: int,
        source: str,
        players: Sequence["Player"],
    ) -> None:
        found_spells = self._match_live_voice_commands(norm_words, new_start, player)
        if not found_spells:
            return

        transcript = " ".join(words).strip()
        print(f"[voice:{source}] new commands: {found_spells} (from '{transcript}')")
        self._enqueue_voice_spells(
            found_spells,
            player_idx,
            source,
            players,
        )

    def _match_live_voice_commands(
        self,
        norm_words: list[str],
        new_start: int,
        player: "Player",
    ) -> list[str]:
        """Return spells whose voice triggers overlap the newly added words."""

        caster = getattr(player, "spellcaster", None)
        if not caster:
            return []

        matches: list[str] = []
        seen: set[str] = set()
        for definition in getattr(caster, "definitions", []):
            triggers = getattr(definition, "voice_triggers", ()) or ()
            for trigger in triggers:
                tokens = [token for token in trigger.lower().split() if token]
                if not tokens:
                    continue
                span = len(tokens)
                for idx in range(0, len(norm_words) - span + 1):
                    if norm_words[idx : idx + span] != tokens:
                        continue
                    if idx + span <= new_start:
                        continue  # match does not include any newly added words
                    if definition.name in seen:
                        break
                    matches.append(definition.name)
                    seen.add(definition.name)
                    break
        return matches

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

        definition = player.get_spell_definition(request.spell_name)
        if not definition:
            self._remove_request(request)
            return False

        reason_message = ""
        cooldown = player.spell_cooldown(definition.name)
        if cooldown > 0:
            reason_message = f"[voice] cannot cast {definition.name} (cooldown {cooldown:.2f}s)"
        elif not player.can_spend_mana(definition.stats.cost):
            reason_message = (
                f"[voice] cannot cast {definition.name} (mana {player.mana:.1f}/{definition.stats.cost:.1f})"
            )

        if reason_message:
            if reason_message != request.last_reason:
                print(reason_message)
                request.last_reason = reason_message
            self._remove_request(request)
            return False

        if player.cast_spell_by_name(request.spell_name, spell_manager):
            print(f"[voice] cast spell: {request.spell_name}")
            self._remove_request(request)
            return True

        self._remove_request(request)
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
