import { NextResponse } from "next/server";

import {
  DepotApiError,
  runTriage,
  type ApiTriageRequest,
  type ApiTriageResponse,
} from "@/lib/depot-api";
import { findFarmerByNationalId, recordCheck } from "@/lib/db";
import { currentFarmer } from "@/lib/session";
import { triageInputSchema } from "@/lib/triage/schema";

export const runtime = "nodejs";

/**
 * Run a depot readiness check.
 *
 * This route decides nothing. It validates the farmer's answers, forwards them
 * to the FastAPI verdict engine, and adapts the reply for the UI. There is
 * deliberately no local fallback engine: two engines meant two verdicts for the
 * same farmer, which is the one failure this product cannot survive. If the
 * engine is unreachable we say so plainly rather than guessing — a farmer
 * betting bus fare deserves "I don't know" over a confident wrong answer.
 */
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
  const input = parsed.data;

  const upstream: ApiTriageRequest = {
    county: input.county,
    constituency: input.constituency,
    ward: input.ward,
    target_depot_id: input.depotId,
    acreage: input.acres,
    documents_held: documentsFor(input),
    is_land_leased: input.isLandLeased,
    // Only meaningful on leased land; sent as false otherwise so an owned
    // holding can never be read as having lease paperwork.
    has_stamped_lease: input.isLandLeased && input.hasStampedLease,
  };

  let verdict: ApiTriageResponse;
  try {
    verdict = await runTriage(upstream);
  } catch (error) {
    if (error instanceof DepotApiError) {
      return NextResponse.json(
        {
          error: error.message,
          unreachable: error.unreachable,
          detail: error.detail,
        },
        { status: error.unreachable ? 503 : error.status }
      );
    }
    throw error;
  }

  // Link the check to a registered farmer so a depot officer can see what the
  // farmer was told before they travelled, and so the farmer's own history is
  // not empty. Anonymous checks stay allowed — a farmer must never have to
  // register to get an answer.
  //
  // The session wins over a posted nationalIdNumber: the cookie is signed, so
  // it is the only identity claim on this endpoint we can actually trust. The
  // posted-number path stays for the signed-out flow. Without the session
  // branch the wizard, which posts no number, left every check by a signed-in
  // farmer with a null farmer_id — an empty history and an empty gate console.
  const sessionFarmer = await currentFarmer();

  const nationalIdNumber =
    typeof body === "object" && body !== null && "nationalIdNumber" in body
      ? String((body as { nationalIdNumber: unknown }).nationalIdNumber ?? "")
      : "";

  let farmerId: string | null = sessionFarmer?.id ?? null;
  if (!farmerId && /^\d{7,9}$/.test(nationalIdNumber)) {
    farmerId = findFarmerByNationalId(nationalIdNumber)?.id ?? null;
  }

  recordCheck({
    farmerId,
    depotId: verdict.depot.depot_id,
    acres: input.acres,
    verdict: verdict.verdict.status,
    bags: verdict.financial_breakdown.allocated_bags,
    totalKes: verdict.financial_breakdown.total_cost_kes,
    missing: verdict.gap_analysis.missing_documents.map((label) => ({
      id: label,
      label,
    })),
    rulesVersion: `${verdict.policy_grounding.circular} / ${verdict.policy_grounding.operating_procedure}`,
  });

  return NextResponse.json(verdict);
}

/**
 * Translate the wizard's answers into the document vocabulary the engine
 * speaks. A photocopy is not a weaker version of the original — it is an
 * actively disqualifying item, so it is declared rather than omitted, and the
 * engine returns the documented refusal for it.
 */
function documentsFor(input: {
  nationalId: "original" | "photocopy" | "none";
  hasEvoucher: boolean;
  hasWaoForm: boolean;
  isLandLeased: boolean;
  hasStampedLease: boolean;
}): string[] {
  const held: string[] = [];

  if (input.nationalId === "original") held.push("original_national_id");
  if (input.nationalId === "photocopy") held.push("national_id_photocopy");

  if (input.hasEvoucher) held.push("kiamis_evoucher_sms_code");
  if (input.hasWaoForm) held.push("wao_signed_form");
  if (input.isLandLeased && input.hasStampedLease) {
    held.push("chiefs_stamped_lease_agreement");
  }

  return held;
}
