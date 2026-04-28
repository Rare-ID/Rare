# Platform Integration

Rare platform integration now has two tracks:

- `public-only / quickstart`: ship Rare login with local verification, two auth endpoints, and a session helper or middleware
- `full-mode / production`: add platform registration, durable stores, full attestation, and negative event ingest

Start with quickstart unless you explicitly need full-mode on day one.

## Core defaults

- Required env: `PLATFORM_AUD`
- Default Rare API base URL: `https://api.rareid.cc`
- `RARE_SIGNER_PUBLIC_KEY_B64` is optional; the SDK can discover it from Rare JWKS
- Public-only still enforces replay protection, attestation verification, delegation verification, and triad consistency

## Language guides

- TypeScript: `/guide/platform/typescript`
- Python: `/guide/platform/python`

## Starter assets

- Next.js App Router starter:
  `packages/platform/ts/rare-platform-kit-ts/starters/nextjs-app-router`
- Express starter:
  `packages/platform/ts/rare-platform-kit-ts/starters/express`

## Agent skill

For agent-driven integration work, use:

- `https://www.rareid.cc/rare-platform-integration.md`

If the agent has local skill installation support, install or map that file as
`rare-platform-integration`.
