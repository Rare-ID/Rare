import type { Request, Response } from "express";

import type { RarePlatformKit } from "@rare-id/platform-kit-web";

export function createExpressRareHandlers(kit: RarePlatformKit) {
  return {
    issueChallenge: async (req: Request, res: Response) => {
      try {
        const challenge = await kit.issueChallenge(req.body?.aud);
        res.json({
          nonce: challenge.nonce,
          aud: challenge.aud,
          issued_at: challenge.issuedAt,
          expires_at: challenge.expiresAt,
        });
      } catch (error) {
        res.status(400).json({ detail: String(error) });
      }
    },

    completeAuth: async (req: Request, res: Response) => {
      try {
        const result = await kit.completeAuth({
          nonce: req.body.nonce,
          agentId: req.body.agent_id,
          sessionPubkey: req.body.session_pubkey,
          delegationToken: req.body.delegation_token,
          signatureBySession: req.body.signature_by_session,
          publicIdentityAttestation: req.body.public_identity_attestation,
          fullIdentityAttestation: req.body.full_identity_attestation,
        });
        res.json(result);
      } catch (error) {
        res.status(400).json({ detail: String(error) });
      }
    },
  };
}
