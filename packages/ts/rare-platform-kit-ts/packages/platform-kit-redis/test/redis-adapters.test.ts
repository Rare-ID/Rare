import { describe, expect, it } from "vitest";

import {
  RedisChallengeStore,
  RedisReplayStore,
  RedisSessionStore,
} from "../src/index";

class FakeRedis {
  private readonly kv = new Map<string, string>();

  async set(key: string, value: string): Promise<"OK"> {
    this.kv.set(key, value);
    return "OK";
  }

  async get(key: string): Promise<string | null> {
    return this.kv.get(key) ?? null;
  }

  async del(key: string): Promise<number> {
    return this.kv.delete(key) ? 1 : 0;
  }

  async exists(key: string): Promise<number> {
    return this.kv.has(key) ? 1 : 0;
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

  it("tracks replay keys", async () => {
    const redis = new FakeRedis();
    const store = new RedisReplayStore(redis as never);

    expect(await store.has("k1")).toBe(false);
    await store.put("k1", 9999999999);
    expect(await store.has("k1")).toBe(true);
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
