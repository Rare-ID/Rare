export interface RareApiClientConfig {
  rareBaseUrl: string;
  fetchImpl?: typeof fetch;
  defaultHeaders?: Record<string, string>;
}

export interface PlatformRegisterChallengeResponse {
  challenge_id: string;
  txt_name: string;
  txt_value: string;
  expires_at: number;
}

export interface PlatformRegisterCompleteResponse {
  platform_id: string;
  platform_aud: string;
  domain: string;
  status: string;
}

export interface JwksResponse {
  issuer: string;
  keys: Array<{
    kid: string;
    kty: string;
    crv: string;
    x: string;
    retire_at?: number;
    rare_role?: string;
  }>;
}

export function extractRareSignerPublicKeyB64(jwks: {
  keys?: Array<Record<string, unknown>>;
}): string {
  if (!Array.isArray(jwks.keys)) {
    throw new Error("invalid JWKS payload");
  }

  const delegation = jwks.keys.find((item) => {
    return (
      typeof item?.rare_role === "string" && item.rare_role === "delegation"
    );
  });
  if (typeof delegation?.x === "string" && delegation.x.length > 0) {
    return delegation.x;
  }

  const fallback = jwks.keys.filter((item) => {
    return (
      typeof item?.kid === "string" &&
      item.kid.includes("rare-signer") &&
      typeof item.x === "string" &&
      item.x.length > 0
    );
  });
  if (fallback.length === 1) {
    return String(fallback[0].x);
  }

  throw new Error("rare signer key not present in JWKS");
}

export class RareApiClient {
  private readonly rareBaseUrl: string;
  private readonly fetchImpl: typeof fetch;
  private readonly defaultHeaders: Record<string, string>;

  constructor(config: RareApiClientConfig) {
    this.rareBaseUrl = config.rareBaseUrl.replace(/\/$/, "");
    this.fetchImpl = config.fetchImpl ?? fetch;
    this.defaultHeaders = config.defaultHeaders ?? {};
  }

  async getJwks(): Promise<JwksResponse> {
    return this.requestJson("GET", "/.well-known/rare-keys.json");
  }

  async getRareSignerPublicKeyB64(): Promise<string> {
    return extractRareSignerPublicKeyB64(await this.getJwks());
  }

  async issuePlatformRegisterChallenge(input: {
    platform_aud: string;
    domain: string;
  }): Promise<PlatformRegisterChallengeResponse> {
    return this.requestJson("POST", "/v1/platforms/register/challenge", input);
  }

  async completePlatformRegister(input: {
    challenge_id: string;
    platform_id: string;
    platform_aud: string;
    domain: string;
    keys: Array<{ kid: string; public_key: string }>;
  }): Promise<PlatformRegisterCompleteResponse> {
    return this.requestJson("POST", "/v1/platforms/register/complete", input);
  }

  async ingestPlatformEvents(
    eventToken: string,
  ): Promise<Record<string, unknown>> {
    return this.requestJson("POST", "/v1/identity-library/events/ingest", {
      event_token: eventToken,
    });
  }

  private async requestJson<T>(
    method: string,
    path: string,
    body?: Record<string, unknown>,
  ): Promise<T> {
    const response = await this.fetchImpl(`${this.rareBaseUrl}${path}`, {
      method,
      headers: {
        "Content-Type": "application/json",
        ...this.defaultHeaders,
      },
      body: body ? JSON.stringify(body) : undefined,
    });
    const text = await response.text();
    const data = text ? (JSON.parse(text) as Record<string, unknown>) : {};
    if (!response.ok) {
      const detail =
        typeof data.detail === "string" ? data.detail : JSON.stringify(data);
      throw new Error(`rare api error ${response.status}: ${detail}`);
    }
    return data as T;
  }
}
