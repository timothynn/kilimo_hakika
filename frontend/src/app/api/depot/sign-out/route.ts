import { NextResponse } from "next/server";

import { ADMIN_COOKIE } from "@/lib/auth";

export const runtime = "nodejs";

export async function POST(request: Request) {
  const response = NextResponse.redirect(new URL("/depot/sign-in", request.url), {
    status: 303,
  });
  response.cookies.delete(ADMIN_COOKIE);
  return response;
}
