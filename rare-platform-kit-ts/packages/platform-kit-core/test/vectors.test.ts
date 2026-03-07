import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { buildActionPayload, buildAuthChallengePayload } from "../src/index";

describe("RIP vectors", () => {
  const candidatePaths = [
    // Split-repo friendly path (executed from package root).
    join(process.cwd(), "test", "fixtures", "rip-v1-signing-inputs.json"),
    // Monorepo fallback (executed from workspace root).
    join(
      process.cwd(),
      "packages",
      "platform-kit-core",
      "test",
      "fixtures",
      "rip-v1-signing-inputs.json",
    ),
    // Legacy monorepo layout fallback.
    join(
      process.cwd(),
      "..",
      "..",
      "..",
      "rare-identity-core",
      "docs",
      "test-vectors",
      "rip-v1-signing-inputs.json",
    ),
  ];
  const vectorPath = candidatePaths.find((p) => existsSync(p));
  if (!vectorPath) {
    throw new Error("RIP vector file not found in known locations");
  }
  const vectors = JSON.parse(readFileSync(vectorPath, "utf8"));

  it("matches challenge payload vector", () => {
    const challenge = vectors.challenge;
    const payload = buildAuthChallengePayload({
      aud: challenge.input.aud,
      nonce: challenge.input.nonce,
      issuedAt: challenge.input.issued_at,
      expiresAt: challenge.input.expires_at,
    });
    expect(payload).toBe(challenge.expected);
  });

  it("matches action payload vector", () => {
    const action = vectors.action_post;
    const payload = buildActionPayload({
      aud: action.input.aud,
      sessionToken: action.input.session_token,
      action: action.input.action,
      actionPayload: action.input.action_payload,
      nonce: action.input.nonce,
      issuedAt: action.input.issued_at,
      expiresAt: action.input.expires_at,
    });
    expect(payload).toBe(action.expected);
  });
});
