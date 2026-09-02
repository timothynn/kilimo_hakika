import { redirect } from "next/navigation";

import { AuthSplit } from "@/components/auth-split";
import { FarmerSignInForm } from "@/components/farmer-auth-forms";
import { currentFarmer } from "@/lib/session";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export default async function LoginPage() {
  // Already signed in? Nothing to do here.
  if (await currentFarmer()) redirect("/dashboard");

  return (
    <AuthSplit
      image="/img/farmers-smallholder.jpg"
      imageAlt=""
      eyebrow="For farmers"
      headline="Never travel to a depot for nothing again"
      tagline="Check what the gate requires, what you are missing, and what it should officially cost — before you spend the fare."
    >
      <FarmerSignInForm />
    </AuthSplit>
  );
}
