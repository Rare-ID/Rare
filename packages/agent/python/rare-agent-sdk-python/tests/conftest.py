from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[3]

for path in (
    ROOT / "src",
    ROOT / "tests",
    WORKSPACE / "packages" / "shared" / "python" / "rare-identity-protocol-python" / "src",
    WORKSPACE / "packages" / "shared" / "python" / "rare-identity-verifier-python" / "src",
    WORKSPACE / "services" / "rare-identity-core" / "libs",
    WORKSPACE / "services" / "rare-identity-core" / "services",
):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
