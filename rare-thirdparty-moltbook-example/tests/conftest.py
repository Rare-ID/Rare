from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = ROOT.parent / "rare-identity-core"

for path in (
    ROOT,
    ROOT / "apps",
    CORE_ROOT / "libs",
    CORE_ROOT / "services",
):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
