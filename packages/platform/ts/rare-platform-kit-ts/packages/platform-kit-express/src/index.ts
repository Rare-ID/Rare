import {
  type NextFunction,
  type Request,
  type Response,
  Router,
} from "express";

import type {
  PlatformSession,
  RarePlatformKit,
  SessionStore,
  VerifiedActionContext,
} from "@rare-id/platform-kit-web";

declare global {
  namespace Express {
    interface Request {
      rareActionContext?: VerifiedActionContext;
      rareSession?: PlatformSession;
      rareSessionToken?: string;
    }
  }
}

export interface RareSessionMiddlewareConfig {
  sessionStore: SessionStore;
  cookieName?: string;
  optional?: boolean;
}

export interface RareActionMiddlewareConfig {
  kit: RarePlatformKit;
  action?: (req: Request) => string;
  actionPayload?: (req: Request) => Record<string, unknown>;
  nonce?: (req: Request) => string;
  issuedAt?: (req: Request) => number;
  expiresAt?: (req: Request) => number;
  signatureBySession?: (req: Request) => string;
  sessionToken?: (req: Request) => string | null;
}

function detailFromError(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function statusFromError(error: unknown): number {
  const detail = detailFromError(error);
  if (
    detail.includes("Authorization") ||
    detail.includes("bearer token") ||
    detail.includes("invalid session token") ||
    detail.includes("session expired")
  ) {
    return 401;
  }
  return 400;
}

function extractBearerToken(
  authorizationHeader?: string | string[],
): string | null {
  if (typeof authorizationHeader !== "string") {
    return null;
  }
  const match = authorizationHeader.match(/^Bearer\s+(.+)$/i);
  if (!match) {
    return null;
  }
  const token = match[1]?.trim();
  return token ? token : null;
}

function readCookie(
  cookieHeader: string | string[] | undefined,
  cookieName: string,
): string | null {
  if (typeof cookieHeader !== "string") {
    return null;
  }
  for (const part of cookieHeader.split(";")) {
    const [rawName, ...rawValue] = part.split("=");
    if (rawName?.trim() !== cookieName) {
      continue;
    }
    const value = rawValue.join("=").trim();
    return value || null;
  }
  return null;
}

export function createExpressRareHandlers(kit: RarePlatformKit) {
  return {
    issueChallenge: async (req: Request, res: Response) => {
      try {
        const challenge = await kit.issueChallenge(req.body?.aud);
        res.json({
          nonce: challenge.nonce,
          aud: challenge.aud,
          issued_at: challenge.issuedAt,
          expires_at: challenge.expiresAt,
        });
      } catch (error) {
        res.status(400).json({ detail: String(error) });
      }
    },

    completeAuth: async (req: Request, res: Response) => {
      try {
        const result = await kit.completeAuth({
          nonce: req.body.nonce,
          agentId: req.body.agent_id,
          sessionPubkey: req.body.session_pubkey,
          delegationToken: req.body.delegation_token,
          signatureBySession: req.body.signature_by_session,
          publicIdentityAttestation: req.body.public_identity_attestation,
          fullIdentityAttestation: req.body.full_identity_attestation,
        });
        res.json(result);
      } catch (error) {
        res
          .status(statusFromError(error))
          .json({ detail: detailFromError(error) });
      }
    },
  };
}

export function createExpressRareRouter(
  kit: RarePlatformKit,
): ReturnType<typeof Router> {
  const router = Router();
  const handlers = createExpressRareHandlers(kit);
  router.post("/auth/challenge", handlers.issueChallenge);
  router.post("/auth/complete", handlers.completeAuth);
  return router;
}

export function createRareSessionMiddleware(
  config: RareSessionMiddlewareConfig,
) {
  const cookieName = config.cookieName ?? "rare_session";

  return async (req: Request, res: Response, next: NextFunction) => {
    try {
      const sessionToken =
        extractBearerToken(req.headers.authorization) ??
        readCookie(req.headers.cookie, cookieName);
      const session = sessionToken
        ? await config.sessionStore.get(sessionToken)
        : null;
      if (!session) {
        if (config.optional) {
          next();
          return;
        }
        res.status(401).json({ detail: "invalid session token" });
        return;
      }

      req.rareSession = session;
      req.rareSessionToken = sessionToken ?? session.sessionToken;
      next();
    } catch (error) {
      res
        .status(statusFromError(error))
        .json({ detail: detailFromError(error) });
    }
  };
}

export function createRareActionMiddleware(config: RareActionMiddlewareConfig) {
  return async (req: Request, res: Response, next: NextFunction) => {
    try {
      const sessionToken =
        config.sessionToken?.(req) ??
        extractBearerToken(req.headers.authorization) ??
        req.rareSessionToken ??
        null;
      if (!sessionToken) {
        res.status(401).json({ detail: "missing Authorization header" });
        return;
      }

      const verified = await config.kit.verifyAction({
        sessionToken,
        action: config.action?.(req) ?? String(req.body?.action ?? "request"),
        actionPayload:
          config.actionPayload?.(req) ??
          ((req.body?.action_payload ?? {}) as Record<string, unknown>),
        nonce: config.nonce?.(req) ?? String(req.body?.nonce ?? ""),
        issuedAt: config.issuedAt?.(req) ?? Number(req.body?.issued_at ?? 0),
        expiresAt: config.expiresAt?.(req) ?? Number(req.body?.expires_at ?? 0),
        signatureBySession:
          config.signatureBySession?.(req) ??
          String(req.body?.signature_by_session ?? ""),
      });
      req.rareActionContext = verified;
      next();
    } catch (error) {
      res
        .status(statusFromError(error))
        .json({ detail: detailFromError(error) });
    }
  };
}
