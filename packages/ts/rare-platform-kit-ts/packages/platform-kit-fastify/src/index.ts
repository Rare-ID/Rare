import type { FastifyInstance } from "fastify";

import type { RarePlatformKit } from "@rare-id/platform-kit-web";

export async function registerRarePlatformKit(
  app: FastifyInstance,
  options: { kit: RarePlatformKit },
): Promise<void> {
  app.post("/auth/challenge", async (request) => {
    const body = request.body as { aud?: string } | undefined;
    const challenge = await options.kit.issueChallenge(body?.aud);
    return {
      nonce: challenge.nonce,
      aud: challenge.aud,
      issued_at: challenge.issuedAt,
      expires_at: challenge.expiresAt,
    };
  });

  app.post("/auth/complete", async (request) => {
    const body = request.body as Record<string, string>;
    return options.kit.completeAuth({
      nonce: String(body.nonce),
      agentId: String(body.agent_id),
      sessionPubkey: String(body.session_pubkey),
      delegationToken: String(body.delegation_token),
      signatureBySession: String(body.signature_by_session),
      publicIdentityAttestation: body.public_identity_attestation,
      fullIdentityAttestation: body.full_identity_attestation,
    });
  });
}
