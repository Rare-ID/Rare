# Next.js App Router

## Default implementation shape

Add these pieces:

- `lib/rare.ts`
- `app/api/rare/auth/challenge/route.ts`
- `app/api/rare/auth/complete/route.ts`
- a session helper or lightweight `middleware.ts` pattern for protected routes

## Wiring rules

- Use `createRarePlatformKitFromEnv(...)` in `lib/rare.ts`
- Use shared challenge/replay/session stores from that module
- Use `createRareSessionResolver(...)` for server-side session lookup
- In `auth/complete`, set an HTTP-only session cookie as a convenience layer; bearer token remains the canonical transport

## Dependency defaults

Install:

```bash
pnpm add @rare-id/platform-kit-web
```

If the app also needs an Express server, add:

```bash
pnpm add @rare-id/platform-kit-express
```

## Guardrails

- Avoid Next middleware for authoritative session validation when the session store is in-memory; use it only as a lightweight cookie-presence gate.
- Real validation should happen in route handlers or server helpers that share the session store.
