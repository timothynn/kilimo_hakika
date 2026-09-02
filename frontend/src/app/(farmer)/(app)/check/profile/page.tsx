import Link from "next/link";
import { redirect } from "next/navigation";

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
import { COUNTIES_ALPHABETICAL, normaliseCounty } from "@/lib/counties";
import { currentFarmer } from "@/lib/session";

import { saveProfile } from "./actions";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * The farmer's stored details.
 *
 * This is what saves them re-typing on every check: the wizard reads land size
 * and county from here. Editable fields are limited to those two — see
 * farmerProfileSchema for why the identity fields are not.
 */
export default async function ProfilePage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string; saved?: string }>;
}) {
  const farmer = await currentFarmer();
  if (!farmer) redirect("/login");

  const { error, saved } = await searchParams;

  return (
    <main className="mx-auto flex w-full max-w-2xl flex-col gap-6 px-4 py-8">
      <header className="flex flex-col gap-1">
        <h1 className="text-3xl">My details</h1>
        <p className="text-muted-foreground">
          Kept so you do not have to type them on every check.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Used to work out your answer</CardTitle>
          <CardDescription>
            Your allocation and cost are calculated from your land size. Keep it
            accurate — a wrong figure gives you a wrong total at the gate.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form action={saveProfile} className="flex flex-col gap-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor="acres">Land size (acres)</Label>
              <Input
                id="acres"
                name="acres"
                type="number"
                inputMode="decimal"
                min="0.1"
                step="0.1"
                defaultValue={farmer.acres}
                className="h-12 max-w-xs text-lg"
                required
              />
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="county">County</Label>
              {/* Native select, not the Radix one: this page posts to a
                  server action, and a plain <select name> submits without
                  JavaScript. Same reason the officer sign-in form is plain
                  HTML. */}
              <select
                id="county"
                name="county"
                defaultValue={normaliseCounty(farmer.county) ?? ""}
                className="border-input bg-background h-12 max-w-xs rounded-md border px-3"
                required
              >
                <option value="" disabled>
                  Choose your county
                </option>
                {COUNTIES_ALPHABETICAL.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
              <p className="text-muted-foreground text-sm">
                Used to put the depots nearest you first.
              </p>
            </div>

            {error === "invalid" && (
              <p className="text-gate text-sm">
                Check those two fields. Land size must be a number above zero,
                and county cannot be blank.
              </p>
            )}
            {saved === "1" && (
              <p className="text-proceed text-sm">Saved.</p>
            )}

            <div className="flex flex-wrap items-center gap-2">
              <Button type="submit">Save</Button>
              <Button asChild variant="outline">
                <Link href="/check">Check a depot</Link>
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Your identity</CardTitle>
          <CardDescription>
            A depot officer reads these back against the card in your hand, so
            they are corrected in person rather than changed here.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 text-sm">
          <Field label="Full name" value={farmer.fullName} />
          <Field label="Phone (you sign in with this)" value={farmer.phone} />
          <Field
            label="National ID"
            value={`Ends ${farmer.nationalIdLast4}`}
            note="We never store the full number — only a scrambled copy an officer can match against."
          />
          <Field
            label="Registered"
            value={new Date(farmer.registeredAt).toLocaleDateString("en-KE")}
          />
        </CardContent>
      </Card>
    </main>
  );
}

function Field({
  label,
  value,
  note,
}: {
  label: string;
  value: string;
  note?: string;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-muted-foreground text-xs">{label}</span>
      <span className="font-medium">{value}</span>
      {note && <span className="text-muted-foreground text-xs">{note}</span>}
    </div>
  );
}
