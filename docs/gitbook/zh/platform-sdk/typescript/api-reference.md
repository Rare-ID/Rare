# TypeScript API 参考

## `@rare-id/platform-kit-web`

主要导出：

- `createRarePlatformKit`
- `createRarePlatformKitFromEnv`
- `createRareSessionResolver`
- `readRarePlatformEnv`
- `derivePlatformIdFromAud`
- `extractBearerToken`

默认存储实现：

- `InMemoryChallengeStore`
- `InMemoryReplayStore`
- `InMemorySessionStore`

核心类型：

- `AuthChallenge`
- `AuthCompleteInput`
- `AuthCompleteResult`
- `PlatformSession`
- `VerifyActionInput`
- `VerifiedActionContext`
- `IngestEventsInput`

## `@rare-id/platform-kit-client`

主要方法：

- `getJwks()`
- `getRareSignerPublicKeyB64()`
- `issuePlatformRegisterChallenge(...)`
- `completePlatformRegister(...)`
- `ingestPlatformEvents(...)`

## `@rare-id/platform-kit-express`

- `createExpressRareRouter`
- `createRareSessionMiddleware`
- `createRareActionMiddleware`

