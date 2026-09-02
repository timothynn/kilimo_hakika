import { NextResponse } from "next/server";

import { findFarmerCredentialsByPhone } from "@/lib/db";
import {
  clearPinAttempts,
  farmerCookieOptions,
  FARMER_COOKIE,
  issueFarmerSession,
  rateLimitPin,
  verifyPin,
} from "@/lib/farmer-auth";
import { farmerSignInSchema } from "@/lib/triage/schema";

export const runtime = "nodejs";

export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Expected a JSON body" }, { status: 400 });
  }

  const parsed = farmerSignInSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { error: parsed.error.issues[0]?.message ?? "Check your details" },
      { status: 400 }
    );
  }

  const { phone, pin } = parsed.data;

  // A 6-digit PIN is a million combinations. Without this it falls in minutes.
  const limit = rateLimitPin(phone);
  if (!limit.allowed) {
    return NextResponse.json(
      {
        error: `Too many attempts. Try again in ${Math.ceil(limit.retryAfterMs / 60000)} minutes.`,
      },
      { status: 429 }
    );
  }

  const record = findFarmerCredentialsByPhone(phone);

  // One message for "no such phone" and "wrong PIN" alike, so this cannot be
  // used to discover which numbers are registered.
  if (!record || !verifyPin(pin, record.pinHash)) {
    return NextResponse.json(
      { error: "That phone number and PIN do not match." },
      { status: 401 }
    );
  }

  clearPinAttempts(phone);

  const response = NextResponse.json({ farmer: record.farmer });
  response.cookies.set(
    FARMER_COOKIE,
    await issueFarmerSession(record.farmer.id),
    farmerCookieOptions
  );
  return response;
}
