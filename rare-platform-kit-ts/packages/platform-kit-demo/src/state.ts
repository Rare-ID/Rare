import { generateKeyPairSync } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";

import type { DemoEnv } from "./config";

export interface DemoPlatformKeys {
  kid: string;
  public_key: string;
  private_key_pem: string;
  created_at: number;
}

export interface DemoRegisterChallengeState {
  challenge_id: string;
  txt_name: string;
  txt_value: string;
  expires_at: number;
  platform_id: string;
  platform_aud: string;
  domain: string;
  key_id: string;
  public_key: string;
  created_at: number;
}

function stateFile(env: DemoEnv, name: string): string {
  return join(env.stateDir, name);
}

async function ensureStateDir(env: DemoEnv): Promise<void> {
  await mkdir(env.stateDir, { recursive: true });
}

async function writeJson(path: string, value: object): Promise<void> {
  await writeFile(path, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

async function readJson<T>(path: string): Promise<T | null> {
  try {
    const raw = await readFile(path, "utf8");
    return JSON.parse(raw) as T;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") {
      return null;
    }
    throw error;
  }
}

function exportPublicKeyB64(
  publicKey: ReturnType<typeof generateKeyPairSync>["publicKey"],
): string {
  const jwk = publicKey.export({ format: "jwk" }) as Record<string, unknown>;
  const x = jwk.x;
  if (typeof x !== "string" || !x.trim()) {
    throw new Error("failed to export Ed25519 public key as JWK");
  }
  return x;
}

export async function ensurePlatformKeys(
  env: DemoEnv,
): Promise<DemoPlatformKeys> {
  await ensureStateDir(env);
  const path = stateFile(env, "platform-keys.json");
  const existing = await readJson<DemoPlatformKeys>(path);
  if (existing) {
    return existing;
  }

  const { privateKey, publicKey } = generateKeyPairSync("ed25519");
  const created: DemoPlatformKeys = {
    kid: env.platformKeyId,
    public_key: exportPublicKeyB64(publicKey),
    private_key_pem: String(
      privateKey.export({ format: "pem", type: "pkcs8" }),
    ),
    created_at: Math.floor(Date.now() / 1000),
  };
  await writeJson(path, created);
  return created;
}

export async function saveRegisterChallenge(
  env: DemoEnv,
  challenge: DemoRegisterChallengeState,
): Promise<void> {
  await ensureStateDir(env);
  await writeJson(
    stateFile(env, "platform-register-challenge.json"),
    challenge,
  );
}

export async function loadRegisterChallenge(
  env: DemoEnv,
): Promise<DemoRegisterChallengeState | null> {
  return readJson<DemoRegisterChallengeState>(
    stateFile(env, "platform-register-challenge.json"),
  );
}
