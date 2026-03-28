import {
  type RareApiClient,
  extractRareSignerPublicKeyB64,
} from "@rare-id/platform-kit-client";
import {
  type IdentityLevel,
  type KeyResolver,
  type RareJwk,
  type RarePlatformEventItem,
  buildActionPayload,
  buildAuthChallengePayload,
  generateNonce,
  nowTs,
  parseRareJwks,
  signPlatformEventToken,
  verifyDelegationToken,
  verifyDetached,
  verifyIdentityAttestation,
} from "@rare-id/platform-kit-core";

export type IdentityMode = "public" | "full";
export type EffectiveLevel = "L0" | "L1" | "L2";

export interface AuthChallenge {
  nonce: string;
  aud: string;
  issuedAt: number;
  expiresAt: number;
}

export interface PlatformSession {
  sessionToken: string;
  agentId: string;
  sessionPubkey: string;
  identityMode: IdentityMode;
  rawLevel: IdentityLevel;
  effectiveLevel: EffectiveLevel;
  displayName: string;
  aud: string;
  createdAt: number;
  expiresAt: number;
}

export interface AuthCompleteInput {
  nonce: string;
  agentId: string;
  sessionPubkey: string;
  delegationToken: string;
  signatureBySession: string;
  publicIdentityAttestation?: string;
  fullIdentityAttestation?: string;
}

export interface AuthCompleteResult {
  session_token: string;
  agent_id: string;
  level: EffectiveLevel;
  raw_level: IdentityLevel;
  identity_mode: IdentityMode;
  display_name: string;
  session_pubkey: string;
}

export interface VerifyActionInput {
  sessionToken: string;
  action: string;
  actionPayload: Record<string, unknown>;
  nonce: string;
  issuedAt: number;
  expiresAt: number;
  signatureBySession: string;
}

export interface VerifiedActionContext {
  session: PlatformSession;
  action: string;
  actionPayload: Record<string, unknown>;
}

export interface IngestEventsInput {
  eventToken?: string;
  platformId?: string;
  kid?: string;
  privateKeyPem?: string;
  jti?: string;
  events?: RarePlatformEventItem[];
  issuedAt?: number;
  expiresAt?: number;
}

export interface IngestEventsResult {
  eventToken: string;
  response: Record<string, unknown>;
}

export interface ChallengeStore {
  set(challenge: AuthChallenge): Promise<void>;
  consume(nonce: string): Promise<AuthChallenge | null>;
}

export interface ReplayStore {
  claim(key: string, expiresAt: number): Promise<boolean>;
}

export interface SessionStore {
  save(session: PlatformSession): Promise<void>;
  get(sessionToken: string): Promise<PlatformSession | null>;
}

export interface RarePlatformKit {
  issueChallenge(aud?: string): Promise<AuthChallenge>;
  completeAuth(input: AuthCompleteInput): Promise<AuthCompleteResult>;
  verifyAction(input: VerifyActionInput): Promise<VerifiedActionContext>;
  ingestNegativeEvents(input: IngestEventsInput): Promise<IngestEventsResult>;
}

export interface RarePlatformKitConfig {
  aud: string;
  challengeStore: ChallengeStore;
  replayStore: ReplayStore;
  sessionStore: SessionStore;
  rareApiClient?: RareApiClient;
  keyResolver?: KeyResolver;
  initialJwks?: { issuer?: string; keys?: Array<Record<string, unknown>> };
  rareSignerPublicKeyB64?: string;
  challengeTtlSeconds?: number;
  sessionTtlSeconds?: number;
  maxSignedTtlSeconds?: number;
  clockSkewSeconds?: number;
}

export function createRarePlatformKit(
  config: RarePlatformKitConfig,
): RarePlatformKit {
  const challengeTtlSeconds = config.challengeTtlSeconds ?? 120;
  const sessionTtlSeconds = config.sessionTtlSeconds ?? 3600;
  const maxSignedTtlSeconds = config.maxSignedTtlSeconds ?? 300;
  const clockSkewSeconds = config.clockSkewSeconds ?? 30;

  const keyCache: Record<string, RareJwk> = config.initialJwks
    ? parseRareJwks(config.initialJwks)
    : {};
  let rareSignerPublicKeyB64 = config.rareSignerPublicKeyB64;

  const resolveIdentityKey: KeyResolver = async (kid) => {
    if (config.keyResolver) {
      return config.keyResolver(kid);
    }
    const existing = keyCache[kid];
    if (existing) {
      return existing;
    }
    if (!config.rareApiClient) {
      return null;
    }
    const jwks = await config.rareApiClient.getJwks();
    Object.assign(keyCache, parseRareJwks(jwks));
    return keyCache[kid] ?? null;
  };

  const resolveRareSignerPublicKey = async (): Promise<string | undefined> => {
    if (rareSignerPublicKeyB64) {
      return rareSignerPublicKeyB64;
    }
    if (config.initialJwks) {
      try {
        rareSignerPublicKeyB64 = extractRareSignerPublicKeyB64(config.initialJwks);
        return rareSignerPublicKeyB64;
      } catch {
        // Fall through to remote fetch when available.
      }
    }
    if (!config.rareApiClient) {
      return undefined;
    }
    rareSignerPublicKeyB64 = await config.rareApiClient.getRareSignerPublicKeyB64();
    return rareSignerPublicKeyB64;
  };

  return {
    async issueChallenge(aud?: string): Promise<AuthChallenge> {
      const now = nowTs();
      const challenge: AuthChallenge = {
        nonce: generateNonce(18),
        aud: aud ?? config.aud,
        issuedAt: now,
        expiresAt: now + challengeTtlSeconds,
      };
      await config.challengeStore.set(challenge);
      return challenge;
    },

    async completeAuth(input: AuthCompleteInput): Promise<AuthCompleteResult> {
      const challenge = await config.challengeStore.consume(input.nonce);
      if (!challenge) {
        throw new Error("unknown challenge nonce");
      }

      const now = nowTs();
      if (challenge.expiresAt < now - clockSkewSeconds) {
        throw new Error("challenge expired");
      }

      const authPayload = buildAuthChallengePayload({
        aud: challenge.aud,
        nonce: challenge.nonce,
        issuedAt: challenge.issuedAt,
        expiresAt: challenge.expiresAt,
      });
      if (
        !verifyDetached(
          authPayload,
          input.signatureBySession,
          input.sessionPubkey,
        )
      ) {
        throw new Error("invalid session challenge signature");
      }

      const delegation = await verifyDelegationToken(input.delegationToken, {
        expectedAud: config.aud,
        requiredScope: "login",
        rareSignerPublicKeyB64: await resolveRareSignerPublicKey(),
        currentTs: now,
        clockSkewSeconds,
      });
      const delegationPayload = delegation.payload;

      const delegatedSessionPubkey = delegationPayload.session_pubkey;
      if (delegatedSessionPubkey !== input.sessionPubkey) {
        throw new Error("session pubkey mismatch");
      }

      let identityMode: IdentityMode | null = null;
      let identityPayload: Record<string, unknown> | null = null;

      if (input.fullIdentityAttestation) {
        try {
          const fullVerified = await verifyIdentityAttestation(
            input.fullIdentityAttestation,
            {
              keyResolver: resolveIdentityKey,
              expectedAud: config.aud,
              currentTs: now,
              clockSkewSeconds,
            },
          );
          identityMode = "full";
          identityPayload = fullVerified.payload;
        } catch {
          // Default SDK strategy: full preferred, then fallback to public.
        }
      }

      if (!identityPayload && input.publicIdentityAttestation) {
        const publicVerified = await verifyIdentityAttestation(
          input.publicIdentityAttestation,
          {
            keyResolver: resolveIdentityKey,
            currentTs: now,
            clockSkewSeconds,
          },
        );
        identityMode = "public";
        identityPayload = publicVerified.payload;
      }

      if (!identityPayload || !identityMode) {
        throw new Error("missing identity attestation");
      }

      const delegatedAgent = delegationPayload.agent_id;
      const identitySub = identityPayload.sub;
      if (input.agentId !== delegatedAgent || input.agentId !== identitySub) {
        throw new Error("agent identity triad mismatch");
      }

      const jti = delegationPayload.jti;
      const exp = delegationPayload.exp;
      if (typeof jti !== "string" || typeof exp !== "number") {
        throw new Error("delegation replay fields missing");
      }

      const delegationReplayKey = `delegation:${jti}`;
      if (!(await config.replayStore.claim(delegationReplayKey, exp))) {
        throw new Error("delegation token replay detected");
      }

      const rawLevel = identityPayload.lvl;
      if (rawLevel !== "L0" && rawLevel !== "L1" && rawLevel !== "L2") {
        throw new Error("unsupported identity level");
      }

      const effectiveLevel: EffectiveLevel =
        identityMode === "public" && rawLevel === "L2" ? "L1" : rawLevel;

      let displayName = "unknown";
      const claims = identityPayload.claims;
      if (claims && typeof claims === "object") {
        const profile = (claims as Record<string, unknown>).profile;
        if (profile && typeof profile === "object") {
          const maybeName = (profile as Record<string, unknown>).name;
          if (typeof maybeName === "string" && maybeName.trim()) {
            displayName = maybeName;
          }
        }
      }

      const sessionToken = generateNonce(24);
      const session: PlatformSession = {
        sessionToken,
        agentId: input.agentId,
        sessionPubkey: input.sessionPubkey,
        identityMode,
        rawLevel,
        effectiveLevel,
        displayName,
        aud: config.aud,
        createdAt: now,
        expiresAt: now + sessionTtlSeconds,
      };
      await config.sessionStore.save(session);

      return {
        session_token: session.sessionToken,
        agent_id: session.agentId,
        level: session.effectiveLevel,
        raw_level: session.rawLevel,
        identity_mode: session.identityMode,
        display_name: session.displayName,
        session_pubkey: session.sessionPubkey,
      };
    },

    async verifyAction(
      input: VerifyActionInput,
    ): Promise<VerifiedActionContext> {
      const session = await config.sessionStore.get(input.sessionToken);
      if (!session) {
        throw new Error("invalid session token");
      }

      const now = nowTs();
      if (session.expiresAt < now) {
        throw new Error("session expired");
      }

      if (input.issuedAt > now + clockSkewSeconds) {
        throw new Error("action issued_at too far in future");
      }
      if (input.expiresAt < now - clockSkewSeconds) {
        throw new Error("action expired");
      }
      if (input.expiresAt <= input.issuedAt) {
        throw new Error("action expires_at must be greater than issued_at");
      }
      if (input.expiresAt - input.issuedAt > maxSignedTtlSeconds) {
        throw new Error(
          `action ttl exceeds max ${maxSignedTtlSeconds} seconds`,
        );
      }

      const replayKey = `action:${session.sessionToken}:${input.nonce}`;
      if (!(await config.replayStore.claim(replayKey, input.expiresAt))) {
        throw new Error("action nonce already consumed");
      }

      const signingInput = buildActionPayload({
        aud: config.aud,
        sessionToken: session.sessionToken,
        action: input.action,
        actionPayload: input.actionPayload,
        nonce: input.nonce,
        issuedAt: input.issuedAt,
        expiresAt: input.expiresAt,
      });
      if (
        !verifyDetached(
          signingInput,
          input.signatureBySession,
          session.sessionPubkey,
        )
      ) {
        throw new Error("invalid action signature");
      }

      return {
        session,
        action: input.action,
        actionPayload: input.actionPayload,
      };
    },

    async ingestNegativeEvents(
      input: IngestEventsInput,
    ): Promise<IngestEventsResult> {
      if (!config.rareApiClient) {
        throw new Error("rareApiClient is required for event ingest");
      }

      let eventToken = input.eventToken;
      if (!eventToken) {
        if (
          !input.platformId ||
          !input.kid ||
          !input.privateKeyPem ||
          !input.jti ||
          !input.events
        ) {
          throw new Error("missing event signing input");
        }
        eventToken = await signPlatformEventToken({
          platformId: input.platformId,
          kid: input.kid,
          privateKeyPem: input.privateKeyPem,
          jti: input.jti,
          events: input.events,
          issuedAt: input.issuedAt,
          expiresAt: input.expiresAt,
        });
      }

      const response =
        await config.rareApiClient.ingestPlatformEvents(eventToken);
      return { eventToken, response };
    },
  };
}

export class InMemoryChallengeStore implements ChallengeStore {
  private readonly challenges = new Map<string, AuthChallenge>();

  async set(challenge: AuthChallenge): Promise<void> {
    this.challenges.set(challenge.nonce, challenge);
  }

  async consume(nonce: string): Promise<AuthChallenge | null> {
    const challenge = this.challenges.get(nonce) ?? null;
    if (challenge) {
      this.challenges.delete(nonce);
    }
    return challenge;
  }
}

export class InMemoryReplayStore implements ReplayStore {
  private readonly seen = new Map<string, number>();

  async claim(key: string, expiresAt: number): Promise<boolean> {
    this.cleanup();
    if (this.seen.has(key)) {
      return false;
    }
    this.seen.set(key, expiresAt);
    this.cleanup();
    return true;
  }

  private cleanup(): void {
    const now = nowTs();
    for (const [key, expiresAt] of this.seen.entries()) {
      if (expiresAt < now) {
        this.seen.delete(key);
      }
    }
  }
}

export class InMemorySessionStore implements SessionStore {
  private readonly sessions = new Map<string, PlatformSession>();

  async save(session: PlatformSession): Promise<void> {
    this.sessions.set(session.sessionToken, session);
  }

  async get(sessionToken: string): Promise<PlatformSession | null> {
    const session = this.sessions.get(sessionToken) ?? null;
    if (!session) {
      return null;
    }
    if (session.expiresAt < nowTs()) {
      this.sessions.delete(sessionToken);
      return null;
    }
    return session;
  }
}
