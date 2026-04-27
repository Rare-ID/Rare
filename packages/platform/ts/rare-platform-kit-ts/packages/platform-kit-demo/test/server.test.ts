import { SignJWT, exportJWK, generateKeyPair } from "jose";
import nacl from "tweetnacl";
import { afterEach, describe, expect, it } from "vitest";

import {
  buildActionPayload,
  buildAuthChallengePayload,
} from "@rare-id/platform-kit-core";

import {
  type DemoServerRuntime,
  createDemoPlatformServer,
} from "../src/server";

function b64url(bytes: Uint8Array): string {
  return Buffer.from(bytes).toString("base64url");
}

function validAgentId(): string {
  return b64url(nacl.sign.keyPair().publicKey);
}

async function startRuntime(): Promise<{
  runtime: DemoServerRuntime;
  baseUrl: string;
  identityPriv: CryptoKey;
  signerPriv: CryptoKey;
}> {
  const [
    { privateKey: identityPriv, publicKey: identityPub },
    { privateKey: signerPriv, publicKey: signerPub },
  ] = await Promise.all([generateKeyPair("EdDSA"), generateKeyPair("EdDSA")]);
  const identityJwk = await exportJWK(identityPub);
  const signerJwk = await exportJWK(signerPub);
  const runtime = createDemoPlatformServer({
    aud: "platform-demo",
    host: "127.0.0.1",
    port: 0,
    rareSignerPublicKeyB64: String(signerJwk.x),
    keyResolver: async () => ({
      kid: "rare-k1",
      kty: "OKP",
      crv: "Ed25519",
      x: String(identityJwk.x),
    }),
  });

  await new Promise<void>((resolve, reject) => {
    runtime.server.once("error", reject);
    runtime.server.listen(0, "127.0.0.1", () => {
      runtime.server.off("error", reject);
      resolve();
    });
  });
  const address = runtime.server.address();
  if (!address || typeof address === "string") {
    throw new Error("failed to resolve test server address");
  }
  return {
    runtime,
    baseUrl: `http://127.0.0.1:${address.port}`,
    identityPriv,
    signerPriv,
  };
}

async function createFullLogin(args: {
  baseUrl: string;
  identityPriv: CryptoKey;
  signerPriv: CryptoKey;
  agentId: string;
  sessionPair: nacl.SignKeyPair;
}) {
  const challengeResponse = await fetch(`${args.baseUrl}/auth/challenge`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ aud: "platform-demo" }),
  });
  const challenge = (await challengeResponse.json()) as Record<
    string,
    number | string
  >;
  const sessionPubkey = b64url(args.sessionPair.publicKey);

  const challengeInput = buildAuthChallengePayload({
    aud: String(challenge.aud),
    nonce: String(challenge.nonce),
    issuedAt: Number(challenge.issued_at),
    expiresAt: Number(challenge.expires_at),
  });
  const signatureBySession = b64url(
    nacl.sign.detached(
      new TextEncoder().encode(challengeInput),
      args.sessionPair.secretKey,
    ),
  );

  const now = Math.floor(Date.now() / 1000);
  const delegationToken = await new SignJWT({
    typ: "rare.delegation",
    ver: 1,
    iss: "rare-signer",
    act: "delegated_by_rare",
    aud: "platform-demo",
    agent_id: args.agentId,
    session_pubkey: sessionPubkey,
    scope: ["login"],
    iat: now,
    exp: now + 300,
    jti: "delegation-jti-1",
  })
    .setProtectedHeader({
      alg: "EdDSA",
      typ: "rare.delegation+jws",
      kid: "rare-signer-k1",
    })
    .sign(args.signerPriv);

  const fullIdentityAttestation = await new SignJWT({
    typ: "rare.identity",
    ver: 1,
    iss: "rare",
    sub: args.agentId,
    lvl: "L2",
    aud: "platform-demo",
    iat: now,
    exp: now + 3600,
    jti: "identity-full-1",
    claims: { profile: { name: "neo" } },
  })
    .setProtectedHeader({
      alg: "EdDSA",
      typ: "rare.identity.full+jws",
      kid: "rare-k1",
    })
    .sign(args.identityPriv);

  const loginResponse = await fetch(`${args.baseUrl}/auth/complete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      nonce: challenge.nonce,
      agent_id: args.agentId,
      session_pubkey: sessionPubkey,
      delegation_token: delegationToken,
      signature_by_session: signatureBySession,
      full_identity_attestation: fullIdentityAttestation,
    }),
  });

  return {
    sessionPubkey,
    loginResponse,
    login: (await loginResponse.json()) as Record<string, string>,
  };
}

async function signAction(args: {
  sessionPair: nacl.SignKeyPair;
  sessionToken: string;
  action: string;
  actionPayload: Record<string, unknown>;
  nonce: string;
}) {
  const issuedAt = Math.floor(Date.now() / 1000);
  const expiresAt = issuedAt + 120;
  const signingInput = buildActionPayload({
    aud: "platform-demo",
    sessionToken: args.sessionToken,
    action: args.action,
    actionPayload: args.actionPayload,
    nonce: args.nonce,
    issuedAt,
    expiresAt,
  });
  const signature = b64url(
    nacl.sign.detached(
      new TextEncoder().encode(signingInput),
      args.sessionPair.secretKey,
    ),
  );
  return {
    nonce: args.nonce,
    issued_at: issuedAt,
    expires_at: expiresAt,
    signature_by_session: signature,
  };
}

let activeRuntime: DemoServerRuntime | null = null;

afterEach(async () => {
  if (activeRuntime) {
    await new Promise<void>((resolve, reject) => {
      activeRuntime?.server.close((error) => {
        if (error) {
          reject(error);
          return;
        }
        resolve();
      });
    });
    activeRuntime = null;
  }
});

describe("platform-kit-demo server", () => {
  it("completes full login and serves me/feed endpoints", async () => {
    const { runtime, baseUrl, identityPriv, signerPriv } = await startRuntime();
    activeRuntime = runtime;
    const sessionPair = nacl.sign.keyPair();

    const { loginResponse, login } = await createFullLogin({
      baseUrl,
      identityPriv,
      signerPriv,
      agentId: validAgentId(),
      sessionPair,
    });

    expect(loginResponse.status).toBe(200);
    expect(login.identity_mode).toBe("full");

    const meResponse = await fetch(`${baseUrl}/me`, {
      headers: { Authorization: `Bearer ${login.session_token}` },
    });
    const me = (await meResponse.json()) as Record<string, string>;
    expect(meResponse.status).toBe(200);
    expect(me.identity_mode).toBe("full");
    expect(me.effective_level).toBe("L2");

    const postSignature = await signAction({
      sessionPair,
      sessionToken: login.session_token,
      action: "post",
      actionPayload: { content: "hello world" },
      nonce: "post-nonce-1",
    });
    const postResponse = await fetch(`${baseUrl}/posts`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${login.session_token}`,
      },
      body: JSON.stringify({
        content: "hello world",
        ...postSignature,
      }),
    });
    const post = (await postResponse.json()) as Record<string, string>;
    expect(postResponse.status).toBe(200);
    expect(post.id).toBe("post-1");

    const commentSignature = await signAction({
      sessionPair,
      sessionToken: login.session_token,
      action: "comment",
      actionPayload: { post_id: "post-1", content: "first reply" },
      nonce: "comment-nonce-1",
    });
    const commentResponse = await fetch(`${baseUrl}/comments`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${login.session_token}`,
      },
      body: JSON.stringify({
        post_id: "post-1",
        content: "first reply",
        ...commentSignature,
      }),
    });
    expect(commentResponse.status).toBe(200);

    const feedResponse = await fetch(`${baseUrl}/feed`);
    const feed = (await feedResponse.json()) as {
      posts: Array<Record<string, string>>;
      comments: Array<Record<string, string>>;
    };
    expect(feedResponse.status).toBe(200);
    expect(feed.posts).toHaveLength(1);
    expect(feed.comments).toHaveLength(1);
  });

  it("rejects action nonce replay", async () => {
    const { runtime, baseUrl, identityPriv, signerPriv } = await startRuntime();
    activeRuntime = runtime;
    const sessionPair = nacl.sign.keyPair();

    const { login } = await createFullLogin({
      baseUrl,
      identityPriv,
      signerPriv,
      agentId: validAgentId(),
      sessionPair,
    });
    const postSignature = await signAction({
      sessionPair,
      sessionToken: login.session_token,
      action: "post",
      actionPayload: { content: "hello replay" },
      nonce: "replay-nonce-1",
    });

    const first = await fetch(`${baseUrl}/posts`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${login.session_token}`,
      },
      body: JSON.stringify({
        content: "hello replay",
        ...postSignature,
      }),
    });
    const second = await fetch(`${baseUrl}/posts`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${login.session_token}`,
      },
      body: JSON.stringify({
        content: "hello replay",
        ...postSignature,
      }),
    });

    expect(first.status).toBe(200);
    expect(second.status).toBe(400);
    await expect(second.json()).resolves.toMatchObject({
      detail: "action nonce already consumed",
    });
  });

  it("rejects missing and expired sessions", async () => {
    const { runtime, baseUrl, identityPriv, signerPriv } = await startRuntime();
    activeRuntime = runtime;
    const sessionPair = nacl.sign.keyPair();

    const { login } = await createFullLogin({
      baseUrl,
      identityPriv,
      signerPriv,
      agentId: validAgentId(),
      sessionPair,
    });

    const missing = await fetch(`${baseUrl}/me`);
    expect(missing.status).toBe(401);

    const existingSession = await runtime.sessionStore.get(login.session_token);
    if (!existingSession) {
      throw new Error("expected saved session");
    }
    await runtime.sessionStore.save({
      ...existingSession,
      expiresAt: 0,
    });

    const expired = await fetch(`${baseUrl}/me`, {
      headers: { Authorization: `Bearer ${login.session_token}` },
    });
    expect(expired.status).toBe(401);
  });
});
