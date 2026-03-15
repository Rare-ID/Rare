import {
  type IncomingMessage,
  type Server,
  type ServerResponse,
  createServer,
} from "node:http";

import { RareApiClient } from "@rare-id/platform-kit-client";
import type { KeyResolver } from "@rare-id/platform-kit-core";
import {
  InMemoryChallengeStore,
  InMemoryReplayStore,
  InMemorySessionStore,
  type PlatformSession,
  createRarePlatformKit,
} from "@rare-id/platform-kit-web";

export interface DemoServerConfig {
  aud?: string;
  host?: string;
  port?: number;
  rareBaseUrl?: string;
  rareApiClient?: RareApiClient;
  keyResolver?: KeyResolver;
  rareSignerPublicKeyB64?: string;
  sessionTtlSeconds?: number;
}

export interface DemoServerRuntime {
  server: Server;
  posts: Array<Record<string, unknown>>;
  comments: Array<Record<string, unknown>>;
  sessionStore: InMemorySessionStore;
  getUrl(): string;
}

function nowTs(): number {
  return Math.floor(Date.now() / 1000);
}

function sendJson(
  res: ServerResponse,
  statusCode: number,
  payload: Record<string, unknown>,
): void {
  res.statusCode = statusCode;
  res.setHeader("Content-Type", "application/json");
  res.end(`${JSON.stringify(payload)}\n`);
}

function sendError(
  res: ServerResponse,
  statusCode: number,
  detail: string,
): void {
  sendJson(res, statusCode, { detail });
}

async function readJsonBody(
  req: IncomingMessage,
): Promise<Record<string, unknown>> {
  const chunks: Buffer[] = [];
  for await (const chunk of req) {
    chunks.push(Buffer.from(chunk));
  }
  if (chunks.length === 0) {
    return {};
  }
  try {
    return JSON.parse(Buffer.concat(chunks).toString("utf8")) as Record<
      string,
      unknown
    >;
  } catch {
    throw new Error("invalid JSON request body");
  }
}

function requireString(body: Record<string, unknown>, key: string): string {
  const value = body[key];
  if (typeof value !== "string" || !value.trim()) {
    throw new Error(`missing ${key}`);
  }
  return value;
}

function requireNumber(body: Record<string, unknown>, key: string): number {
  const value = body[key];
  if (typeof value !== "number" || !Number.isInteger(value)) {
    throw new Error(`missing ${key}`);
  }
  return value;
}

function extractBearerToken(req: IncomingMessage): string {
  const authorization = req.headers.authorization;
  if (!authorization) {
    throw new Error("missing Authorization header");
  }
  if (!authorization.startsWith("Bearer ")) {
    throw new Error("invalid Authorization header");
  }
  const token = authorization.slice("Bearer ".length).trim();
  if (!token) {
    throw new Error("empty bearer token");
  }
  return token;
}

function statusForError(error: unknown): number {
  const detail = error instanceof Error ? error.message : String(error);
  if (
    detail.includes("Authorization") ||
    detail.includes("bearer token") ||
    detail.includes("invalid session token") ||
    detail.includes("session expired")
  ) {
    return 401;
  }
  if (detail.includes("post not found")) {
    return 404;
  }
  return 400;
}

async function requireSession(
  sessionStore: InMemorySessionStore,
  req: IncomingMessage,
): Promise<PlatformSession> {
  const sessionToken = extractBearerToken(req);
  const session = await sessionStore.get(sessionToken);
  if (!session) {
    throw new Error("invalid session token");
  }
  return session;
}

export function createDemoPlatformServer(
  config: DemoServerConfig = {},
): DemoServerRuntime {
  const aud = config.aud ?? "platform-demo-local";
  const host = config.host ?? "127.0.0.1";
  const port = config.port ?? 8080;
  const challengeStore = new InMemoryChallengeStore();
  const replayStore = new InMemoryReplayStore();
  const sessionStore = new InMemorySessionStore();
  const posts: Array<Record<string, unknown>> = [];
  const comments: Array<Record<string, unknown>> = [];
  const rareApiClient =
    config.rareApiClient ??
    new RareApiClient({
      rareBaseUrl: config.rareBaseUrl ?? "https://api.rareid.cc",
    });

  const kit = createRarePlatformKit({
    aud,
    rareApiClient: config.keyResolver ? undefined : rareApiClient,
    keyResolver: config.keyResolver,
    rareSignerPublicKeyB64: config.rareSignerPublicKeyB64,
    challengeStore,
    replayStore,
    sessionStore,
    sessionTtlSeconds: config.sessionTtlSeconds,
  });

  const server = createServer(async (req, res) => {
    try {
      const url = new URL(req.url ?? "/", `http://${host}:${port}`);

      if (req.method === "POST" && url.pathname === "/auth/challenge") {
        const body = await readJsonBody(req);
        const requestedAud = body.aud;
        if (requestedAud && requestedAud !== aud) {
          sendError(res, 400, "aud mismatch");
          return;
        }
        const challenge = await kit.issueChallenge(aud);
        sendJson(res, 200, {
          nonce: challenge.nonce,
          aud: challenge.aud,
          issued_at: challenge.issuedAt,
          expires_at: challenge.expiresAt,
        });
        return;
      }

      if (req.method === "POST" && url.pathname === "/auth/complete") {
        const body = await readJsonBody(req);
        const fullIdentityAttestation = requireString(
          body,
          "full_identity_attestation",
        );
        const login = await kit.completeAuth({
          nonce: requireString(body, "nonce"),
          agentId: requireString(body, "agent_id"),
          sessionPubkey: requireString(body, "session_pubkey"),
          delegationToken: requireString(body, "delegation_token"),
          signatureBySession: requireString(body, "signature_by_session"),
          fullIdentityAttestation,
        });
        if (login.identity_mode !== "full") {
          throw new Error("full identity attestation required");
        }
        sendJson(res, 200, login as unknown as Record<string, unknown>);
        return;
      }

      if (req.method === "GET" && url.pathname === "/me") {
        const session = await requireSession(sessionStore, req);
        sendJson(res, 200, {
          agent_id: session.agentId,
          identity_mode: session.identityMode,
          raw_level: session.rawLevel,
          effective_level: session.effectiveLevel,
          display_name: session.displayName,
          session_pubkey: session.sessionPubkey,
          aud: session.aud,
          created_at: session.createdAt,
          expires_at: session.expiresAt,
        });
        return;
      }

      if (req.method === "POST" && url.pathname === "/posts") {
        const body = await readJsonBody(req);
        const sessionToken = extractBearerToken(req);
        const content = requireString(body, "content");
        const verified = await kit.verifyAction({
          sessionToken,
          action: "post",
          actionPayload: { content },
          nonce: requireString(body, "nonce"),
          issuedAt: requireNumber(body, "issued_at"),
          expiresAt: requireNumber(body, "expires_at"),
          signatureBySession: requireString(body, "signature_by_session"),
        });
        const post = {
          id: `post-${posts.length + 1}`,
          agent_id: verified.session.agentId,
          display_name: verified.session.displayName,
          effective_level: verified.session.effectiveLevel,
          content,
          created_at: nowTs(),
        };
        posts.push(post);
        sendJson(res, 200, post);
        return;
      }

      if (req.method === "POST" && url.pathname === "/comments") {
        const body = await readJsonBody(req);
        const sessionToken = extractBearerToken(req);
        const postId = requireString(body, "post_id");
        const content = requireString(body, "content");
        if (!posts.find((item) => item.id === postId)) {
          sendError(res, 404, "post not found");
          return;
        }
        const verified = await kit.verifyAction({
          sessionToken,
          action: "comment",
          actionPayload: { post_id: postId, content },
          nonce: requireString(body, "nonce"),
          issuedAt: requireNumber(body, "issued_at"),
          expiresAt: requireNumber(body, "expires_at"),
          signatureBySession: requireString(body, "signature_by_session"),
        });
        const comment = {
          id: `comment-${comments.length + 1}`,
          post_id: postId,
          agent_id: verified.session.agentId,
          display_name: verified.session.displayName,
          effective_level: verified.session.effectiveLevel,
          content,
          created_at: nowTs(),
        };
        comments.push(comment);
        sendJson(res, 200, comment);
        return;
      }

      if (req.method === "GET" && url.pathname === "/feed") {
        sendJson(res, 200, { posts, comments });
        return;
      }

      sendError(res, 404, "not found");
    } catch (error) {
      sendError(
        res,
        statusForError(error),
        error instanceof Error ? error.message : String(error),
      );
    }
  });

  return {
    server,
    posts,
    comments,
    sessionStore,
    getUrl() {
      return `http://${host}:${port}`;
    },
  };
}

export async function startDemoPlatformServer(
  config: DemoServerConfig = {},
): Promise<DemoServerRuntime> {
  const runtime = createDemoPlatformServer(config);
  await new Promise<void>((resolve, reject) => {
    runtime.server.once("error", reject);
    runtime.server.listen(
      config.port ?? 8080,
      config.host ?? "127.0.0.1",
      () => {
        runtime.server.off("error", reject);
        resolve();
      },
    );
  });
  return runtime;
}
