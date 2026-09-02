import Link from "next/link";
import { redirect } from "next/navigation";
import { CircleCheck, CircleSlash } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { listChecksForFarmer } from "@/lib/db";
import { currentFarmer } from "@/lib/session";
import { DepotApiError, getDepots } from "@/lib/depot-api";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const kes = (amount: number) => `${amount.toLocaleString("en-KE")} KES`;
const when = (iso: string) => new Date(iso).toLocaleString("en-KE");

/**
 * The farmer's own copy of what they were told before travelling — the same
 * rows the gate console reads. Kept read-only: a past verdict is a record, and
 * re-running it is what /check is for.
 */
export default async function CheckHistoryPage() {
  const farmer = await currentFarmer();
  if (!farmer) redirect("/login");

  const checks = listChecksForFarmer(farmer.id);
  // Depot names come from the same service that issues verdicts, so the ids
  // in a stored check always resolve against the current roster. If it is
  // unreachable we fall back to the id rather than failing the page — this is
  // a record of the past, not a verdict, so a bare id is survivable.
  let depots: { id: string; name: string }[] = [];
  try {
    depots = (await getDepots()).depots.map((d) => ({
      id: d.depot_id,
      name: d.name,
    }));
  } catch (error) {
    if (!(error instanceof DepotApiError)) throw error;
  }

  return (
    <main className="mx-auto flex w-full max-w-2xl flex-col gap-6 px-4 py-8">
      <header className="flex flex-col gap-1">
        <h1 className="text-3xl">My past checks</h1>
        <p className="text-muted-foreground">
          What this tool told you before each trip. A depot officer sees the
          same list.
        </p>
      </header>

      {checks.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>No checks yet</CardTitle>
            <CardDescription>
              Run a check before you travel and it will appear here.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild>
              <Link href="/check">Check a depot</Link>
            </Button>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Most recent first</CardTitle>
            <CardDescription>
              Rules change. An old check is not a promise about today.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {checks.map((check) => {
              const proceed = check.verdict === "PROCEED";
              const Icon = proceed ? CircleCheck : CircleSlash;
              const depot = depots.find((d) => d.id === check.depotId);

              return (
                <div key={check.id} className="flex flex-col gap-2">
                  {/* Icon plus label, never colour alone. */}
                  <div className="flex flex-wrap items-center gap-2">
                    <Icon
                      className={`size-4 ${proceed ? "text-proceed" : "text-gate"}`}
                      aria-hidden
                    />
                    <span
                      className={`font-heading ${proceed ? "text-proceed" : "text-gate"}`}
                    >
                      {proceed ? "Proceed" : "Do not travel"}
                    </span>
                    <span className="text-muted-foreground text-sm">
                      {depot?.name ?? check.depotId} &middot;{" "}
                      {when(check.checkedAt)}
                    </span>
                  </div>
                  <p className="text-sm">
                    {check.acres} acres &middot; {check.bags} bags &middot;{" "}
                    <span className="text-statutory-strong font-heading">
                      {kes(check.totalKes)}
                    </span>
                  </p>
                  {check.missing.length > 0 && (
                    <div className="flex flex-wrap gap-2">
                      {check.missing.map((item) => (
                        <Badge key={item.id} variant="outline">
                          Missing: {item.label}
                        </Badge>
                      ))}
                    </div>
                  )}
                  <Separator className="bg-border" />
                </div>
              );
            })}
          </CardContent>
        </Card>
      )}
    </main>
  );
}
