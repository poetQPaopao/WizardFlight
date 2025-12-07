from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Sequence, Optional

import pygame

if TYPE_CHECKING:  # pragma: no cover - typing helpers
    from player import Player
    from .behaviors import SpellBehavior
    from .effects import SpellEffect
    from .visuals import SpellVisual


_sound_cache: dict[Path, pygame.mixer.Sound] = {}
_variant_cache: dict[tuple[Path, int], list[pygame.mixer.Sound]] = {}
_mixer_ready: Optional[bool] = None


def _resolve_sound_path(raw_path: Path) -> Path | None:
    """Resolve a sound path relative to CWD or the project root."""

    if raw_path.is_absolute():
        return raw_path if raw_path.exists() else None

    # Prefer CWD (where assets/ lives when running the game)
    candidate = Path.cwd() / raw_path
    if candidate.exists():
        return candidate

    # Fallback to path relative to the repository root (../.. from this file)
    repo_root = Path(__file__).resolve().parents[2]
    candidate = repo_root / raw_path
    if candidate.exists():
        return candidate
    return None


def _ensure_mixer_initialized() -> bool:
    """Initialize pygame.mixer once and cache the result."""

    global _mixer_ready
    if _mixer_ready is True:
        return True
    if _mixer_ready is False:
        return False
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        _mixer_ready = True
    except Exception as exc:  # pragma: no cover - hardware/env specific
        print(f"[audio] Unable to initialize mixer: {exc}")
        _mixer_ready = False
    return _mixer_ready


def _load_sound(path: Path, volume: float) -> pygame.mixer.Sound | None:
    """Load and cache a sound file at the desired volume."""

    resolved = path.resolve()
    sound = _sound_cache.get(resolved)
    if sound is not None:
        sound.set_volume(volume)
        return sound
    try:
        sound = pygame.mixer.Sound(str(resolved))
        sound.set_volume(volume)
        _sound_cache[resolved] = sound
        return sound
    except Exception as exc:  # pragma: no cover - file/device issues
        print(f"[audio] Failed to load sound {resolved}: {exc}")
        return None


def play_sound_effect(path: str | Path | None, volume: float = 1.0) -> None:
    """Safely play a sound path at the requested volume."""

    if path is None:
        return
    resolved = _resolve_sound_path(Path(path))
    if not resolved or not _ensure_mixer_initialized():
        return
    clamped_volume = max(0.0, min(1.0, volume))
    sound = _load_sound(resolved, clamped_volume)
    if sound:
        sound.play()


def load_sound_variants(sound_path: str | Path | None, parts: int, base_volume: float = 1.0) -> list[pygame.mixer.Sound]:
    """Split a sound file into ``parts`` equal segments and return playable clips."""

    if not sound_path or parts <= 0:
        return []
    base_volume = max(0.0, min(1.0, base_volume))
    resolved = _resolve_sound_path(Path(sound_path))
    if not resolved or not _ensure_mixer_initialized():
        return []

    key = (resolved, parts)
    cached = _variant_cache.get(key)
    if cached:
        for sound in cached:
            sound.set_volume(base_volume)
        return cached

    base_sound = _load_sound(resolved, base_volume)
    if base_sound is None:
        return []
    try:
        sample_array = pygame.sndarray.array(base_sound)
    except Exception as exc:  # pragma: no cover - env specific
        print(f"[audio] Failed to split sound {resolved}: {exc}")
        return []

    total_samples = sample_array.shape[0]
    segments = max(1, parts)
    if total_samples <= segments:
        _variant_cache[key] = [base_sound]
        return [base_sound]

    chunk_size = total_samples // segments
    if chunk_size <= 0:
        _variant_cache[key] = [base_sound]
        return [base_sound]

    variants: list[pygame.mixer.Sound] = []
    for idx in range(segments):
        start = idx * chunk_size
        end = total_samples if idx == segments - 1 else (idx + 1) * chunk_size
        try:
            sliced = sample_array[start:end].copy()
            variant = pygame.sndarray.make_sound(sliced)
            variant.set_volume(base_volume)
            variants.append(variant)
        except Exception as exc:  # pragma: no cover - conversion issues
            print(f"[audio] Failed to build sound slice {idx} from {resolved}: {exc}")
            break

    if not variants:
        variants = [base_sound]
    _variant_cache[key] = variants
    return variants


@dataclass(slots=True)
class SpellStats:
    """Tunable values shared across every runtime instance of a spell."""

    damage: float
    speed: float
    cost: float
    radius: float
    lifetime: float
    cooldown: float
    max_hits: int = 1


@dataclass(slots=True)
class SpellContext:
    """Bundle references passed into each behavior update call."""

    spell: "Spell"
    players: Sequence[Player]
    bounds: pygame.Rect


class Spell:
    """Runtime spell instance composed of stats, behaviors, effects, and visuals."""

    def __init__(
        self,
        *,
        name: str,
        stats: SpellStats,
        caster: Player,
        position: pygame.Vector2,
        direction: pygame.Vector2,
        behaviors: list["SpellBehavior"],
        effects: list["SpellEffect"],
        visual: "SpellVisual",
    ) -> None:
        """Build a live spell with baked behaviors/effects/visuals."""

        self.name = name
        self.stats = stats
        self.caster = caster
        self.position = pygame.Vector2(position)
        self.radius = max(2.0, stats.radius)
        direction = pygame.Vector2(direction)
        if direction.length_squared() == 0:
            direction = pygame.Vector2(1, 0)
        self.velocity = direction.normalize() * stats.speed
        self.behaviors = behaviors
        self.effects = effects
        self.visual = visual
        self.alive = True
        self.age = 0.0
        self.targets_hit = 0
        self._hit_targets: set[Player] = set()
        diameter = int(self.radius * 2)
        self.rect = pygame.Rect(0, 0, diameter, diameter)
        self.sync_geometry()
        if self.visual:
            self.visual.on_spawn(self)

    def sync_geometry(self) -> None:
        """Re-center the pygame.Rect using the logical position."""

        self.rect.center = (int(self.position.x), int(self.position.y))

    def kill(self) -> None:
        """Mark the spell as dead without triggering any visual effects."""

        self.alive = False

    def update(self, dt: float, players: Sequence[Player], bounds: pygame.Rect) -> None:
        """Advance behaviors, visuals, and age tracking."""

        if not self.alive:
            return
        if dt < 0:
            dt = 0.0
        self.age += dt
        context = SpellContext(spell=self, players=players, bounds=bounds)
        for behavior in self.behaviors:
            behavior.update(context, dt)
            if not self.alive:
                break
        if self.visual and self.alive:
            self.visual.update(self, dt)

    def draw(self, surface: pygame.Surface) -> None:
        """Render either the visual helper or a fallback circle."""

        if not self.visual:
            pygame.draw.circle(surface, (255, 255, 255), self.rect.center, int(self.radius))
        else:
            self.visual.draw(surface, self)

    def apply_hit(self, target: Player) -> None:
        """Apply spell effects to a target, respecting multi-hit limits."""

        if target in self._hit_targets or not self.alive:
            return
        for effect in self.effects:
            effect.apply(self, target)
        self._hit_targets.add(target)
        self.targets_hit += 1
        if self.targets_hit >= self.stats.max_hits:
            self.kill()


@dataclass(slots=True)
class SpellDefinition:
    """Factory inputs for instantiating spells on demand."""

    name: str
    stats: SpellStats
    behavior_factory: Callable[[], list["SpellBehavior"]]
    effect_factory: Callable[[], list["SpellEffect"]]
    visual_factory: Callable[[], "SpellVisual"]
    voice_triggers: tuple[str, ...] = ()
    icon: Optional[pygame.Surface] = None
    sound_path: str | Path | None = None
    sound_volume: float = 0.8

    def __post_init__(self) -> None:
        """Normalize voice trigger keywords for consistent matching."""

        triggers: list[str] = []
        seen: set[str] = set()
        for keyword in self.voice_triggers or ():
            cleaned = keyword.strip().lower()
            if not cleaned or cleaned in seen:
                continue
            triggers.append(cleaned)
            seen.add(cleaned)
        object.__setattr__(self, "voice_triggers", tuple(triggers))
        volume = max(0.0, min(1.0, self.sound_volume))
        object.__setattr__(self, "sound_volume", volume)

        resolved_sound = None
        if self.sound_path:
            resolved_sound = _resolve_sound_path(Path(self.sound_path))
        object.__setattr__(self, "sound_path", resolved_sound)

    def create_spell(self, caster: Player, position: pygame.Vector2, direction: pygame.Vector2) -> Spell:
        """Instantiate a new ``Spell`` with fresh behaviors/effects/visuals."""

        return Spell(
            name=self.name,
            stats=self.stats,
            caster=caster,
            position=position,
            direction=direction,
            behaviors=self.behavior_factory(),
            effects=self.effect_factory(),
            visual=self.visual_factory(),
        )

    def play_sound(self) -> None:
        """Play the configured cast sound, if available."""

        play_sound_effect(self.sound_path, self.sound_volume)
