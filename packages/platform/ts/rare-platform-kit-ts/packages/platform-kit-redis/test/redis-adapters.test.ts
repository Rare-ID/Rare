import { describe, expect, it } from "vitest";

import {
  RedisChallengeStore,
  RedisReplayStore,
  RedisSessionStore,
} from "../src/index";

class FakeRedis {
  private readonly kv = new Map<string, string>();

  async set(
    key: string,
    value: string,
    _mode?: string,
    _ttl?: number,
    condition?: string,
  ): Promise<"OK" | null> {
    if (condition === "NX" && this.kv.has(key)) {
      return null;
    }
    this.kv.set(key, value);
    return "OK";
  }

  async get(key: string): Promise<string | null> {
    return this.kv.get(key) ?? null;
  }

  async del(key: string): Promise<number> {
    return this.kv.delete(key) ? 1 : 0;
  }

  async getdel(key: string): Promise<string | null> {
    const value = this.kv.get(key) ?? null;
    if (value !== null) {
      this.kv.delete(key);
    }
    return value;
  }

  async eval(script: string, _numKeys: number, key: string): Promise<string | null> {
    if (!script.includes("GET") || !script.includes("DEL")) {
      throw new Error("unexpected script");
    }
    return this.getdel(key);
  }
}

describe("redis adapters", () => {
  it("stores and consumes challenge", async () => {
    const redis = new FakeRedis();
    const store = new RedisChallengeStore(redis as never);

    await store.set({
      nonce: "n1",
      aud: "platform",
      issuedAt: 1,
      expiresAt: 9999999999,
    });
    const got = await store.consume("n1");
    expect(got?.nonce).toBe("n1");
    const empty = await store.consume("n1");
    expect(empty).toBeNull();
  });

  it("claims replay keys atomically", async () => {
    const redis = new FakeRedis();
    const store = new RedisReplayStore(redis as never);

    expect(await store.claim("k1", 9999999999)).toBe(true);
    expect(await store.claim("k1", 9999999999)).toBe(false);
  });

  it("stores and reads session", async () => {
    const redis = new FakeRedis();
    const store = new RedisSessionStore(redis as never);

    await store.save({
      sessionToken: "s1",
      agentId: "a1",
      sessionPubkey: "p1",
      identityMode: "public",
      rawLevel: "L1",
      effectiveLevel: "L1",
      displayName: "neo",
      aud: "platform",
      createdAt: 1,
      expiresAt: 9999999999,
    });

    const got = await store.get("s1");
    expect(got?.agentId).toBe("a1");
  });
});
