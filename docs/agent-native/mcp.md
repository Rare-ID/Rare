# MCP Auth With Rare

MCP servers can treat Rare as an agent authentication layer in front of tools. The server verifies a Rare platform session, then authorizes tool calls against the authenticated `agent_id`, `aud`, trust level, and session scope.

## Required Checks

- Challenge response includes `aud`.
- Delegation `agent_id`, auth complete `agent_id`, and identity attestation `sub` match.
- Delegation `aud`, `scope`, and `exp` are valid for this MCP server.
- Signed action input uses `rare-act-v1:{aud}:{session_token}:{action}:{payload_hash}:{nonce}:{issued_at}:{expires_at}`.
- Replay store rejects reused action nonces or session claims.

## FastAPI Pattern

```python
from fastapi import Depends, FastAPI
from rare_platform_sdk import create_fastapi_session_dependency

app = FastAPI()
require_rare_session = create_fastapi_session_dependency(session_store)

@app.post("/mcp/tools/call")
async def call_tool(session=Depends(require_rare_session)):
    agent_id = session.agent_id
    aud = session.aud
    scopes = set(session.scope)
    if "mcp:tools" not in scopes:
        return {"error": "insufficient_scope"}
    return {"ok": True, "agent_id": agent_id, "aud": aud}
```

## Express Pattern

```ts
import express from "express";
import { createRareActionMiddleware } from "@rare-id/platform-kit-express";

const app = express();

app.post(
  "/mcp/tools/call",
  createRareActionMiddleware({ kit, action: "mcp.tools.call" }),
  (req, res) => {
    res.json({ ok: true, agent_id: req.rare.agentId, aud: req.rare.aud });
  },
);
```

## Fastify Pattern

```ts
fastify.post("/mcp/tools/call", {
  preHandler: [rareActionPreHandler({ kit, action: "mcp.tools.call" })],
}, async (request) => {
  return { ok: true, agent_id: request.rare.agentId, aud: request.rare.aud };
});
```

## Nest Pattern

```ts
@UseGuards(RareActionGuard)
@Post("/mcp/tools/call")
callTool(@Req() req: RareRequest) {
  return { ok: true, agent_id: req.rare.agentId, aud: req.rare.aud };
}
```

These snippets are integration patterns. Production servers should use durable challenge, replay, and session stores.
