---
name: rare-platform-integration
description: Integrate Rare login into a platform app using the adoption-first quickstart. Use when wiring Rare into Next.js App Router, Express, FastAPI, or another Node/Python backend.
---

# Rare Platform Integration

Use this skill when the user wants Rare login added to an existing platform app.

## Default Decisions

- Default mode: `public-only`
- Default Rare base URL: `https://api.rareid.cc`
- Required env by default: `PLATFORM_AUD`
- `RARE_BASE_URL` is optional unless the target deployment is not production
- `RARE_SIGNER_PUBLIC_KEY_B64` is optional; prefer JWKS auto-discovery
- Do not start with platform registration, full attestation, or event ingest unless the user explicitly asks for full-mode

## Mode Selection

Before editing, explain the two integration modes in one short comparison and let the human choose:

- `public-only`: recommended default; fastest rollout; requires only the quickstart auth routes, session handling, and `PLATFORM_AUD`
- `full-mode`: use only when the platform explicitly needs registration, full attestation, raw `L0/L1/L2`, durable production rollout details, or event ingest

If the human does not choose, recommend `public-only` and proceed with that mode.

## Required Outcome

Unless the repo shape blocks it, finish all of these:

1. Install the Rare platform dependencies for the detected stack.
2. Add Rare kit bootstrap using the stack's `fromEnv` helper.
3. Add the auth challenge route.
4. Add the auth complete route.
5. Add session storage plus a session helper or middleware.
6. Add or document the required env values.
7. Give local test steps using the Rare Agent CLI.

## Framework Routing

- Next.js App Router: read [references/nextjs-app-router.md](./references/nextjs-app-router.md)
- Express: read [references/express.md](./references/express.md)
- FastAPI: read [references/fastapi.md](./references/fastapi.md)
- Other Python services: read [references/python-generic.md](./references/python-generic.md)

## Interaction Rules

- Detect the app framework from the repo before editing.
- Start by telling the human which framework was detected and present the two Rare integration modes.
- Prefer the adoption-first helpers over raw `createRarePlatformKit(...)` wiring:
  - TypeScript: `createRarePlatformKitFromEnv(...)`
  - Python: `create_rare_platform_kit_from_env(...)`
- If the human selects `public-only`, implement it directly.
- If the human selects `full-mode`, explain that the first step is still the quickstart auth routes, then extend toward registration and production wiring.
- If the human does not select a mode, keep the initial integration public-only even if the SDK supports full-mode.
- Preserve protocol red lines: replay protection, triad consistency, identity token verification, delegation token verification.
- For local-only demos, in-memory stores are acceptable. For production codepaths, call out that durable stores are required.

## Resource Map

- Env and mode defaults: [references/env-and-modes.md](./references/env-and-modes.md)
- Next.js App Router steps: [references/nextjs-app-router.md](./references/nextjs-app-router.md)
- Express steps: [references/express.md](./references/express.md)
- FastAPI steps: [references/fastapi.md](./references/fastapi.md)
- Generic Python fallback: [references/python-generic.md](./references/python-generic.md)
- Local validation flow: [references/test-flow.md](./references/test-flow.md)
