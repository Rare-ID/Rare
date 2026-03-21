import { RareApiClient } from "@rare-id/platform-kit-client";

import type { DemoEnv } from "./config";
import {
  ensurePlatformKeys,
  loadRegisterChallenge,
  saveRegisterChallenge,
} from "./state";

export async function issueDemoRegisterChallenge(
  env: DemoEnv,
  fetchImpl?: typeof fetch,
): Promise<Record<string, unknown>> {
  const client = new RareApiClient({
    rareBaseUrl: env.rareBaseUrl,
    fetchImpl,
  });
  const keys = await ensurePlatformKeys(env);
  const response = await client.issuePlatformRegisterChallenge({
    platform_aud: env.platformAud,
    domain: env.platformDomain,
  });
  await saveRegisterChallenge(env, {
    challenge_id: response.challenge_id,
    txt_name: response.txt_name,
    txt_value: response.txt_value,
    expires_at: response.expires_at,
    platform_id: env.platformId,
    platform_aud: env.platformAud,
    domain: env.platformDomain,
    key_id: keys.kid,
    public_key: keys.public_key,
    created_at: Math.floor(Date.now() / 1000),
  });
  return {
    ...response,
    platform_id: env.platformId,
    platform_aud: env.platformAud,
    domain: env.platformDomain,
    key_id: keys.kid,
    public_key: keys.public_key,
  };
}

export async function completeDemoRegister(
  env: DemoEnv,
  fetchImpl?: typeof fetch,
): Promise<Record<string, unknown>> {
  const client = new RareApiClient({
    rareBaseUrl: env.rareBaseUrl,
    fetchImpl,
  });
  const challenge = await loadRegisterChallenge(env);
  if (!challenge) {
    throw new Error(
      "missing saved platform register challenge; run demo:register:challenge first",
    );
  }
  if (challenge.platform_id !== env.platformId) {
    throw new Error("PLATFORM_ID does not match saved register challenge");
  }
  if (challenge.platform_aud !== env.platformAud) {
    throw new Error("PLATFORM_AUD does not match saved register challenge");
  }
  if (challenge.domain !== env.platformDomain) {
    throw new Error("PLATFORM_DOMAIN does not match saved register challenge");
  }

  const keys = await ensurePlatformKeys(env);
  const response = await client.completePlatformRegister({
    challenge_id: challenge.challenge_id,
    platform_id: env.platformId,
    platform_aud: env.platformAud,
    domain: env.platformDomain,
    keys: [{ kid: keys.kid, public_key: keys.public_key }],
  });
  return {
    ...response,
    key_id: keys.kid,
    public_key: keys.public_key,
  };
}
