import { NextResponse } from "next/server";

import { rare } from "@/lib/rare";

export async function POST(request: Request) {
  try {
    const body = (await request.json().catch(() => ({}))) as { aud?: string };
    const challenge = await rare.issueChallenge(body.aud);
    return NextResponse.json({
      nonce: challenge.nonce,
      aud: challenge.aud,
      issued_at: challenge.issuedAt,
      expires_at: challenge.expiresAt,
    });
  } catch (error) {
    return NextResponse.json(
      { detail: error instanceof Error ? error.message : String(error) },
      { status: 400 },
    );
  }
}
