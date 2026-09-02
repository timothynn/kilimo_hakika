import Link from "next/link";
import { redirect } from "next/navigation";

import { FarmerSignUpForm } from "@/components/farmer-auth-forms";
import { currentFarmer } from "@/lib/session";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export default async function SignUpPage() {
  if (await currentFarmer()) redirect("/check");

  return (
    <main className="mx-auto flex w-full max-w-xl flex-col gap-6 px-4 py-12">
      <header className="flex flex-col gap-1">
        <Link href="/" className="text-muted-foreground text-sm underline">
          Kilimo Hakika
        </Link>
        <h1 className="text-2xl">Create an account</h1>
      </header>

      <FarmerSignUpForm />
    </main>
  );
}
