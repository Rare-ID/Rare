---
name: rare-platform-integration
description: Integrate Rare login into Next.js App Router, Express, or FastAPI applications. Use when a user wants a coding agent to detect the app framework, explain public-only and full-mode Rare platform options, ask for the preferred integration mode, and implement the selected Rare login flow.
---

# Rare Platform Integration

Use this skill when the user wants an agent or coding assistant to wire Rare login into an application.

## Public Entry Points

- Overview: `https://www.rareid.cc/guide/platform`
- TypeScript guide: `https://www.rareid.cc/guide/platform/typescript`
- Python guide: `https://www.rareid.cc/guide/platform/python`
- Default Rare API base URL: `https://api.rareid.cc`

## Supported Frameworks

- Next.js App Router
- Express
- FastAPI

If the app uses a different framework, map the same protocol flow to that framework only after explaining the missing first-party starter support.

## Required Behavior

1. Detect whether the app is Next.js App Router, Express, or FastAPI.
2. Explain the two integration modes before editing files:
   - `public-only / quickstart`: Rare login with local verification, two auth endpoints, and a session helper or middleware.
   - `full-mode / production`: platform registration, durable stores, full attestation, and negative event ingest.
3. Recommend `public-only / quickstart` unless the user explicitly needs full-mode on day one.
4. Ask the human to choose `public-only` or `full-mode`.
5. Implement only the selected mode.
6. Preserve the app's existing routing, environment, session, and middleware conventions.
7. Add or update focused tests when the app already has a matching test setup.
8. Provide local validation steps using URL-first `rare login --public-only` and `rare platform-check` for public-only mode.

## Security Rules

Do not remove or bypass these checks:

- challenge nonce one-time use
- delegation replay protection
- identity attestation verification
- triad consistency between auth completion, delegation, and attestation subject
- full token `aud` enforcement in full-mode
- signed action verification against the delegated session key when delegated actions are added

Public-only mode still enforces replay protection, attestation verification, delegation verification, and triad consistency. It caps effective governance to `L1`.

## Environment Defaults

- Required env: `PLATFORM_AUD`
- Optional env: `RARE_BASE_URL`, defaults to `https://api.rareid.cc`
- Optional env: `RARE_SIGNER_PUBLIC_KEY_B64`; SDKs can discover the signer key from Rare JWKS when not set

## TypeScript Defaults

Use the TypeScript guide for Next.js App Router and Express:

`https://www.rareid.cc/guide/platform/typescript`

Package defaults:

- Next.js or generic Node handlers: `@rare-id/platform-kit-web`
- Express: `@rare-id/platform-kit-web` and `@rare-id/platform-kit-express`

Starter references:

- Next.js App Router starter: `packages/platform/ts/rare-platform-kit-ts/starters/nextjs-app-router`
- Express starter: `packages/platform/ts/rare-platform-kit-ts/starters/express`

## Python Defaults

Use the Python guide for FastAPI:

`https://www.rareid.cc/guide/platform/python`

Package default:

- `rare-platform-sdk`

FastAPI is the preferred Python integration path.

## Local Validation

For public-only mode, validate with:

```bash
rare register --name alice
rare login --platform-url http://127.0.0.1:<port>/rare --public-only
rare platform-check --platform-url http://127.0.0.1:<port>/rare
```

Rare-compatible challenge responses must include `aud`. The CLI uses the `aud` returned by `POST <platform-url>/auth/challenge` for the auth proof and delegated session. Add `--aud <platform_aud>` only when you want to pin an expected value and fail on mismatch.
