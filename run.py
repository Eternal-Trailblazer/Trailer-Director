#!/usr/bin/env python
"""
Launcher for Autonomous Trailer Director (Gemini API mode).
Sets up paths correctly and runs CLI.
Usage: python run.py [cli args...]
       python run.py run --package ./test_episode --config ./config/default_config.yaml --output ./output
"""
import sys
import os
from pathlib import Path

# ─── PERMANENT PATH FIX ───
ROOT = Path(__file__).parent.resolve()
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))          # Make 'src' importable
os.chdir(ROOT)                         # Ensure correct working directory
# ────────────────────────────

if __name__ == "__main__":
    from src.cli import cli
    cli()
