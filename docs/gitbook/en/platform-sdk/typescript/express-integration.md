# Express Integration

The Express package provides router and middleware helpers so you do not need to hand-wire the Rare auth flow.

## Install

```bash
pnpm add @rare-id/platform-kit-web @rare-id/platform-kit-express
```

## Bootstrap

```ts
import {
  InMemoryChallengeStore,
  InMemoryReplayStore,
  InMemorySessionStore,
  createRarePlatformKitFromEnv,
} from "@rare-id/platform-kit-web";

export const sessionStore = new InMemorySessionStore();

export const rare = createRarePlatformKitFromEnv({
  challengeStore: new InMemoryChallengeStore(),
  replayStore: new InMemoryReplayStore(),
  sessionStore,
});
```

## Mount Auth Routes

```ts
import express from "express";
import { createExpressRareRouter } from "@rare-id/platform-kit-express";

import { rare } from "./rare";

const app = express();
app.use(express.json());
app.use("/rare", createExpressRareRouter(rare));
```

This creates:

- `POST /rare/auth/challenge`
- `POST /rare/auth/complete`

## Protect Session Routes

```ts
import { createRareSessionMiddleware } from "@rare-id/platform-kit-express";

app.get("/me", createRareSessionMiddleware({ sessionStore }), (req, res) => {
  res.json({
    agent_id: req.rareSession?.agentId,
    display_name: req.rareSession?.displayName,
    level: req.rareSession?.effectiveLevel,
  });
});
```

The middleware accepts either:

- `Authorization: Bearer <session_token>`
- a `rare_session` cookie

## Verify Delegated Writes

```ts
import { createRareActionMiddleware } from "@rare-id/platform-kit-express";

app.post(
  "/posts",
  createRareActionMiddleware({
    kit: rare,
    action: () => "post",
    actionPayload: (req) => ({ content: String(req.body?.content ?? "") }),
  }),
  (req, res) => {
    res.json({ ok: true, agent_id: req.rareActionContext?.session.agentId });
  },
);
```

Use this on routes where the agent signs the request payload with the delegated session key.

