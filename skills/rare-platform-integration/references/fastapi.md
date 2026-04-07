# FastAPI

## Default implementation shape

Add these pieces:

- a Rare bootstrap module using `create_rare_platform_kit_from_env(...)`
- `app.include_router(create_fastapi_rare_router_from_env(...), prefix="/rare")`
- `create_fastapi_session_dependency(...)` for authenticated routes

## Dependency defaults

Install:

```bash
pip install rare-platform-sdk
```

## Route pattern

- `POST /rare/auth/challenge`
- `POST /rare/auth/complete`
- authenticated routes using a dependency that resolves the Rare platform session

## Guardrails

- FastAPI is the preferred Python integration path
- Keep the first pass public-only unless the user explicitly asks for full-mode
- Use in-memory stores only for local demos and single-process development
