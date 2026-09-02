import Link from "next/link";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { registryStats } from "@/lib/db";

import { lookupFarmer } from "./actions";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export default async function VerifyArrivalPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const { error } = await searchParams;
  const stats = registryStats();

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-4 py-8">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl">Verify an arrival</h1>
        <p className="text-muted-foreground text-sm">
          Type the ID number on the card the farmer is holding.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Farmer lookup</CardTitle>
          <CardDescription>
            Matches on the full ID number. We store it scrambled, so a partial
            number will not find anyone.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form action={lookupFarmer} className="flex flex-col gap-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor="nationalId">National ID number</Label>
              <Input
                id="nationalId"
                name="nationalId"
                inputMode="numeric"
                className="h-12 max-w-xs text-lg"
                required
              />
            </div>

            {error === "notfound" && (
              <p className="text-gate text-sm">
                No registered farmer with that ID. They can still be served —
                registration is optional — but check their documents by hand.
              </p>
            )}
            {error === "invalid" && (
              <p className="text-gate text-sm">
                That does not look like an ID number. Expect 7 to 9 digits.
              </p>
            )}

            <Button type="submit" className="self-start">
              Look up
            </Button>
          </form>
        </CardContent>
      </Card>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Registered farmers" value={stats.farmers} />
        <Stat label="Checks run" value={stats.checks} />
        <Stat label="Told to proceed" value={stats.proceed} tone="proceed" />
        <Stat label="Told not to travel" value={stats.doNotTravel} tone="gate" />
      </section>

      <p className="text-muted-foreground text-sm">
        <Link href="/depot/farmers" className="underline">
          Browse all registered farmers
        </Link>
      </p>
    </main>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone?: "proceed" | "gate";
}) {
  const toneClass =
    tone === "proceed"
      ? "text-proceed"
      : tone === "gate"
        ? "text-gate"
        : "text-foreground";

  return (
    <Card>
      <CardContent className="flex flex-col gap-1 pt-6">
        <span className={`font-heading text-3xl ${toneClass}`}>{value}</span>
        <span className="text-muted-foreground text-sm">{label}</span>
      </CardContent>
    </Card>
  );
}
