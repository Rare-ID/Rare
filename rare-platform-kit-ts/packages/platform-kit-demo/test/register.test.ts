import { mkdtemp } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { readDemoEnv } from "../src/config";
import {
  completeDemoRegister,
  issueDemoRegisterChallenge,
} from "../src/register";
import { ensurePlatformKeys, loadRegisterChallenge } from "../src/state";

describe("platform-kit-demo register", () => {
  it("issues and persists a platform register challenge", async () => {
    const stateDir = await mkdtemp(join(tmpdir(), "rare-demo-register-"));
    let capturedBody = "";
    const fetchImpl: typeof fetch = (async (_input, init) => {
      capturedBody = String(init?.body ?? "");
      return new Response(
        JSON.stringify({
          challenge_id: "challenge-1",
          txt_name: "_rare-challenge.demo.example.com",
          txt_value: "rare-platform-register-v1:platform-demo:challenge-1",
          expires_at: 1700000000,
        }),
        { status: 200 },
      );
    }) as typeof fetch;

    const env = readDemoEnv(
      {
        RARE_BASE_URL: "https://rare.example",
        PLATFORM_ID: "platform-demo",
        PLATFORM_AUD: "platform-demo",
        PLATFORM_DOMAIN: "demo.example.com",
        PLATFORM_STATE_DIR: stateDir,
      },
      { requireDomain: true },
    );

    const response = await issueDemoRegisterChallenge(env, fetchImpl);
    const saved = await loadRegisterChallenge(env);

    expect(JSON.parse(capturedBody)).toEqual({
      platform_aud: "platform-demo",
      domain: "demo.example.com",
    });
    expect(response).toMatchObject({
      challenge_id: "challenge-1",
      platform_id: "platform-demo",
      platform_aud: "platform-demo",
      domain: "demo.example.com",
    });
    expect(saved).toMatchObject({
      challenge_id: "challenge-1",
      platform_id: "platform-demo",
      platform_aud: "platform-demo",
      domain: "demo.example.com",
    });
  });

  it("completes platform registration with the generated demo key", async () => {
    const stateDir = await mkdtemp(join(tmpdir(), "rare-demo-register-"));
    const env = readDemoEnv(
      {
        RARE_BASE_URL: "https://rare.example",
        PLATFORM_ID: "platform-demo",
        PLATFORM_AUD: "platform-demo",
        PLATFORM_DOMAIN: "demo.example.com",
        PLATFORM_STATE_DIR: stateDir,
      },
      { requireDomain: true },
    );

    const keys = await ensurePlatformKeys(env);
    await issueDemoRegisterChallenge(
      env,
      (async () =>
        new Response(
          JSON.stringify({
            challenge_id: "challenge-2",
            txt_name: "_rare-challenge.demo.example.com",
            txt_value: "rare-platform-register-v1:platform-demo:challenge-2",
            expires_at: 1700000001,
          }),
          { status: 200 },
        )) as typeof fetch,
    );

    let capturedBody = "";
    const fetchImpl: typeof fetch = (async (_input, init) => {
      capturedBody = String(init?.body ?? "");
      return new Response(
        JSON.stringify({
          platform_id: "platform-demo",
          platform_aud: "platform-demo",
          domain: "demo.example.com",
          status: "active",
        }),
        { status: 200 },
      );
    }) as typeof fetch;

    const response = await completeDemoRegister(env, fetchImpl);

    expect(JSON.parse(capturedBody)).toEqual({
      challenge_id: "challenge-2",
      platform_id: "platform-demo",
      platform_aud: "platform-demo",
      domain: "demo.example.com",
      keys: [{ kid: keys.kid, public_key: keys.public_key }],
    });
    expect(response).toMatchObject({
      platform_id: "platform-demo",
      platform_aud: "platform-demo",
      domain: "demo.example.com",
      status: "active",
      key_id: keys.kid,
      public_key: keys.public_key,
    });
  });
});
