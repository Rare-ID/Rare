from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[3]

for path in (
    ROOT / "src",
    WORKSPACE / "packages" / "shared" / "python" / "rare-identity-protocol-python" / "src",
):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
