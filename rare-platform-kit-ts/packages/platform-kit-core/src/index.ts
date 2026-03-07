import { createHash, randomBytes } from "node:crypto";
import {
  SignJWT,
  decodeJwt,
  decodeProtectedHeader,
  importJWK,
  importPKCS8,
  jwtVerify,
} from "jose";
import nacl from "tweetnacl";

export type IdentityLevel = "L0" | "L1" | "L2";

export interface VerifiedTokenResult {
  header: Record<string, unknown>;
  payload: Record<string, unknown>;
}

export interface RareJwks {
  issuer?: string;
  keys?: Array<Record<string, unknown>>;
}

export interface RareJwk {
  kid: string;
  kty: "OKP";
  crv: "Ed25519";
  x: string;
}

export type KeyResolver = (
  kid: string,
) => Promise<RareJwk | null> | RareJwk | null;

export function parseRareJwks(jwks: RareJwks): Record<string, RareJwk> {
  if (!Array.isArray(jwks.keys)) {
    throw new Error("invalid JWKS payload");
  }
  const resolved: Record<string, RareJwk> = {};
  for (const item of jwks.keys) {
    if (!item || typeof item !== "object") {
      continue;
    }
    const kid = item.kid;
    const kty = item.kty;
    const crv = item.crv;
    const x = item.x;
    if (typeof kid !== "string" || typeof x !== "string") {
      continue;
    }
    if (kty !== "OKP" || crv !== "Ed25519") {
      continue;
    }
    resolved[kid] = { kid, kty, crv, x };
  }
  return resolved;
}

export interface VerifyIdentityOptions {
  keyResolver: KeyResolver;
  expectedAud?: string;
  currentTs?: number;
  clockSkewSeconds?: number;
}

export async function verifyIdentityAttestation(
  token: string,
  options: VerifyIdentityOptions,
): Promise<VerifiedTokenResult> {
  const header = decodeProtectedHeader(token);
  const typ = header.typ;
  if (typ !== "rare.identity.public+jws" && typ !== "rare.identity.full+jws") {
    throw new Error("invalid identity token typ");
  }

  const kid = header.kid;
  if (typeof kid !== "string") {
    throw new Error("missing key id");
  }

  const resolved = await options.keyResolver(kid);
  if (!resolved) {
    throw new Error("unknown identity key id");
  }

  const key = await importJWK(
    {
      kty: "OKP",
      crv: "Ed25519",
      x: resolved.x,
    },
    "EdDSA",
  );

  const verified = await jwtVerify(token, key, {
    algorithms: ["EdDSA"],
    clockTolerance: options.clockSkewSeconds ?? 30,
  });

  const payload = verified.payload as Record<string, unknown>;
  if (payload.typ !== "rare.identity") {
    throw new Error("invalid identity payload typ");
  }
  if (payload.ver !== 1) {
    throw new Error("unsupported identity payload version");
  }
  if (payload.iss !== "rare") {
    throw new Error("invalid identity issuer");
  }

  if (typ === "rare.identity.full+jws") {
    if (!options.expectedAud) {
      throw new Error("expected_aud required for full identity token");
    }
    if (payload.aud !== options.expectedAud) {
      throw new Error("identity full token aud mismatch");
    }
  } else if (Object.prototype.hasOwnProperty.call(payload, "aud")) {
    throw new Error("public identity token must not contain aud");
  }

  const level = payload.lvl;
  if (level !== "L0" && level !== "L1" && level !== "L2") {
    throw new Error("invalid identity level");
  }

  const now = options.currentTs ?? nowTs();
  const iat = payload.iat;
  const exp = payload.exp;
  if (typeof iat !== "number" || typeof exp !== "number") {
    throw new Error("identity timestamps must be integers");
  }
  const skew = options.clockSkewSeconds ?? 30;
  if (iat - skew > now) {
    throw new Error("identity token not yet valid");
  }
  if (exp + skew < now) {
    throw new Error("identity token expired");
  }

  return { header: header as Record<string, unknown>, payload };
}

export interface VerifyDelegationOptions {
  expectedAud: string;
  requiredScope: string;
  rareSignerPublicKeyB64?: string;
  currentTs?: number;
  clockSkewSeconds?: number;
}

export async function verifyDelegationToken(
  token: string,
  options: VerifyDelegationOptions,
): Promise<VerifiedTokenResult> {
  const header = decodeProtectedHeader(token);
  if (header.typ !== "rare.delegation+jws") {
    throw new Error("invalid delegation token typ");
  }

  const payload = decodeJwt(token) as Record<string, unknown>;
  if (payload.typ !== "rare.delegation") {
    throw new Error("invalid delegation payload typ");
  }
  if (payload.ver !== 1) {
    throw new Error("unsupported delegation payload version");
  }

  const agentId = payload.agent_id;
  if (typeof agentId !== "string") {
    throw new Error("delegation agent_id missing");
  }

  let key: Awaited<ReturnType<typeof importJWK>>;
  if (payload.iss === "rare-signer") {
    if (payload.act !== "delegated_by_rare") {
      throw new Error("rare signer delegation missing act");
    }
    if (!options.rareSignerPublicKeyB64) {
      throw new Error("rare signer key unavailable");
    }
    key = await importJWK(
      { kty: "OKP", crv: "Ed25519", x: options.rareSignerPublicKeyB64 },
      "EdDSA",
    );
  } else if (payload.iss === "agent") {
    if (payload.act !== "delegated_by_agent") {
      throw new Error("agent delegation missing act");
    }
    key = await importJWK({ kty: "OKP", crv: "Ed25519", x: agentId }, "EdDSA");
  } else {
    throw new Error("unsupported delegation issuer");
  }

  const verified = await jwtVerify(token, key, {
    algorithms: ["EdDSA"],
    clockTolerance: options.clockSkewSeconds ?? 30,
  });
  const verifiedPayload = verified.payload as Record<string, unknown>;

  if (verifiedPayload.aud !== options.expectedAud) {
    throw new Error("delegation aud mismatch");
  }

  const scope = verifiedPayload.scope;
  if (!Array.isArray(scope) || !scope.includes(options.requiredScope)) {
    throw new Error("delegation scope missing required action");
  }

  if (typeof verifiedPayload.session_pubkey !== "string") {
    throw new Error("delegation missing session_pubkey");
  }

  const now = options.currentTs ?? nowTs();
  const iat = verifiedPayload.iat;
  const exp = verifiedPayload.exp;
  const jti = verifiedPayload.jti;
  if (typeof iat !== "number" || typeof exp !== "number") {
    throw new Error("delegation timestamps must be integers");
  }
  if (typeof jti !== "string" || jti.trim().length === 0) {
    throw new Error("delegation jti missing");
  }
  const skew = options.clockSkewSeconds ?? 30;
  if (iat - skew > now) {
    throw new Error("delegation token not yet valid");
  }
  if (exp + skew < now) {
    throw new Error("delegation token expired");
  }

  return {
    header: header as Record<string, unknown>,
    payload: verifiedPayload,
  };
}

export function buildAuthChallengePayload(input: {
  aud: string;
  nonce: string;
  issuedAt: number;
  expiresAt: number;
}): string {
  return `rare-auth-v1:${input.aud}:${input.nonce}:${input.issuedAt}:${input.expiresAt}`;
}

export function buildActionPayload(input: {
  aud: string;
  sessionToken: string;
  action: string;
  actionPayload: Record<string, unknown>;
  nonce: string;
  issuedAt: number;
  expiresAt: number;
}): string {
  const bodyHash = sha256Hex(stableJson(input.actionPayload));
  return `rare-act-v1:${input.aud}:${input.sessionToken}:${input.action}:${bodyHash}:${input.nonce}:${input.issuedAt}:${input.expiresAt}`;
}

export function stableJson(value: unknown): string {
  return JSON.stringify(sortJson(value));
}

function sortJson(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => sortJson(item));
  }
  if (value && typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>).sort(
      ([a], [b]) => (a < b ? -1 : a > b ? 1 : 0),
    );
    const output: Record<string, unknown> = {};
    for (const [k, v] of entries) {
      output[k] = sortJson(v);
    }
    return output;
  }
  return value;
}

function sha256Hex(input: string): string {
  const bytes = new TextEncoder().encode(input);
  return createHash("sha256").update(bytes).digest("hex");
}

export function verifyDetached(
  input: string,
  signatureB64Url: string,
  publicKeyB64Url: string,
): boolean {
  const message = new TextEncoder().encode(input);
  const signature = decodeBase64Url(signatureB64Url);
  const publicKey = decodeBase64Url(publicKeyB64Url);
  return nacl.sign.detached.verify(message, signature, publicKey);
}

export interface RarePlatformEventItem {
  event_id: string;
  agent_id: string;
  category: "spam" | "fraud" | "abuse" | "policy_violation";
  severity: number;
  outcome: string;
  occurred_at: number;
  evidence_hash?: string;
}

export interface SignPlatformEventTokenInput {
  platformId: string;
  kid: string;
  privateKeyPem: string;
  jti: string;
  events: RarePlatformEventItem[];
  issuedAt?: number;
  expiresAt?: number;
}

export async function signPlatformEventToken(
  input: SignPlatformEventTokenInput,
): Promise<string> {
  const issuedAt = input.issuedAt ?? nowTs();
  const expiresAt = input.expiresAt ?? issuedAt + 300;
  const key = await importPKCS8(input.privateKeyPem, "EdDSA");
  const payload = {
    typ: "rare.platform-event",
    ver: 1,
    iss: input.platformId,
    aud: "rare.identity-library",
    iat: issuedAt,
    exp: expiresAt,
    jti: input.jti,
    events: input.events,
  };
  return new SignJWT(payload)
    .setProtectedHeader({
      alg: "EdDSA",
      typ: "rare.platform-event+jws",
      kid: input.kid,
    })
    .sign(key);
}

export function nowTs(): number {
  return Math.floor(Date.now() / 1000);
}

export function generateNonce(size = 18): string {
  return randomBytes(size).toString("base64url");
}

export function decodeBase64Url(value: string): Uint8Array {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  const pad =
    normalized.length % 4 === 0 ? "" : "=".repeat(4 - (normalized.length % 4));
  return new Uint8Array(Buffer.from(normalized + pad, "base64"));
}
