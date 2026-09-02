import Link from "next/link";
import { redirect } from "next/navigation";
import { ArrowRight, CircleCheck, CircleSlash } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { listChecksForFarmer } from "@/lib/db";
import { currentFarmer } from "@/lib/session";
import { loadRules } from "@/lib/triage/rules";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const kes = (amount: number) => `${amount.toLocaleString("en-KE")} KES`;
const when = (iso: string) => new Date(iso).toLocaleString("en-KE");

/**
 * Where a farmer lands after signing in, and where the result screen sends
 * them. It answers "what was I last told" at a glance and puts running a new
 * check one tap away — it is not a home for new features. Anything that does
 * not serve the three questions belongs nowhere, including here.
 */
export default async function DashboardPage() {
  const farmer = await currentFarmer();
  if (!farmer) redirect("/login");

  const checks = listChecksForFarmer(farmer.id);
  const last = checks[0];
  const depots = loadRules().depots;
  const lastDepot = last
    ? (depots.find((d) => d.id === last.depotId)?.name ?? last.depotId)
    : null;
  const proceed = last?.verdict === "PROCEED";

  return (
    <main className="mx-auto flex w-full max-w-2xl flex-col gap-6 px-4 py-8">
      <header className="flex flex-col gap-1">
        <h1 className="text-3xl">Karibu, {farmer.fullName.split(" ")[0]}</h1>
        <p className="text-muted-foreground">
          {checks.length === 0
            ? "Run a check before you spend money travelling to a depot."
            : `${checks.length} ${checks.length === 1 ? "check" : "checks"} so far. Rules change — check again before each trip.`}
        </p>
      </header>

      <Button asChild size="lg" className="h-14 self-start text-base">
        <Link href="/check">
          Check a depot <ArrowRight />
        </Link>
      </Button>

      {last ? (
        <Card>
          {/* Filled band, not coloured text: on a green UI, green type reads
              as decoration. Icon and label carry the meaning without colour. */}
          <div
            className={`flex items-center gap-2 rounded-t-md px-6 py-3 ${
              proceed
                ? "bg-proceed text-proceed-foreground"
                : "bg-gate text-gate-foreground"
            }`}
          >
            {proceed ? (
              <CircleCheck className="size-5 shrink-0" aria-hidden />
            ) : (
              <CircleSlash className="size-5 shrink-0" aria-hidden />
            )}
            <span className="font-heading tracking-wide">
              {proceed ? "PROCEED" : "DO NOT TRAVEL"}
            </span>
          </div>

          <CardHeader>
            <CardTitle>Your last check</CardTitle>
            <CardDescription>
              {lastDepot} &middot; {when(last.checkedAt)}
            </CardDescription>
          </CardHeader>

          <CardContent className="flex flex-col gap-4">
            <div className="grid gap-3 sm:grid-cols-3">
              <Figure label="Land size" value={`${last.acres} acres`} />
              <Figure label="Allowed" value={`${last.bags} bags`} statutory />
              <Figure
                label="Official total"
                value={kes(last.totalKes)}
                statutory
              />
            </div>

            {last.missing.length > 0 && (
              <div className="flex flex-col gap-2">
                <span className="text-muted-foreground text-sm">
                  What you were missing:
                </span>
                <div className="flex flex-wrap gap-2">
                  {last.missing.map((item) => (
                    <Badge key={item.id} variant="outline">
                      {item.label}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            <div className="flex flex-wrap gap-2">
              <Button asChild variant="outline">
                <Link href="/check/history">See all my checks</Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>No checks yet</CardTitle>
            <CardDescription>
              A check tells you whether the depot will serve you, what you are
              missing, and the official price — before you travel.
            </CardDescription>
          </CardHeader>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Your details</CardTitle>
          <CardDescription>
            Filled into every check so you do not retype them.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-end justify-between gap-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <Figure label="Land size" value={`${farmer.acres} acres`} />
            <Figure label="County" value={farmer.county} />
          </div>
          <Button asChild variant="outline">
            <Link href="/check/profile">Edit my details</Link>
          </Button>
        </CardContent>
      </Card>
    </main>
  );
}

function Figure({
  label,
  value,
  statutory,
}: {
  label: string;
  value: string;
  /** Gazette brass, for official figures only. Never decorative. */
  statutory?: boolean;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-muted-foreground text-xs">{label}</span>
      <span
        className={`font-heading text-lg ${statutory ? "text-statutory-strong" : ""}`}
      >
        {value}
      </span>
    </div>
  );
}
