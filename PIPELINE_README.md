# Game Launch Pipeline 🎮

A desktop application that orchestrates taking a game from development to
deployment with visual feedback and human approval gates.

```
python launch_pipeline.py /path/to/your/game
```

---

## What it does

Four pipeline stages, each with a character avatar and status indicator:

| Stage | Avatar | What happens |
|-------|--------|-------------|
| **Dev** | 👨‍💻 | Scan game folder, confirm name & description |
| **Marketing** | 📢 | Claude generates 5 variants each of: store listing, social thread, press release, key art briefs — you pick the best |
| **Store Setup** | ⚙️ | Claude generates Itch.io JSON config, Steam config template, Google Analytics setup — you review & approve |
| **Deploy** | 🚀 | Checklist turns all green, "Ready to Deploy" button unlocks |

All approved content is saved to `game-launch/` inside your project folder.

---

## Quick Start

**1. Install dependencies**
```bash
pip install httpx
# (tkinter is bundled with Python — no extra install needed)
```

**2. Add your API key**
```bash
cp config.json.template config.json
# Edit config.json and replace sk-ant-YOUR-KEY-HERE with your real key
# OR: export ANTHROPIC_API_KEY=sk-ant-...
```

**3. Run**
```bash
python launch_pipeline.py /path/to/your/game
# e.g.:
python launch_pipeline.py C:\Games\spelljammer
python launch_pipeline.py ~/projects/my-game
python launch_pipeline.py .   # current directory
```

---

## Output Structure

After completing the pipeline, your game folder will contain:

```
game-launch/
├── marketing/
│   ├── store-listing.txt          # Itch.io store description
│   ├── social-media.txt           # Twitter/X announcement thread
│   ├── press-release.txt          # Press release snippet
│   └── key-art-descriptions.txt   # Art direction briefs
├── configs/
│   ├── itch-io-config.json        # Itch.io page configuration
│   ├── steam-config.json          # Steam Steamworks template
│   └── analytics-setup.js        # Google Analytics 4 events
└── launch-manifest.json           # Pipeline state (resume-able)
```

---

## Config file

`config.json` (copy from `config.json.template`):

```json
{
  "api_key": "sk-ant-...",
  "model": "claude-sonnet-4-6"
}
```

The app also reads `ANTHROPIC_API_KEY` from the environment if no `config.json`
is present. If neither exists, it will prompt you on first launch and save the
key for future runs.

---

## Resume / Revert

The pipeline saves state continuously to `game-launch/launch-manifest.json`.
Run the same command again to pick up where you left off:

```bash
python launch_pipeline.py /path/to/game  # resumes current stage automatically
```

To start over, delete `game-launch/launch-manifest.json`.

---

## Requirements

- Python 3.10+
- `httpx` (`pip install httpx`)
- `tkinter` (bundled with standard Python distributions)
- Anthropic API key (get one at console.anthropic.com)

---

## Tips

- **Edit variants before approving** — click ✎ Edit in any variant tab to customize the generated text
- **Approve All** in Store Setup approves all three configs at once with their current content
- **Click any completed stage** in the timeline to jump back and revise
- **Works on any game type** — HTML5, Python, Unity exports, Godot builds, etc.
