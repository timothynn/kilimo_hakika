import Link from "next/link";
import { redirect } from "next/navigation";

import { FarmerSignInForm } from "@/components/farmer-auth-forms";
import { currentFarmer } from "@/lib/session";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export default async function LoginPage() {
  // Already signed in? Nothing to do here.
  if (await currentFarmer()) redirect("/check");

  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-6 px-4 py-12">
      <header className="flex flex-col gap-1">
        <Link href="/" className="text-muted-foreground text-sm underline">
          Kilimo Hakika
        </Link>
        <h1 className="text-2xl">Sign in</h1>
      </header>

      <FarmerSignInForm />

      <p className="text-muted-foreground text-sm">
        Are you a depot officer?{" "}
        <Link href="/depot/sign-in" className="underline">
          Gate console sign-in
        </Link>
      </p>
    </main>
  );
}
