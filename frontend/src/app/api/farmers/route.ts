import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { ADMIN_COOKIE, verifySession } from "@/lib/auth";
import { listFarmers, registerFarmer } from "@/lib/db";
import { farmerRegistrationSchema } from "@/lib/triage/schema";

export const runtime = "nodejs";

/**
 * Listing the registry is officer-only. Middleware guards the /depot pages,
 * but it does not cover /api — so this route checks the session itself
 * rather than assuming an upstream gate.
 */
export async function GET(request: Request) {
  const store = await cookies();
  if (!(await verifySession(store.get(ADMIN_COOKIE)?.value))) {
    return NextResponse.json({ error: "Not authorised" }, { status: 401 });
  }

  const county = new URL(request.url).searchParams.get("county") ?? undefined;
  return NextResponse.json({ farmers: listFarmers({ county }) });
}

export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Expected a JSON body" }, { status: 400 });
  }

  const parsed = farmerRegistrationSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { error: "Invalid input", issues: parsed.error.issues },
      { status: 400 }
    );
  }

  // consentGiven is validated, not stored as a column value — registerFarmer
  // stamps consent_given_at itself.
  const farmer = {
    fullName: parsed.data.fullName,
    nationalId: parsed.data.nationalId,
    phone: parsed.data.phone,
    county: parsed.data.county,
    acres: parsed.data.acres,
  };

  try {
    return NextResponse.json({ farmer: registerFarmer(farmer) }, { status: 201 });
  } catch (error) {
    // national_id_hash is UNIQUE — a repeat registration is a conflict, not a
    // server error, and the message must not confirm which ID is taken.
    if (error instanceof Error && error.message.includes("UNIQUE")) {
      return NextResponse.json(
        { error: "This farmer is already registered" },
        { status: 409 }
      );
    }
    throw error;
  }
}
