# WizardFlight Copilot Instructions
## Overview
- Multi-player wizard dogfight built on pygame (see `game/flying_demo.py`); the main loop wires `Player`, `SpellManager`, `PoseControlSystem`, `VoiceCommandManager`, and `CustomSpellCreator`, so edits often touch several systems.
- `game/player.py` owns movement, mana/health, status effects, and a `SpellCaster`; always route manual or voice casts through `SpellCaster.handle_input`/`cast_spell_by_name` to keep cooldown + mana enforcement centralized.
- Spells are declared via `SpellDefinition` factories under `game/spell_system`; runtime instances live in `SpellManager`, which updates/draws them each frame.
## Input & Control Systems
- Keyboard layouts live in `controller/controls.py`; reuse `ControlScheme.wasd()` / `.arrow_keys()` instead of scattering pygame constants.
- `PoseControlSystem` wraps the Mediapipe `DualPoseController`; it injects overrides via `PoseKeyState`, so build new pose gestures by mapping to ControlScheme keys rather than mutating `Player` directly.
- `pose_detection/pose_input_test.py` is the quickest way to debug camera posture—run `python -m controller.pose_detection.pose_input_test [--dual]` from `WizardFlight/` to visualize overlays before touching gameplay code.
- Voice commands route through `VoiceCommandManager`; never mutably cast from transcript code without queuing `VoiceSpellRequest`s so cooldown/mana and logging stay in sync.
## Voice & Audio Workflow
- `audio_input.AudioListener` streams microphones to AssemblyAI; export `ASSEMBLYAI_API_KEY` before running or it falls back to a placeholder key that should not ship.
- `interactive_configure_microphones` supports dual-device or stereo-split setups; mappings key off player display names, so keep `Player.name` stable.
- Validate input hardware with `python -m controller.voice_detection.audio_input_test --list-devices` (plus `--device-index`, `--channel-mapping`) before launching pygame.
- `test/micTest.py` prints live RMS per mic/stereo channel—ideal for confirming gain/device indexes on macOS.
- `VoiceCommandManager.process_audio` only consumes `TranscriptEvent.stage == "final"`; extend that flow if you need partial-phrase reactions instead of reading `listener.command` directly.
## Spells & Custom Content
- Default spells live in `spell_system/spellbook.py`; prefer `BaseSpell` + behavior factories (`TargetMovementBehavior`, `BoundsBehavior`, `CollisionBehavior`, etc.) so collision/targeting stays consistent.
- On-hit logic belongs in `spell_system/effects.py` and should use `Player` helpers (`apply_damage`, `heal`, `add_status`, `apply_knockback`) so HUD + status bars remain accurate.
- `CustomSpellCreator` (game start) calls `image_gen.generate_pixel_art_spell_icon` and `spellbook.generate_parameters`; keep the `assets/custom_spells/` directory organized because `SpriteSpellVisual` resolves sprites relative to cwd first.
- Always populate `SpellDefinition.voice_triggers`; `SpellCaster.match_voice_commands` lowercases transcripts and dedupes keywords, so supply concise trigger phrases.
## External Services
- AssemblyAI streaming depends on `sounddevice`/PyAudio; on macOS install PortAudio (`brew install portaudio`) before `pip install sounddevice` or device enumeration will fail.
- `game/image_gen.py` currently embeds a DashScope key; prefer reading `DASHSCOPE_API_KEY` (or similar) from the environment before committing.
- `spellbook.generate_parameters` uses `google.genai.Client`; ensure `GOOGLE_API_KEY` (or application default credentials) exists or the client call will raise.
- `PoseControlSystem` needs camera access; grant Terminal (or VS Code) camera permission on macOS or `DualPoseController.available` remains False.
## Running & Debugging
- Activate the venv, then launch with `python -m game.flying_demo [--disable-pose]`; `ESC` quits and `R` restarts once a round ends.
- For rapid iteration set `use_pose_input=False` (or pass `--disable-pose`) to avoid waiting on Mediapipe hardware.
- Watch the `[voice:*]` logs emitted from `VoiceCommandManager` inside the game loop—they surface microphone errors, matched keywords, and cooldown waits when diagnosing spell casts.
- `SpellManager` lacks spatial partitioning; keep spell counts modest or batch expensive visuals to avoid frame drops.
- `Player.update` expects `dt` seconds from `pygame.time.Clock.tick`; when unit testing, stub the clock to feed deterministic `dt`.
## Testing & Utilities
- No automated test suite exists; rely on manual testers: `test/whisperTest.py` (AssemblyAI), `test/micTest.py` (device gain), `test/image_gen_test/test.py` (icon download), and the pose/audio CLI tools before merging hardware-facing changes.
- Keep `Todo.md` synchronized with any new systems so other contributors know the current roadmap.
