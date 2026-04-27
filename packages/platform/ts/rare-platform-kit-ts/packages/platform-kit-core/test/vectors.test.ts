import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { SignJWT, exportJWK, generateKeyPair } from "jose";
import { describe, expect, it } from "vitest";

import {
  buildActionPayload,
  buildAuthChallengePayload,
  verifyDelegationToken,
  verifyIdentityAttestation,
} from "../src/index";

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
      "services",
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

describe("token verification negative vectors", () => {
  it("rejects identity attestations whose sub is not an Ed25519 public key", async () => {
    const { privateKey, publicKey } = await generateKeyPair("EdDSA");
    const jwk = await exportJWK(publicKey);
    const now = Math.floor(Date.now() / 1000);
    const token = await new SignJWT({
      typ: "rare.identity",
      ver: 1,
      iss: "rare",
      sub: "not-a-pubkey",
      lvl: "L1",
      claims: { profile: { name: "alice" } },
      iat: now,
      exp: now + 300,
      jti: "id-invalid-sub",
    })
      .setProtectedHeader({
        alg: "EdDSA",
        typ: "rare.identity.public+jws",
        kid: "rare-k1",
      })
      .sign(privateKey);

    await expect(
      verifyIdentityAttestation(token, {
        keyResolver: () => ({
          kid: "rare-k1",
          kty: "OKP",
          crv: "Ed25519",
          x: String(jwk.x),
        }),
      }),
    ).rejects.toThrow("identity subject must be Ed25519 public key");
  });

  it("rejects rare-signer delegations whose agent_id is not an Ed25519 public key", async () => {
    const { privateKey, publicKey } = await generateKeyPair("EdDSA");
    const jwk = await exportJWK(publicKey);
    const session = await generateKeyPair("EdDSA");
    const sessionJwk = await exportJWK(session.publicKey);
    const now = Math.floor(Date.now() / 1000);
    const token = await new SignJWT({
      typ: "rare.delegation",
      ver: 1,
      iss: "rare-signer",
      act: "delegated_by_rare",
      agent_id: "not-a-pubkey",
      session_pubkey: String(sessionJwk.x),
      aud: "platform",
      scope: ["login"],
      iat: now,
      exp: now + 300,
      jti: "deleg-invalid-agent",
    })
      .setProtectedHeader({
        alg: "EdDSA",
        typ: "rare.delegation+jws",
        kid: "rare-signer-k1",
      })
      .sign(privateKey);

    await expect(
      verifyDelegationToken(token, {
        expectedAud: "platform",
        requiredScope: "login",
        rareSignerPublicKeyB64: String(jwk.x),
      }),
    ).rejects.toThrow("delegation agent_id must be Ed25519 public key");
  });
});
