from __future__ import annotations

from fastapi import FastAPI

from apps.runtime import create_runtime


rare_service, platform_service, rare_app, platform_app = create_runtime()

app = FastAPI(title="Rare + Third-party Platform", version="0.1.0")
app.mount("/rare", rare_app)
app.mount("/platform", platform_app)
