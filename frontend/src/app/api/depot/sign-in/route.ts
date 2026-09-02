import { NextResponse } from "next/server";

import {
  ADMIN_COOKIE,
  checkPassphrase,
  issueSession,
  sessionCookieOptions,
} from "@/lib/auth";

export const runtime = "nodejs";

export async function POST(request: Request) {
  const form = await request.formData();
  const passphrase = String(form.get("passphrase") ?? "");
  const next = String(form.get("next") ?? "/depot");

  // Only allow same-origin paths back, so ?next= cannot be used to bounce an
  // officer to another site after they authenticate.
  const target = next.startsWith("/") && !next.startsWith("//") ? next : "/depot";

  if (!checkPassphrase(passphrase)) {
    const retry = new URL("/depot/sign-in", request.url);
    retry.searchParams.set("error", "1");
    retry.searchParams.set("next", target);
    return NextResponse.redirect(retry, { status: 303 });
  }

  const response = NextResponse.redirect(new URL(target, request.url), {
    status: 303,
  });
  response.cookies.set(ADMIN_COOKIE, await issueSession(), sessionCookieOptions);
  return response;
}
