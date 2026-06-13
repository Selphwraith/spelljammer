#!/usr/bin/env python3
"""
Game Launch Pipeline
====================
Orchestrates taking a game from development to deployment with
visual feedback and human approval gates.

Usage:
    python launch_pipeline.py                          # browse to game folder in UI
    python launch_pipeline.py /path/to/game            # open with game pre-loaded
    python launch_pipeline.py C:\\Games\\spelljammer    # Windows path also works

Prerequisites:
    pip install httpx
    Add your Anthropic API key to config.json (see config.json.template)
"""
import sys
import os

# Make sure the pipeline package is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline.app import GameLaunchApp


def main() -> None:
    game_path = sys.argv[1] if len(sys.argv) > 1 else None
    app = GameLaunchApp(game_path=game_path)
    app.mainloop()


if __name__ == "__main__":
    main()
