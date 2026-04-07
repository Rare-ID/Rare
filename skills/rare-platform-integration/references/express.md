# Express

## Default implementation shape

Add these pieces:

- a Rare bootstrap module using `createRarePlatformKitFromEnv(...)`
- `app.use("/rare", createExpressRareRouter(rare))`
- `createRareSessionMiddleware(...)` for authenticated routes
- `createRareActionMiddleware(...)` for delegated signed actions

## Dependency defaults

Install:

```bash
pnpm add @rare-id/platform-kit-web @rare-id/platform-kit-express
```

## Route pattern

- `POST /rare/auth/challenge`
- `POST /rare/auth/complete`
- `GET /me` with session middleware
- protected action routes such as `POST /posts` with action middleware

## Guardrails

- Keep session transport bearer-compatible even if cookies are also used
- Do not bypass `verifyAction(...)` for delegated writes
