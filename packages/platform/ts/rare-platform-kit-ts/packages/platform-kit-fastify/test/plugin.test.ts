import Fastify from "fastify";
import { describe, expect, it, vi } from "vitest";

import { registerRarePlatformKit } from "../src/index";

describe("registerRarePlatformKit", () => {
  it("registers challenge and complete routes", async () => {
    const kit = {
      issueChallenge: vi.fn().mockResolvedValue({
        nonce: "n1",
        aud: "platform",
        issuedAt: 1,
        expiresAt: 2,
      }),
      completeAuth: vi.fn().mockResolvedValue({ ok: true }),
    };

    const app = Fastify();
    await registerRarePlatformKit(app, { kit: kit as never });

    const challenge = await app.inject({
      method: "POST",
      url: "/auth/challenge",
      payload: { aud: "platform" },
    });
    expect(challenge.statusCode).toBe(200);
    expect(challenge.json()).toEqual({
      nonce: "n1",
      aud: "platform",
      issued_at: 1,
      expires_at: 2,
    });

    const complete = await app.inject({
      method: "POST",
      url: "/auth/complete",
      payload: {
        nonce: "n",
        agent_id: "a",
        session_pubkey: "p",
        delegation_token: "d",
        signature_by_session: "s",
      },
    });
    expect(complete.statusCode).toBe(200);
    expect(complete.json()).toEqual({ ok: true });

    await app.close();
  });

  it("surfaces completion errors as 500", async () => {
    const kit = {
      issueChallenge: vi.fn(),
      completeAuth: vi.fn().mockRejectedValue(new Error("boom")),
    };

    const app = Fastify();
    await registerRarePlatformKit(app, { kit: kit as never });
    const complete = await app.inject({
      method: "POST",
      url: "/auth/complete",
      payload: {
        nonce: "n",
        agent_id: "a",
        session_pubkey: "p",
        delegation_token: "d",
        signature_by_session: "s",
      },
    });

    expect(complete.statusCode).toBe(500);
    await app.close();
  });
});
