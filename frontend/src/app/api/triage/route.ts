import { NextResponse } from "next/server";

import { findFarmerByNationalId, recordCheck } from "@/lib/db";
import { triage, UnknownDepotError } from "@/lib/triage/engine";
import { loadRules } from "@/lib/triage/rules";
import { triageInputSchema } from "@/lib/triage/schema";

export const runtime = "nodejs";

export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Expected a JSON body" }, { status: 400 });
  }

  // Re-validate server-side. The wizard uses the same schema, but a verdict
  // must never rest on what the browser claimed.
  const parsed = triageInputSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { error: "Invalid input", issues: parsed.error.issues },
      { status: 400 }
    );
  }

  let result;
  try {
    result = triage(loadRules(), parsed.data);
  } catch (error) {
    if (error instanceof UnknownDepotError) {
      return NextResponse.json({ error: error.message }, { status: 404 });
    }
    throw error;
  }

  // Optional: link the check to a registered farmer so a depot officer can
  // see what the farmer was told before they travelled. Anonymous checks are
  // still allowed — a farmer should not have to register to get an answer.
  const nationalId =
    typeof body === "object" && body !== null && "nationalId" in body
      ? String((body as { nationalId: unknown }).nationalId ?? "")
      : "";

  let farmerId: string | null = null;
  if (/^\d{7,9}$/.test(nationalId)) {
    farmerId = findFarmerByNationalId(nationalId)?.id ?? null;
  }

  recordCheck({
    farmerId,
    depotId: result.depot.id,
    acres: result.acres,
    verdict: result.verdict,
    bags: result.costing.bags,
    totalKes: result.costing.totalKes,
    missing: result.missing.map((m) => ({ id: m.id, label: m.label })),
    rulesVersion: result.rulesVersion,
  });

  return NextResponse.json(result);
}
