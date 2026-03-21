import { SignJWT, exportJWK, generateKeyPair } from "jose";
import nacl from "tweetnacl";
import { describe, expect, it } from "vitest";

import {
  buildActionPayload,
  buildAuthChallengePayload,
} from "@rare-id/platform-kit-core";
import {
  InMemoryChallengeStore,
  InMemoryReplayStore,
  InMemorySessionStore,
  createRarePlatformKit,
} from "../src/index";

function b64url(bytes: Uint8Array): string {
  return Buffer.from(bytes).toString("base64url");
}

async function setupKit() {
  const [
    { privateKey: identityPriv, publicKey: identityPub },
    { privateKey: signerPriv, publicKey: signerPub },
  ] = await Promise.all([generateKeyPair("EdDSA"), generateKeyPair("EdDSA")]);

  const identityJwk = await exportJWK(identityPub);
  const signerJwk = await exportJWK(signerPub);

  const challengeStore = new InMemoryChallengeStore();
  const replayStore = new InMemoryReplayStore();
  const sessionStore = new InMemorySessionStore();

  const kit = createRarePlatformKit({
    aud: "platform",
    challengeStore,
    replayStore,
    sessionStore,
    rareSignerPublicKeyB64: String(signerJwk.x),
    keyResolver: async () => ({
      kid: "rare-k1",
      kty: "OKP",
      crv: "Ed25519",
      x: String(identityJwk.x),
    }),
  });

  return { kit, identityPriv, signerPriv };
}

async function createAuthPayload(args: {
  kit: ReturnType<typeof createRarePlatformKit>;
  signerPriv: CryptoKey;
  identityPriv: CryptoKey;
  agentId: string;
  sessionPair: nacl.SignKeyPair;
  sessionPubkey: string;
  fullAud?: string;
  delegationJti: string;
}) {
  const challenge = await args.kit.issueChallenge("platform");
  const challengeInput = buildAuthChallengePayload({
    aud: challenge.aud,
    nonce: challenge.nonce,
    issuedAt: challenge.issuedAt,
    expiresAt: challenge.expiresAt,
  });
  const signatureBySession = b64url(
    nacl.sign.detached(
      new TextEncoder().encode(challengeInput),
      args.sessionPair.secretKey,
    ),
  );

  const now = Math.floor(Date.now() / 1000);
  const delegation = await new SignJWT({
    typ: "rare.delegation",
    ver: 1,
    iss: "rare-signer",
    act: "delegated_by_rare",
    aud: "platform",
    agent_id: args.agentId,
    session_pubkey: args.sessionPubkey,
    scope: ["login"],
    iat: now,
    exp: now + 300,
    jti: args.delegationJti,
  })
    .setProtectedHeader({
      alg: "EdDSA",
      typ: "rare.delegation+jws",
      kid: "rare-signer-k1",
    })
    .sign(args.signerPriv);

  const fullWrongAud = await new SignJWT({
    typ: "rare.identity",
    ver: 1,
    iss: "rare",
    sub: args.agentId,
    lvl: "L2",
    aud: args.fullAud ?? "other-platform",
    iat: now,
    exp: now + 3600,
    jti: "id-full-1",
    claims: { profile: { name: "neo" } },
  })
    .setProtectedHeader({
      alg: "EdDSA",
      typ: "rare.identity.full+jws",
      kid: "rare-k1",
    })
    .sign(args.identityPriv);

  const publicIdentity = await new SignJWT({
    typ: "rare.identity",
    ver: 1,
    iss: "rare",
    sub: args.agentId,
    lvl: "L2",
    iat: now,
    exp: now + 3600,
    jti: "id-pub-1",
    claims: { profile: { name: "neo" } },
  })
    .setProtectedHeader({
      alg: "EdDSA",
      typ: "rare.identity.public+jws",
      kid: "rare-k1",
    })
    .sign(args.identityPriv);

  return {
    challenge,
    signatureBySession,
    delegation,
    fullWrongAud,
    publicIdentity,
  };
}

describe("RarePlatformKit", () => {
  it("consumes in-memory challenges exactly once", async () => {
    const store = new InMemoryChallengeStore();
    await store.set({
      nonce: "challenge-1",
      aud: "platform",
      issuedAt: 1,
      expiresAt: 9999999999,
    });

    expect((await store.consume("challenge-1"))?.nonce).toBe("challenge-1");
    expect(await store.consume("challenge-1")).toBeNull();
  });

  it("claims in-memory replay keys atomically", async () => {
    const store = new InMemoryReplayStore();

    expect(await store.claim("replay-1", 9999999999)).toBe(true);
    expect(await store.claim("replay-1", 9999999999)).toBe(false);
  });

  it("falls back from full to public and caps L2 to L1", async () => {
    const { kit, identityPriv, signerPriv } = await setupKit();
    const sessionPair = nacl.sign.keyPair();
    const sessionPubkey = b64url(sessionPair.publicKey);
    const agentId = "agent-test-id";

    const auth = await createAuthPayload({
      kit,
      signerPriv,
      identityPriv,
      agentId,
      sessionPair,
      sessionPubkey,
      delegationJti: "jti-1",
    });

    const result = await kit.completeAuth({
      nonce: auth.challenge.nonce,
      agentId,
      sessionPubkey,
      delegationToken: auth.delegation,
      signatureBySession: auth.signatureBySession,
      fullIdentityAttestation: auth.fullWrongAud,
      publicIdentityAttestation: auth.publicIdentity,
    });

    expect(result.identity_mode).toBe("public");
    expect(result.raw_level).toBe("L2");
    expect(result.level).toBe("L1");
    expect(result.display_name).toBe("neo");
  });

  it("rejects triad mismatch", async () => {
    const { kit, identityPriv, signerPriv } = await setupKit();
    const sessionPair = nacl.sign.keyPair();
    const sessionPubkey = b64url(sessionPair.publicKey);

    const auth = await createAuthPayload({
      kit,
      signerPriv,
      identityPriv,
      agentId: "agent-a",
      sessionPair,
      sessionPubkey,
      delegationJti: "jti-2",
    });

    await expect(
      kit.completeAuth({
        nonce: auth.challenge.nonce,
        agentId: "agent-b",
        sessionPubkey,
        delegationToken: auth.delegation,
        signatureBySession: auth.signatureBySession,
        fullIdentityAttestation: auth.fullWrongAud,
        publicIdentityAttestation: auth.publicIdentity,
      }),
    ).rejects.toThrow(/triad/i);
  });

  it("rejects delegation replay", async () => {
    const { kit, identityPriv, signerPriv } = await setupKit();
    const sessionPair = nacl.sign.keyPair();
    const sessionPubkey = b64url(sessionPair.publicKey);
    const agentId = "agent-replay";

    const auth1 = await createAuthPayload({
      kit,
      signerPriv,
      identityPriv,
      agentId,
      sessionPair,
      sessionPubkey,
      delegationJti: "jti-replay",
    });

    await kit.completeAuth({
      nonce: auth1.challenge.nonce,
      agentId,
      sessionPubkey,
      delegationToken: auth1.delegation,
      signatureBySession: auth1.signatureBySession,
      fullIdentityAttestation: auth1.fullWrongAud,
      publicIdentityAttestation: auth1.publicIdentity,
    });

    const challenge2 = await kit.issueChallenge("platform");
    const payload2 = buildAuthChallengePayload({
      aud: challenge2.aud,
      nonce: challenge2.nonce,
      issuedAt: challenge2.issuedAt,
      expiresAt: challenge2.expiresAt,
    });
    const signature2 = b64url(
      nacl.sign.detached(
        new TextEncoder().encode(payload2),
        sessionPair.secretKey,
      ),
    );

    await expect(
      kit.completeAuth({
        nonce: challenge2.nonce,
        agentId,
        sessionPubkey,
        delegationToken: auth1.delegation,
        signatureBySession: signature2,
        publicIdentityAttestation: auth1.publicIdentity,
      }),
    ).rejects.toThrow(/replay/i);
  });

  it("rejects action nonce replay", async () => {
    const { kit, identityPriv, signerPriv } = await setupKit();
    const sessionPair = nacl.sign.keyPair();
    const sessionPubkey = b64url(sessionPair.publicKey);
    const agentId = "agent-action";

    const auth = await createAuthPayload({
      kit,
      signerPriv,
      identityPriv,
      agentId,
      sessionPair,
      sessionPubkey,
      delegationJti: "jti-action",
    });

    const login = await kit.completeAuth({
      nonce: auth.challenge.nonce,
      agentId,
      sessionPubkey,
      delegationToken: auth.delegation,
      signatureBySession: auth.signatureBySession,
      publicIdentityAttestation: auth.publicIdentity,
    });

    const now = Math.floor(Date.now() / 1000);
    const actionPayload = { content: "hello" };
    const signingInput = buildActionPayload({
      aud: "platform",
      sessionToken: login.session_token,
      action: "post",
      actionPayload,
      nonce: "act-1",
      issuedAt: now,
      expiresAt: now + 120,
    });
    const actionSig = b64url(
      nacl.sign.detached(
        new TextEncoder().encode(signingInput),
        sessionPair.secretKey,
      ),
    );

    await kit.verifyAction({
      sessionToken: login.session_token,
      action: "post",
      actionPayload,
      nonce: "act-1",
      issuedAt: now,
      expiresAt: now + 120,
      signatureBySession: actionSig,
    });

    await expect(
      kit.verifyAction({
        sessionToken: login.session_token,
        action: "post",
        actionPayload,
        nonce: "act-1",
        issuedAt: now,
        expiresAt: now + 120,
        signatureBySession: actionSig,
      }),
    ).rejects.toThrow(/nonce/i);
  });
});
