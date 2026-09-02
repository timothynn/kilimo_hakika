import { redirect } from "next/navigation";

import { AuthSplit } from "@/components/auth-split";
import { FarmerSignUpForm } from "@/components/farmer-auth-forms";
import { currentFarmer } from "@/lib/session";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export default async function SignUpPage() {
  if (await currentFarmer()) redirect("/check");

  return (
    <AuthSplit
      image="/img/maize-field.jpg"
      imageAlt=""
      eyebrow="For farmers"
      headline="One account, recognised at the gate"
      tagline="Your details let the depot officer confirm who you are without paperwork. Checking a depot never requires it."
    >
      <FarmerSignUpForm />
    </AuthSplit>
  );
}
