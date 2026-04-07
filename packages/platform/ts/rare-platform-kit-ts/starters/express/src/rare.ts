import {
  InMemoryChallengeStore,
  InMemoryReplayStore,
  InMemorySessionStore,
  createRarePlatformKitFromEnv,
} from "@rare-id/platform-kit-web";

const challengeStore = new InMemoryChallengeStore();
const replayStore = new InMemoryReplayStore();
export const sessionStore = new InMemorySessionStore();

export const rare = createRarePlatformKitFromEnv({
  challengeStore,
  replayStore,
  sessionStore,
});
