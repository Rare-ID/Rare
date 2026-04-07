# TypeScript API Reference

This page lists the main public entry points for the TypeScript platform kit.

## `@rare-id/platform-kit-web`

Core exports:

- `createRarePlatformKit(config)`
- `createRarePlatformKitFromEnv(options)`
- `createRareSessionResolver(config)`
- `readRarePlatformEnv(env?)`
- `derivePlatformIdFromAud(aud)`
- `extractBearerToken(header)`

Default stores:

- `InMemoryChallengeStore`
- `InMemoryReplayStore`
- `InMemorySessionStore`

Important interfaces:

- `AuthChallenge`
- `AuthCompleteInput`
- `AuthCompleteResult`
- `PlatformSession`
- `VerifyActionInput`
- `VerifiedActionContext`
- `IngestEventsInput`
- `IngestEventsResult`

Key methods on `RarePlatformKit`:

- `issueChallenge(aud?)`
- `completeAuth(input)`
- `verifyAction(input)`
- `ingestNegativeEvents(input)`

## `@rare-id/platform-kit-client`

Use this client for platform registration and event ingest:

- `getJwks()`
- `getRareSignerPublicKeyB64()`
- `issuePlatformRegisterChallenge(input)`
- `completePlatformRegister(input)`
- `ingestPlatformEvents(eventToken)`

Helper:

- `extractRareSignerPublicKeyB64(jwks)`

## `@rare-id/platform-kit-express`

Express helpers:

- `createExpressRareRouter(kit)`
- `createExpressRareHandlers(kit)`
- `createRareSessionMiddleware(config)`
- `createRareActionMiddleware(config)`

Injected request properties:

- `req.rareSession`
- `req.rareSessionToken`
- `req.rareActionContext`

## Other Packages

- `@rare-id/platform-kit-core`: low-level token verification and payload builders
- `@rare-id/platform-kit-fastify`: Fastify plugin
- `@rare-id/platform-kit-nest`: NestJS helpers
- `@rare-id/platform-kit-redis`: Redis-backed stores

## Config Defaults

When omitted:

- challenge TTL: `120` seconds
- session TTL: `3600` seconds
- max signed action TTL: `300` seconds
- clock skew: `30` seconds

