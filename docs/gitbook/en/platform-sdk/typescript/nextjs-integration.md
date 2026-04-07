# Next.js Integration

The repository ships a starter for the Next.js App Router:

```text
packages/platform/ts/rare-platform-kit-ts/starters/nextjs-app-router
```

## Core Bootstrap

The starter keeps Rare wiring in `lib/rare.ts`:

```ts
import {
  InMemoryChallengeStore,
  InMemoryReplayStore,
  InMemorySessionStore,
  createRarePlatformKitFromEnv,
  createRareSessionResolver,
} from "@rare-id/platform-kit-web";

export const RARE_SESSION_COOKIE_NAME = "rare_session";

const challengeStore = new InMemoryChallengeStore();
const replayStore = new InMemoryReplayStore();
const sessionStore = new InMemorySessionStore();

export const rare = createRarePlatformKitFromEnv({
  challengeStore,
  replayStore,
  sessionStore,
});
```

## Route Handlers

Challenge route:

```ts
export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as { aud?: string };
  const challenge = await rare.issueChallenge(body.aud);
  return NextResponse.json({
    nonce: challenge.nonce,
    aud: challenge.aud,
    issued_at: challenge.issuedAt,
    expires_at: challenge.expiresAt,
  });
}
```

Complete route:

```ts
export async function POST(request: Request) {
  const body = (await request.json()) as Record<string, string | undefined>;
  const result = await rare.completeAuth({
    nonce: String(body.nonce ?? ""),
    agentId: String(body.agent_id ?? ""),
    sessionPubkey: String(body.session_pubkey ?? ""),
    delegationToken: String(body.delegation_token ?? ""),
    signatureBySession: String(body.signature_by_session ?? ""),
    publicIdentityAttestation: body.public_identity_attestation,
    fullIdentityAttestation: body.full_identity_attestation,
  });

  const response = NextResponse.json(result);
  response.cookies.set("rare_session", result.session_token, {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
  });
  return response;
}
```

## Middleware

You can gate app sections by checking the session cookie:

```ts
export function middleware(request: NextRequest) {
  if (request.nextUrl.pathname.startsWith("/dashboard")) {
    const sessionCookie = request.cookies.get("rare_session")?.value;
    if (!sessionCookie) {
      return NextResponse.redirect(new URL("/login", request.url));
    }
  }
  return NextResponse.next();
}
```

## Recommendation

Use the starter as your baseline, then replace the in-memory stores before deploying multiple instances.

