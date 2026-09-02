"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { updateFarmerProfile } from "@/lib/db";
import { currentFarmer } from "@/lib/session";
import { farmerProfileSchema } from "@/lib/triage/schema";

/**
 * Save the farmer's own land size and county.
 *
 * The farmer id comes from the session cookie, never from the form — a hidden
 * id field would let anyone edit anyone. A server action is its own entry
 * point, so the session check happens here and not only on the page.
 */
export async function saveProfile(formData: FormData) {
  const farmer = await currentFarmer();
  if (!farmer) redirect("/login");

  const parsed = farmerProfileSchema.safeParse({
    county: formData.get("county"),
    acres: Number(formData.get("acres")),
  });
  if (!parsed.success) {
    redirect("/check/profile?error=invalid");
  }

  updateFarmerProfile({
    id: farmer.id,
    county: parsed.data.county,
    acres: parsed.data.acres,
  });

  // The wizard prefills from this row, so its cached render is now stale.
  revalidatePath("/check");
  redirect("/check/profile?saved=1");
}
