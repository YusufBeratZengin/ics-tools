"""Unit and integration tests for ics-tools."""

import sys
from pathlib import Path

# Ensure src/ is in sys.path for unittest discover without pip install
src_dir = str(Path(__file__).resolve().parent.parent / "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)
