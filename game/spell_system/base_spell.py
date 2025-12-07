from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional, Sequence

from .behaviors import BoundsBehavior, CollisionBehavior, LinearMovementBehavior, LifetimeBehavior, SpellBehavior
from .core import SpellDefinition, SpellStats
from .effects import SpellEffect
from .visuals import SpellVisual


class BaseSpell:
    """Helper for single-target spells with a shared behavior stack."""

    def __init__(
        self,
        *,
        name: str,
        stats: SpellStats,
        effect_factory: Callable[[], list[SpellEffect]],
        visual_factory: Callable[[], SpellVisual],
        behavior_factory: Optional[Callable[[], list[SpellBehavior]]] = None,
        friendly_fire: bool = False,
        voice_triggers: Optional[Sequence[str]] = None,
        sound_path: str | Path | None = None,
        sound_volume: float = 0.8,
    ) -> None:
        """Store factories and defaults that drive derived spell definitions."""

        stats.max_hits = 1
        self.name = name
        self.stats = stats
        self._effect_factory = effect_factory
        self._visual_factory = visual_factory
        self._behavior_factory = behavior_factory
        self._friendly_fire = friendly_fire
        self._voice_triggers = tuple(voice_triggers or ())
        self._sound_path = sound_path
        self._sound_volume = sound_volume

    def _build_behaviors(self) -> list[SpellBehavior]:
        """Construct default behaviors when no custom factory is provided."""

        if self._behavior_factory is not None:
            return self._behavior_factory()
        margin = self.stats.radius
        return [
            LinearMovementBehavior(),
            LifetimeBehavior(),
            BoundsBehavior(margin=margin),
            CollisionBehavior(friendly_fire=self._friendly_fire),
        ]

    def to_definition(self) -> SpellDefinition:
        """Convert the helper into a ``SpellDefinition`` instance."""

        return SpellDefinition(
            name=self.name,
            stats=self.stats,
            behavior_factory=lambda: self._build_behaviors(),
            effect_factory=self._effect_factory,
            visual_factory=self._visual_factory,
            voice_triggers=self._voice_triggers,
            sound_path=self._sound_path,
            sound_volume=self._sound_volume,
        )
