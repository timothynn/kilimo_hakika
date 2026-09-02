import Link from "next/link";

import { RegisterForm } from "@/components/register-form";

export default function RegisterPage() {
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-col gap-6 px-4 py-8">
      <header className="flex flex-col gap-1">
        <Link href="/" className="text-muted-foreground text-sm underline">
          Back to the depot check
        </Link>
        <h1 className="text-3xl">Register</h1>
      </header>

      <RegisterForm />
    </main>
  );
}
