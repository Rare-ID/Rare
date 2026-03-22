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
    const getdel = (
      this.redis as Redis & { getdel?: (key: string) => Promise<string | null> }
    ).getdel;
    if (typeof getdel === "function") {
      const payload = await getdel.call(this.redis, key);
      return payload ? (JSON.parse(payload) as AuthChallenge) : null;
    }

    const evalResult = await (
      this.redis as Redis & {
        eval?: (
          script: string,
          numKeys: number,
          ...args: string[]
        ) => Promise<string | null>;
      }
    ).eval?.(
      "local payload = redis.call('GET', KEYS[1]); if payload then redis.call('DEL', KEYS[1]); end; return payload",
      1,
      key,
    );
    if (typeof evalResult === "string") {
      return JSON.parse(evalResult) as AuthChallenge;
    }
    return null;
  }
}

export class RedisReplayStore implements ReplayStore {
  constructor(
    private readonly redis: Redis,
    private readonly prefix = "rare:replay",
  ) {}

  async claim(key: string, expiresAt: number): Promise<boolean> {
    const result = await this.redis.set(
      `${this.prefix}:${key}`,
      "1",
      "EX",
      ttlSeconds(expiresAt),
      "NX",
    );
    return result === "OK";
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
