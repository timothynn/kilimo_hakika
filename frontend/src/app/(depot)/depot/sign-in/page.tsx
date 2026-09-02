import Link from "next/link";
import { Lock, ShieldAlert } from "lucide-react";

import { AuthSplit, IconField } from "@/components/auth-split";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export const runtime = "nodejs";

export default async function DepotSignInPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string; next?: string }>;
}) {
  const { error, next } = await searchParams;

  return (
    <AuthSplit
      image="/img/farming-kenya.jpg"
      imageAlt=""
      eyebrow="Depot officers"
      headline="Gate console"
      tagline="Look a farmer up by ID, see the verdict they were given before travelling, and record what they actually collected."
    >
      <div className="flex flex-col gap-7">
        <div className="flex flex-col gap-2">
          <h2 className="text-4xl sm:text-5xl">Officer sign-in</h2>
          <p className="text-muted-foreground">
            Enter the depot passphrase issued by the programme administrator.
          </p>
        </div>

        {/* Plain HTML form, no JavaScript needed — a gate terminal on a bad
            connection should still be able to sign in. */}
        <form
          action="/api/depot/sign-in"
          method="post"
          className="flex flex-col gap-5"
        >
          <input type="hidden" name="next" value={next ?? "/depot"} />

          <IconField
            id="passphrase"
            label="Depot passphrase"
            icon={<Lock className="size-4" />}
          >
            <Input
              id="passphrase"
              name="passphrase"
              type="password"
              autoComplete="current-password"
              placeholder="••••••••••••"
              className="h-14 pl-11 text-base"
              required
            />
          </IconField>

          {/* Deliberately vague: never reveal whether a passphrase exists,
              only that this attempt failed. */}
          {error && (
            <p className="text-gate animate-fade-in text-sm" role="alert">
              Incorrect passphrase.
            </p>
          )}

          <Button type="submit" className="h-14 text-base">
            Sign in to the console
          </Button>
        </form>

        <div className="border-border bg-secondary/60 flex gap-3 rounded-lg border p-4">
          <ShieldAlert className="text-gate mt-0.5 size-5 shrink-0" aria-hidden />
          <p className="text-muted-foreground text-sm">
            This console shows farmers&apos; personal details. Do not sign in on
            a shared or public device, and sign out when you leave the gate.
          </p>
        </div>

        <p className="text-muted-foreground text-sm">
          Are you a farmer?{" "}
          <Link href="/login" className="text-foreground underline">
            Farmer sign-in
          </Link>
          {" · "}
          <Link href="/check" className="underline">
            Check a depot
          </Link>
        </p>
      </div>
    </AuthSplit>
  );
}
