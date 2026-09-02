import { NextResponse, type NextRequest } from "next/server";

import { ADMIN_COOKIE, verifySession } from "@/lib/auth";

/**
 * Gates the depot officer console.
 *
 * This is the perimeter for page navigations only. API routes and server
 * actions re-check the session themselves — they are separate entry points,
 * and relying on this alone would leave them open.
 */
export async function proxy(request: NextRequest) {
  const authorised = await verifySession(
    request.cookies.get(ADMIN_COOKIE)?.value
  );

  if (authorised) return NextResponse.next();

  const signIn = new URL("/depot/sign-in", request.url);
  signIn.searchParams.set("next", request.nextUrl.pathname);
  return NextResponse.redirect(signIn);
}

export const config = {
  // Everything under /depot except the sign-in page itself. Written as a
  // negative lookahead rather than a list so a new officer page is protected
  // by default instead of by remembering to add it here.
  matcher: ["/depot((?!/sign-in).*)"],
};
