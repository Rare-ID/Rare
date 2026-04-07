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

const resolveRareSession = createRareSessionResolver({
  sessionStore,
  cookieName: RARE_SESSION_COOKIE_NAME,
});

export async function resolveRareSessionFromRequest(request: Request) {
  return resolveRareSession({
    authorizationHeader: request.headers.get("authorization"),
    cookieHeader: request.headers.get("cookie"),
  });
}
