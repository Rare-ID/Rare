# TypeScript 入门

Rare TypeScript 平台套件适合 Node.js 平台快速接入 Rare 登录。

## 安装

通用 Web 处理器：

```bash
pnpm add @rare-id/platform-kit-web
```

Express：

```bash
pnpm add @rare-id/platform-kit-web @rare-id/platform-kit-express
```

## 最小初始化

```ts
import {
  InMemoryChallengeStore,
  InMemoryReplayStore,
  InMemorySessionStore,
  createRarePlatformKitFromEnv,
  createRareSessionResolver,
} from "@rare-id/platform-kit-web";

const challengeStore = new InMemoryChallengeStore();
const replayStore = new InMemoryReplayStore();
const sessionStore = new InMemorySessionStore();

export const rare = createRarePlatformKitFromEnv({
  challengeStore,
  replayStore,
  sessionStore,
});

export const resolveRareSession = createRareSessionResolver({ sessionStore });
```

## 认证流程

签发 challenge：

```ts
const challenge = await rare.issueChallenge();
```

完成登录：

```ts
const result = await rare.completeAuth({
  nonce: body.nonce,
  agentId: body.agent_id,
  sessionPubkey: body.session_pubkey,
  delegationToken: body.delegation_token,
  signatureBySession: body.signature_by_session,
  publicIdentityAttestation: body.public_identity_attestation,
  fullIdentityAttestation: body.full_identity_attestation,
});
```

