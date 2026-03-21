import { describe, expect, it } from "vitest";

import { RareApiClient } from "../src/index";

describe("RareApiClient", () => {
  it("sends expected request for platform register challenge", async () => {
    let capturedUrl = "";
    let capturedMethod = "";
    let capturedBody = "";
    const fetchImpl: typeof fetch = (async (input, init) => {
      capturedUrl = String(input);
      capturedMethod = String(init?.method ?? "GET");
      capturedBody = String(init?.body ?? "");
      return new Response(
        JSON.stringify({
          challenge_id: "c1",
          txt_name: "_rare.example.com",
          txt_value: "proof",
          expires_at: 123,
        }),
        { status: 200 },
      );
    }) as typeof fetch;

    const client = new RareApiClient({
      rareBaseUrl: "https://rare.example",
      fetchImpl,
    });

    const response = await client.issuePlatformRegisterChallenge({
      platform_aud: "platform",
      domain: "example.com",
    });

    expect(capturedUrl).toBe(
      "https://rare.example/v1/platforms/register/challenge",
    );
    expect(capturedMethod).toBe("POST");
    expect(JSON.parse(capturedBody)).toEqual({
      platform_aud: "platform",
      domain: "example.com",
    });
    expect(response.challenge_id).toBe("c1");
  });

  it("throws rich error for non-2xx responses", async () => {
    const fetchImpl: typeof fetch = (async () => {
      return new Response(JSON.stringify({ detail: "bad request" }), {
        status: 400,
      });
    }) as typeof fetch;

    const client = new RareApiClient({
      rareBaseUrl: "https://rare.example",
      fetchImpl,
    });

    await expect(client.getJwks()).rejects.toThrow(
      "rare api error 400: bad request",
    );
  });
});
