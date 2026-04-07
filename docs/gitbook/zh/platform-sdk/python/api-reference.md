# Python API 参考

主要导出：

- `create_rare_platform_kit`
- `create_rare_platform_kit_from_env`
- `read_rare_platform_env`
- `derive_platform_id_from_aud`
- `create_fastapi_rare_router`
- `create_fastapi_rare_router_from_env`
- `create_fastapi_session_dependency`
- `resolve_platform_session`
- `extract_bearer_token`

主要类型：

- `AuthChallenge`
- `AuthCompleteInput`
- `AuthCompleteResult`
- `PlatformSession`
- `VerifyActionInput`
- `VerifiedActionContext`
- `RarePlatformEventItem`
- `IngestEventsInput`
- `RarePlatformKitConfig`

存储实现：

- `InMemoryChallengeStore`
- `InMemoryReplayStore`
- `InMemorySessionStore`
- `RedisChallengeStore`
- `RedisReplayStore`
- `RedisSessionStore`

