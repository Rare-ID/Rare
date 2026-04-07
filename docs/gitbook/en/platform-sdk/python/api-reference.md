# Python API Reference

This page lists the main public entry points for `rare-platform-sdk`.

## Top-Level Exports

Core construction:

- `create_rare_platform_kit(config)`
- `create_rare_platform_kit_from_env(...)`
- `read_rare_platform_env(env=None)`
- `derive_platform_id_from_aud(aud)`

FastAPI helpers:

- `create_fastapi_rare_router(kit, prefix="")`
- `create_fastapi_rare_router_from_env(...)`
- `create_fastapi_session_dependency(session_store, ...)`
- `resolve_platform_session(...)`
- `extract_bearer_token(authorization)`

Rare API client:

- `RareApiClient`
- `ApiError`
- `RareApiClientError`

## Main Data Types

- `AuthChallenge`
- `AuthCompleteInput`
- `AuthCompleteResult`
- `PlatformSession`
- `VerifyActionInput`
- `VerifiedActionContext`
- `RarePlatformEventItem`
- `IngestEventsInput`
- `IngestEventsResult`
- `RarePlatformEnv`
- `RarePlatformKitConfig`

## Store Implementations

In-memory:

- `InMemoryChallengeStore`
- `InMemoryReplayStore`
- `InMemorySessionStore`

Redis-backed:

- `RedisChallengeStore`
- `RedisReplayStore`
- `RedisSessionStore`

## `RareApiClient`

Useful methods:

- `get_jwks()`
- `get_rare_signer_public_key_b64()`
- `issue_platform_register_challenge(...)`
- `complete_platform_register(...)`
- `ingest_platform_events(event_token)`

## Default Runtime Values

- challenge TTL: `120` seconds
- session TTL: `3600` seconds
- max signed TTL: `300` seconds
- clock skew: `30` seconds

