import type { ExecutionContext } from "@nestjs/common";
import { describe, expect, it, vi } from "vitest";

import {
  RARE_PLATFORM_KIT,
  RareAuthGuard,
  RarePlatformKitModule,
} from "../src/index";

function buildContext(req: Record<string, unknown>): ExecutionContext {
  return {
    switchToHttp: () => ({
      getRequest: () => req,
      getResponse: () => ({}),
      getNext: () => undefined,
    }),
  } as ExecutionContext;
}

describe("RareAuthGuard", () => {
  it("returns false when bearer token is missing", async () => {
    const kit = { verifyAction: vi.fn() };
    const guard = new RareAuthGuard(kit as never);
    const allowed = await guard.canActivate(
      buildContext({ headers: {}, body: {} }),
    );
    expect(allowed).toBe(false);
    expect(kit.verifyAction).not.toHaveBeenCalled();
  });

  it("returns true when verifyAction succeeds", async () => {
    const kit = { verifyAction: vi.fn().mockResolvedValue({}) };
    const guard = new RareAuthGuard(kit as never);
    const allowed = await guard.canActivate(
      buildContext({
        headers: { authorization: "Bearer s1" },
        body: {
          action: "post",
          action_payload: { content: "hello" },
          nonce: "n1",
          issued_at: 1,
          expires_at: 2,
          signature_by_session: "sig",
        },
      }),
    );
    expect(allowed).toBe(true);
    expect(kit.verifyAction).toHaveBeenCalledTimes(1);
  });

  it("returns false when verifyAction throws", async () => {
    const kit = {
      verifyAction: vi.fn().mockRejectedValue(new Error("denied")),
    };
    const guard = new RareAuthGuard(kit as never);
    const allowed = await guard.canActivate(
      buildContext({
        headers: { authorization: "Bearer s1" },
        body: {
          action: "post",
          action_payload: { content: "hello" },
          nonce: "n1",
          issued_at: 1,
          expires_at: 2,
          signature_by_session: "sig",
        },
      }),
    );
    expect(allowed).toBe(false);
  });
});

describe("RarePlatformKitModule", () => {
  it("exports provider definitions", () => {
    const kit = { verifyAction: vi.fn() };
    const configured = RarePlatformKitModule.forRoot(kit as never);
    expect(configured.module).toBe(RarePlatformKitModule);
    expect(configured.exports).toEqual([RARE_PLATFORM_KIT, RareAuthGuard]);
    expect(configured.providers).toHaveLength(2);
  });
});
