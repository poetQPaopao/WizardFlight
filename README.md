# WizardFlight

A multi-player wizard dogfight game controlled by voice, pose, and keyboard inputs. Players cast spells using voice commands and control their wizard's movement using body gestures or keyboard controls.

## Features

- **Voice Casting**: Cast spells by shouting their names (e.g., "Fireball", "Freeze").
- **Pose Control**: Control your character's movement by tilting your head or body (requires webcam).
- **Custom Spells**: Generate unique pixel-art spell icons and stats using AI.
- **Multiplayer**: Local multiplayer support.

## Installation

### Prerequisites

- Python 3.9 or higher
- A working microphone
- A webcam (optional, for pose control)

### 1. Install System Dependencies

**macOS:**
You need to install PortAudio for the audio library to work correctly.
```bash
brew install portaudio
```

### 2. Install Python Dependencies

Navigate to the project root and install the required packages:

```bash
pip install -r requirements.txt
```

## Configuration

This game relies on several AI services. You need to set up API keys as environment variables for the full experience.

### Required API Keys

| Variable Name | Service | Purpose |
|--------------|---------|---------|
| `DASHSCOPE_API_KEY` | [Aliyun DashScope](https://dashscope.aliyun.com/) | Generating pixel-art icons for custom spells. |
| `ASSEMBLYAI_API_KEY` | [AssemblyAI](https://www.assemblyai.com/) | Real-time voice recognition for spell casting. |
| `GOOGLE_API_KEY` | [Google Gemini](https://ai.google.dev/) | Generating spell parameters from descriptions. |

### Setting Environment Variables

#### macOS / Linux (Zsh/Bash)

**Temporary (Current Session Only):**
```bash
export DASHSCOPE_API_KEY="your_dashscope_key_here"
export ASSEMBLYAI_API_KEY="your_assemblyai_key_here"
export GOOGLE_API_KEY="your_google_key_here"
```

**Permanent:**
Add the export lines to your shell configuration file (e.g., `~/.zshrc` or `~/.bashrc`):

1. Open the config file:
   ```bash
   nano ~/.zshrc
   ```
2. Add the following lines at the end:
   ```bash
   export DASHSCOPE_API_KEY="your_dashscope_key_here"
   export ASSEMBLYAI_API_KEY="your_assemblyai_key_here"
   export GOOGLE_API_KEY="your_google_key_here"
   ```
3. Save and exit (`Ctrl+O`, `Enter`, `Ctrl+X`).
4. Reload the configuration:
   ```bash
   source ~/.zshrc
   ```

#### Windows (PowerShell)

**Temporary:**
```powershell
$env:DASHSCOPE_API_KEY="your_dashscope_key_here"
$env:ASSEMBLYAI_API_KEY="your_assemblyai_key_here"
$env:GOOGLE_API_KEY="your_google_key_here"
```

**Permanent:**
```powershell
[System.Environment]::SetEnvironmentVariable('DASHSCOPE_API_KEY', 'your_dashscope_key_here', [System.EnvironmentVariableTarget]::User)
[System.Environment]::SetEnvironmentVariable('ASSEMBLYAI_API_KEY', 'your_assemblyai_key_here', [System.EnvironmentVariableTarget]::User)
[System.Environment]::SetEnvironmentVariable('GOOGLE_API_KEY', 'your_google_key_here', [System.EnvironmentVariableTarget]::User)
```

## Running the Game

To start the game:

```bash
python -m game.flying_demo
```

### Options

- **Disable Pose Control**: If you don't have a webcam or want to use keyboard only.
  ```bash
  python -m game.flying_demo --disable-pose
  ```

## Controls

- **Movement**: 
  - **Keyboard**: WASD or Arrow Keys.
  - **Pose**: Tilt your head/body to move.
- **Casting**:
  - **Voice**: Say the spell name (e.g., "Fire Bolt", "Healing Wave").
  - **Keyboard**: Spacebar (casts the currently selected spell).
- **Game**:
  - `R`: Restart round (when game over).
  - `ESC`: Quit game.
