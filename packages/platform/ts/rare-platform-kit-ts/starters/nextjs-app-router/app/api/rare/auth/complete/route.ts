import { NextResponse } from "next/server";

import { rare, RARE_SESSION_COOKIE_NAME } from "@/lib/rare";

export async function POST(request: Request) {
  try {
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
    response.cookies.set(RARE_SESSION_COOKIE_NAME, result.session_token, {
      httpOnly: true,
      sameSite: "lax",
      path: "/",
    });
    return response;
  } catch (error) {
    return NextResponse.json(
      { detail: error instanceof Error ? error.message : String(error) },
      { status: 400 },
    );
  }
}
