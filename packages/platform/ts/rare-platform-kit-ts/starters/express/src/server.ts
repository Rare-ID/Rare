import express from "express";

import {
  createExpressRareRouter,
  createRareActionMiddleware,
  createRareSessionMiddleware,
} from "@rare-id/platform-kit-express";

import { rare, sessionStore } from "./rare";

const app = express();
app.use(express.json());

app.use("/rare", createExpressRareRouter(rare));

app.get(
  "/me",
  createRareSessionMiddleware({ sessionStore }),
  (req, res) => {
    res.json({
      agent_id: req.rareSession?.agentId,
      display_name: req.rareSession?.displayName,
      identity_mode: req.rareSession?.identityMode,
      level: req.rareSession?.effectiveLevel,
    });
  },
);

app.post(
  "/posts",
  createRareActionMiddleware({
    kit: rare,
    action: () => "post",
    actionPayload: (req) => ({ content: String(req.body?.content ?? "") }),
  }),
  (req, res) => {
    res.json({
      ok: true,
      agent_id: req.rareActionContext?.session.agentId,
      content: String(req.body?.content ?? ""),
    });
  },
);

app.listen(3000);
