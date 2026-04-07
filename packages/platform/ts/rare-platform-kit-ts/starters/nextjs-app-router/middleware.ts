import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import { RARE_SESSION_COOKIE_NAME } from "@/lib/rare";

export function middleware(request: NextRequest) {
  if (request.nextUrl.pathname.startsWith("/dashboard")) {
    const sessionCookie = request.cookies.get(RARE_SESSION_COOKIE_NAME)?.value;
    if (!sessionCookie) {
      return NextResponse.redirect(new URL("/login", request.url));
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*"],
};
