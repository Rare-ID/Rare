import { resolve } from "node:path";

export interface DemoEnv {
  rareBaseUrl: string;
  rareSignerPublicKeyB64: string;
  platformId: string;
  platformAud: string;
  platformDomain: string;
  platformKeyId: string;
  stateDir: string;
  host: string;
  port: number;
}

function requireString(
  env: NodeJS.ProcessEnv,
  key: string,
  fallback?: string,
): string {
  const value = env[key] ?? fallback;
  if (!value || !value.trim()) {
    throw new Error(`missing required environment variable ${key}`);
  }
  return value.trim();
}

function parsePort(raw: string): number {
  const value = Number.parseInt(raw, 10);
  if (!Number.isInteger(value) || value <= 0 || value > 65535) {
    throw new Error(`invalid PLATFORM_PORT: ${raw}`);
  }
  return value;
}

export function readDemoEnv(
  env: NodeJS.ProcessEnv = process.env,
  options: { requireDomain?: boolean } = {},
): DemoEnv {
  const rareBaseUrl = requireString(
    env,
    "RARE_BASE_URL",
    "https://api.rareid.cc",
  ).replace(/\/$/, "");
  const rareSignerPublicKeyB64 = (env.RARE_SIGNER_PUBLIC_KEY_B64 ?? "").trim();
  const platformId = requireString(env, "PLATFORM_ID", "platform-demo-local");
  const platformAud = requireString(env, "PLATFORM_AUD", "platform-demo-local");
  const platformDomain = options.requireDomain
    ? requireString(env, "PLATFORM_DOMAIN")
    : (env.PLATFORM_DOMAIN ?? "").trim();
  const host = requireString(env, "PLATFORM_HOST", "127.0.0.1");
  const port = parsePort(env.PLATFORM_PORT ?? "8080");
  const stateDir = resolve(
    process.cwd(),
    env.PLATFORM_STATE_DIR ?? ".demo-state/platform-demo",
  );
  const platformKeyId = requireString(
    env,
    "PLATFORM_KEY_ID",
    `${platformId}-k1`,
  );

  return {
    rareBaseUrl,
    rareSignerPublicKeyB64,
    platformId,
    platformAud,
    platformDomain,
    platformKeyId,
    stateDir,
    host,
    port,
  };
}
