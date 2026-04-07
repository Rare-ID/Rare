# Python Platform SDK

The `rare-platform-sdk` Python package provides everything you need to integrate Rare agent identity into Python web applications, with first-class FastAPI support.

## Features

- Challenge-response authentication flow
- Local attestation and delegation verification (no network calls required)
- Replay protection with configurable stores
- Session management
- FastAPI router and dependency injection helpers
- Redis-backed stores for production deployments

## Five-Minute Path

For a first integration, start with `public-only / quickstart`:

- one required env var: `PLATFORM_AUD`
- two auth endpoints: `/auth/challenge` and `/auth/complete`
- one session dependency for protected routes

This keeps Rare's core security guarantees without pushing protocol details into application code.

## Next Steps

- [Getting Started](getting-started.md) — install and configure the SDK
- [FastAPI Integration](fastapi-integration.md) — add Rare login to a FastAPI app
- [API Reference](api-reference.md) — full types and function reference
