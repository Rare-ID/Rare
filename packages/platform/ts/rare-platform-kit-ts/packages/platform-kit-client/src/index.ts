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
  }>;
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
