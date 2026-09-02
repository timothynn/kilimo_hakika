import Link from "next/link";
import { notFound } from "next/navigation";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import {
  findFarmerById,
  listChecksForFarmer,
  listServiceRecords,
} from "@/lib/db";
import { loadRules } from "@/lib/triage/rules";

import { recordServed } from "../../actions";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const kes = (amount: number) => `${amount.toLocaleString("en-KE")} KES`;
const when = (iso: string) => new Date(iso).toLocaleString("en-KE");

export default async function FarmerDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const farmer = findFarmerById(id);
  if (!farmer) notFound();

  const checks = listChecksForFarmer(id);
  const served = listServiceRecords(id);
  const depots = loadRules().depots;
  const latest = checks[0];

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-8">
      <header className="flex flex-col gap-1">
        <Link
          href="/depot/farmers"
          className="text-muted-foreground text-sm underline"
        >
          Back to registry
        </Link>
        <h1 className="text-2xl">{farmer.fullName}</h1>
        <p className="text-muted-foreground text-sm">
          ID &hellip;{farmer.nationalIdLast4} &middot; {farmer.county} County
          &middot; {farmer.acres} acres &middot; {farmer.phone}
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>What this farmer was told</CardTitle>
          <CardDescription>
            {checks.length === 0
              ? "This farmer has not run a depot check."
              : "Most recent check first. Compare against the documents in front of you."}
          </CardDescription>
        </CardHeader>
        {checks.length > 0 && (
          <CardContent className="flex flex-col gap-4">
            {checks.map((check) => {
              const proceed = check.verdict === "PROCEED";
              const Icon = proceed ? CircleCheck : CircleSlash;
              const depot = depots.find((d) => d.id === check.depotId);

              return (
                <div key={check.id} className="flex flex-col gap-2">
                  <div className="flex items-center gap-2">
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
                      {depot?.name ?? check.depotId} &middot; {when(check.checkedAt)}
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
                          {item.label}
                        </Badge>
                      ))}
                    </div>
                  )}
                  <Separator className="bg-border/40" />
                </div>
              );
            })}
          </CardContent>
        )}
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Mark as served</CardTitle>
          <CardDescription>
            Record what the farmer actually collected. This is a record of what
            happened, not a prediction — it can differ from the check above.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form action={recordServed} className="flex flex-col gap-4">
            <input type="hidden" name="farmerId" value={farmer.id} />

            <div className="flex flex-col gap-2">
              <Label htmlFor="depotId">Depot</Label>
              <select
                id="depotId"
                name="depotId"
                defaultValue={latest?.depotId ?? depots[0]?.id}
                className="border-input bg-background h-12 rounded-md border px-3"
                required
              >
                {depots.map((depot) => (
                  <option key={depot.id} value={depot.id}>
                    {depot.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="flex flex-col gap-2">
                <Label htmlFor="bags">Bags collected</Label>
                <Input
                  id="bags"
                  name="bags"
                  type="number"
                  min="0"
                  step="1"
                  defaultValue={latest?.bags ?? 0}
                  className="h-12"
                  required
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="totalKes">Amount paid (KES)</Label>
                <Input
                  id="totalKes"
                  name="totalKes"
                  type="number"
                  min="0"
                  step="1"
                  defaultValue={latest?.totalKes ?? 0}
                  className="h-12"
                  required
                />
              </div>
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="note">Note (optional)</Label>
              <Input
                id="note"
                name="note"
                placeholder="Why this differs from the check, if it does"
                className="h-12"
              />
            </div>

            <Button type="submit" className="self-start">
              Record as served
            </Button>
          </form>
        </CardContent>
      </Card>

      {served.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Service history</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            {served.map((record) => (
              <div key={record.id} className="text-sm">
                <span className="font-heading">
                  {depots.find((d) => d.id === record.depotId)?.name ??
                    record.depotId}
                </span>{" "}
                &middot; {record.bags} bags &middot; {kes(record.totalKes)}{" "}
                &middot;{" "}
                <span className="text-muted-foreground">
                  {when(record.servedAt)}
                </span>
                {record.note && (
                  <p className="text-muted-foreground">{record.note}</p>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </main>
  );
}
