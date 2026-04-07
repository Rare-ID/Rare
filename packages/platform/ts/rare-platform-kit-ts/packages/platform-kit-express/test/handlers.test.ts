import { describe, expect, it, vi } from "vitest";

import {
  createExpressRareHandlers,
  createRareActionMiddleware,
  createRareSessionMiddleware,
} from "../src/index";

describe("createExpressRareHandlers", () => {
  it("maps challenge response fields", async () => {
    const kit = {
      issueChallenge: vi.fn().mockResolvedValue({
        nonce: "n1",
        aud: "platform",
        issuedAt: 10,
        expiresAt: 20,
      }),
      completeAuth: vi.fn(),
    };
    const handlers = createExpressRareHandlers(kit as never);

    const json = vi.fn();
    await handlers.issueChallenge(
      { body: { aud: "platform" } } as never,
      { json, status: vi.fn() } as never,
    );

    expect(json).toHaveBeenCalledWith({
      nonce: "n1",
      aud: "platform",
      issued_at: 10,
      expires_at: 20,
    });
  });

  it("returns 400 payload when auth completion fails", async () => {
    const kit = {
      issueChallenge: vi.fn(),
      completeAuth: vi.fn().mockRejectedValue(new Error("invalid payload")),
    };
    const handlers = createExpressRareHandlers(kit as never);

    const json = vi.fn();
    const status = vi.fn().mockReturnValue({ json });
    await handlers.completeAuth(
      {
        body: {
          nonce: "n",
          agent_id: "a",
          session_pubkey: "p",
          delegation_token: "d",
          signature_by_session: "s",
        },
      } as never,
      { json, status } as never,
    );

    expect(status).toHaveBeenCalledWith(400);
    expect(json).toHaveBeenCalledTimes(1);
    expect(String(json.mock.calls[0][0].detail)).toMatch(/invalid payload/);
  });

  it("loads a session into the request", async () => {
    const middleware = createRareSessionMiddleware({
      sessionStore: {
        get: vi.fn().mockResolvedValue({
          sessionToken: "s1",
          agentId: "agent-1",
          sessionPubkey: "pub-1",
          identityMode: "public",
          rawLevel: "L1",
          effectiveLevel: "L1",
          displayName: "neo",
          aud: "platform",
          createdAt: 1,
          expiresAt: 9999999999,
        }),
        save: vi.fn(),
      },
    });

    const req = {
      headers: {
        authorization: "Bearer s1",
      },
    } as never;
    const next = vi.fn();
    await middleware(
      req,
      { status: vi.fn().mockReturnValue({ json: vi.fn() }) } as never,
      next,
    );

    expect(next).toHaveBeenCalledTimes(1);
    expect(req.rareSession.agentId).toBe("agent-1");
  });

  it("verifies delegated actions and stores the verified context", async () => {
    const middleware = createRareActionMiddleware({
      kit: {
        verifyAction: vi.fn().mockResolvedValue({
          session: { agentId: "agent-1" },
          action: "post",
          actionPayload: { content: "hello" },
        }),
      } as never,
      action: () => "post",
      actionPayload: (req) => ({ content: String(req.body?.content ?? "") }),
    });

    const req = {
      headers: {
        authorization: "Bearer s1",
      },
      body: {
        content: "hello",
        nonce: "n1",
        issued_at: 10,
        expires_at: 20,
        signature_by_session: "sig",
      },
    } as never;
    const next = vi.fn();
    await middleware(
      req,
      { status: vi.fn().mockReturnValue({ json: vi.fn() }) } as never,
      next,
    );

    expect(next).toHaveBeenCalledTimes(1);
    expect(req.rareActionContext.session.agentId).toBe("agent-1");
  });
});
