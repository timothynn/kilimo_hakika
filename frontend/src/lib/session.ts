import { cookies } from "next/headers";

import { ADMIN_COOKIE, verifySession } from "@/lib/auth";
import { findFarmerById, type Farmer } from "@/lib/db";
import { FARMER_COOKIE, readFarmerSession } from "@/lib/farmer-auth";

/** The signed-in farmer, or null. Safe to call on any server component. */
export async function currentFarmer(): Promise<Farmer | null> {
  const store = await cookies();
  const farmerId = await readFarmerSession(store.get(FARMER_COOKIE)?.value);
  if (!farmerId) return null;

  // The cookie survives the row being deleted, so re-read rather than trust it.
  return findFarmerById(farmerId);
}

/** Whether a depot officer session is active. */
export async function isOfficer(): Promise<boolean> {
  const store = await cookies();
  return verifySession(store.get(ADMIN_COOKIE)?.value);
}
