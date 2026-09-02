"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ADMIN_COOKIE, verifySession } from "@/lib/auth";
import { findFarmerByNationalId, markServed } from "@/lib/db";
import { farmerLookupSchema } from "@/lib/triage/schema";

/**
 * Server actions are their own entry point — middleware protects page
 * navigations, not action invocations. Each action re-checks the session
 * rather than trusting that the caller reached it through a guarded page.
 */
async function requireOfficer() {
  const store = await cookies();
  if (!(await verifySession(store.get(ADMIN_COOKIE)?.value))) {
    redirect("/depot/sign-in");
  }
}

export async function lookupFarmer(formData: FormData) {
  await requireOfficer();

  const parsed = farmerLookupSchema.safeParse({
    nationalId: formData.get("nationalId"),
  });
  if (!parsed.success) {
    redirect("/depot?error=invalid");
  }

  const farmer = findFarmerByNationalId(parsed.data.nationalId);
  if (!farmer) {
    redirect("/depot?error=notfound");
  }

  redirect(`/depot/farmers/${farmer.id}`);
}

export async function recordServed(formData: FormData) {
  await requireOfficer();

  const farmerId = String(formData.get("farmerId") ?? "");
  const depotId = String(formData.get("depotId") ?? "");
  const bags = Number(formData.get("bags") ?? 0);
  const totalKes = Number(formData.get("totalKes") ?? 0);
  const note = String(formData.get("note") ?? "").trim();

  if (!farmerId || !depotId || !Number.isFinite(bags)) {
    redirect(`/depot/farmers/${farmerId}?error=invalid`);
  }

  markServed({
    farmerId,
    depotId,
    bags: Math.trunc(bags),
    totalKes: Math.trunc(totalKes),
    note: note || undefined,
  });

  revalidatePath(`/depot/farmers/${farmerId}`);
}
