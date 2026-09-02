import { NextResponse } from "next/server";

import { FARMER_COOKIE } from "@/lib/farmer-auth";

export const runtime = "nodejs";

export async function POST(request: Request) {
  const response = NextResponse.redirect(new URL("/", request.url), {
    status: 303,
  });
  response.cookies.delete(FARMER_COOKIE);
  return response;
}
