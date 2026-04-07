# Generic Python Fallback

If the project is Python but not FastAPI:

1. Use `create_rare_platform_kit_from_env(...)` for bootstrap.
2. Add two HTTP handlers that call:
   - `issue_challenge(...)`
   - `complete_auth(...)`
3. Add session lookup around the framework's request object by reading bearer auth first.
4. If the framework has dependency or middleware hooks, prefer those over ad hoc helper calls in every endpoint.

Do not invent framework-specific helpers that are not already in the repo. Keep the implementation minimal and explicit.
