import { NextResponse } from "next/server";

import { registerFarmer } from "@/lib/db";
import {
  farmerCookieOptions,
  FARMER_COOKIE,
  hashPin,
  issueFarmerSession,
} from "@/lib/farmer-auth";
import { farmerSignUpSchema } from "@/lib/triage/schema";

export const runtime = "nodejs";

export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Expected a JSON body" }, { status: 400 });
  }

  const parsed = farmerSignUpSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { error: parsed.error.issues[0]?.message ?? "Check your details" },
      { status: 400 }
    );
  }

  const { fullName, nationalId, phone, county, acres, pin } = parsed.data;

  let farmer;
  try {
    farmer = registerFarmer({
      fullName,
      nationalId,
      phone,
      county,
      acres,
      pinHash: hashPin(pin),
    });
  } catch (error) {
    // phone and national_id_hash are both UNIQUE. Do not say which one
    // collided — that would confirm whether a given ID or number is registered.
    if (error instanceof Error && error.message.includes("UNIQUE")) {
      return NextResponse.json(
        { error: "An account with these details already exists. Try signing in." },
        { status: 409 }
      );
    }
    throw error;
  }

  const response = NextResponse.json({ farmer }, { status: 201 });
  response.cookies.set(
    FARMER_COOKIE,
    await issueFarmerSession(farmer.id),
    farmerCookieOptions
  );
  return response;
}
