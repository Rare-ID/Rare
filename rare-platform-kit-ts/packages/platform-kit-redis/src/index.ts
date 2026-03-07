import type Redis from "ioredis";

import type {
  AuthChallenge,
  ChallengeStore,
  PlatformSession,
  ReplayStore,
  SessionStore,
} from "@rare-id/platform-kit-web";

function ttlSeconds(expiresAt: number): number {
  const now = Math.floor(Date.now() / 1000);
  return Math.max(1, expiresAt - now);
}

export class RedisChallengeStore implements ChallengeStore {
  constructor(
    private readonly redis: Redis,
    private readonly prefix = "rare:challenge",
  ) {}

  async set(challenge: AuthChallenge): Promise<void> {
    await this.redis.set(
      `${this.prefix}:${challenge.nonce}`,
      JSON.stringify(challenge),
      "EX",
      ttlSeconds(challenge.expiresAt),
    );
  }

  async consume(nonce: string): Promise<AuthChallenge | null> {
    const key = `${this.prefix}:${nonce}`;
    const payload = await this.redis.get(key);
    if (!payload) {
      return null;
    }
    await this.redis.del(key);
    return JSON.parse(payload) as AuthChallenge;
  }
}

export class RedisReplayStore implements ReplayStore {
  constructor(
    private readonly redis: Redis,
    private readonly prefix = "rare:replay",
  ) {}

  async has(key: string): Promise<boolean> {
    const exists = await this.redis.exists(`${this.prefix}:${key}`);
    return exists > 0;
  }

  async put(key: string, expiresAt: number): Promise<void> {
    await this.redis.set(
      `${this.prefix}:${key}`,
      "1",
      "EX",
      ttlSeconds(expiresAt),
    );
  }
}

export class RedisSessionStore implements SessionStore {
  constructor(
    private readonly redis: Redis,
    private readonly prefix = "rare:session",
  ) {}

  async save(session: PlatformSession): Promise<void> {
    await this.redis.set(
      `${this.prefix}:${session.sessionToken}`,
      JSON.stringify(session),
      "EX",
      ttlSeconds(session.expiresAt),
    );
  }

  async get(sessionToken: string): Promise<PlatformSession | null> {
    const payload = await this.redis.get(`${this.prefix}:${sessionToken}`);
    if (!payload) {
      return null;
    }
    return JSON.parse(payload) as PlatformSession;
  }
}
