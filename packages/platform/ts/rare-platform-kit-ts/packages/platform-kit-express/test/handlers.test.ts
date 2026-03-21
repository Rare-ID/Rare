import { describe, expect, it, vi } from "vitest";

import { createExpressRareHandlers } from "../src/index";

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
});
