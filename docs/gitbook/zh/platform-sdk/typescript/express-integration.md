# Express 集成

`@rare-id/platform-kit-express` 提供 Rare 登录所需的路由和中间件。

## 挂载 Rare 路由

```ts
import express from "express";
import { createExpressRareRouter } from "@rare-id/platform-kit-express";

app.use("/rare", createExpressRareRouter(rare));
```

这会创建：

- `POST /rare/auth/challenge`
- `POST /rare/auth/complete`

## 会话中间件

```ts
import { createRareSessionMiddleware } from "@rare-id/platform-kit-express";

app.get("/me", createRareSessionMiddleware({ sessionStore }), (req, res) => {
  res.json({
    agent_id: req.rareSession?.agentId,
    level: req.rareSession?.effectiveLevel,
  });
});
```

## 委托动作校验

```ts
import { createRareActionMiddleware } from "@rare-id/platform-kit-express";
```

把它挂到需要 Agent 用会话密钥签名的写接口上。

