import { createServer } from "node:http";

import { RareApiClient } from "@rare-id/platform-kit-client";
import {
  InMemoryChallengeStore,
  InMemoryReplayStore,
  InMemorySessionStore,
  createRarePlatformKit,
} from "@rare-id/platform-kit-web";

const rare = new RareApiClient({ rareBaseUrl: "http://127.0.0.1:8000/rare" });
const kit = createRarePlatformKit({
  aud: "platform",
  rareApiClient: rare,
  challengeStore: new InMemoryChallengeStore(),
  replayStore: new InMemoryReplayStore(),
  sessionStore: new InMemorySessionStore(),
});

const server = createServer(async (req, res) => {
  if (req.method === "POST" && req.url === "/auth/challenge") {
    const challenge = await kit.issueChallenge("platform");
    res.setHeader("Content-Type", "application/json");
    res.end(
      JSON.stringify({
        nonce: challenge.nonce,
        aud: challenge.aud,
        issued_at: challenge.issuedAt,
        expires_at: challenge.expiresAt,
      }),
    );
    return;
  }

  if (req.method === "POST" && req.url === "/auth/complete") {
    const body = await new Promise<string>((resolve, reject) => {
      const chunks: Buffer[] = [];
      req.on("data", (chunk) => chunks.push(Buffer.from(chunk)));
      req.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
      req.on("error", reject);
    });

    const input = JSON.parse(body) as Record<string, string>;
    const login = await kit.completeAuth({
      nonce: input.nonce,
      agentId: input.agent_id,
      sessionPubkey: input.session_pubkey,
      delegationToken: input.delegation_token,
      signatureBySession: input.signature_by_session,
      publicIdentityAttestation: input.public_identity_attestation,
      fullIdentityAttestation: input.full_identity_attestation,
    });

    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify(login));
    return;
  }

  res.statusCode = 404;
  res.end("not found");
});

server.listen(8080, "127.0.0.1", () => {
  console.log("platform listening on http://127.0.0.1:8080");
});
