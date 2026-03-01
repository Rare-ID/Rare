from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for rel in ("libs", "services"):
    path = ROOT / rel
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
