"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowLeft, ArrowRight, Loader2, MapPin } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { VerdictCard } from "@/components/verdict-card";
import { COUNTIES_ALPHABETICAL, normaliseCounty } from "@/lib/counties";
import { triageInputSchema } from "@/lib/triage/schema";
import type { TriageResult } from "@/lib/triage/types";

export type DepotOption = {
  id: string;
  name: string;
  county: string;
  /** Placeholder figures, no circular behind them. See Depot.provisional. */
  provisional?: boolean;
};

export type DocumentOption = {
  id: string;
  label: string;
  detail: string;
};

const STEPS = ["Your land", "Your depot", "Your documents"] as const;

export function TriageWizard({
  depots,
  documents,
  defaultAcres,
  defaultDepotId,
  defaultCounty,
  dashboardHref,
}: {
  depots: DepotOption[];
  documents: DocumentOption[];
  /** Prefilled for a signed-in farmer. Still editable — the stored figure
      may be stale, and people farm more than one parcel. */
  defaultAcres?: number;
  /** The farmer's last depot, or one in their county. Editable for the same
      reason. Documents are deliberately never prefilled: a tick would claim
      they are holding a paper they may have lost since, and the verdict has
      to describe what is in their hand right now. */
  defaultDepotId?: string;
  /** The signed-in farmer's county, so step one starts on the right one. */
  defaultCounty?: string;
  /** Where the result screen's primary button goes. Absent when signed out. */
  dashboardHref?: string;
}) {
  const [step, setStep] = useState(0);
  const [acres, setAcres] = useState(defaultAcres ? String(defaultAcres) : "");
  const [county, setCounty] = useState(normaliseCounty(defaultCounty) ?? "");
  const [depotId, setDepotId] = useState(defaultDepotId ?? "");
  const [held, setHeld] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<TriageResult | null>(null);

  const acresValue = Number(acres);
  const acresValid = acres.trim() !== "" && acresValue > 0 && acresValue <= 1000;

  // The depot serving the chosen county, if the rules file lists one. Only
  // three counties have a depot today; the rest are a deliberate "not listed"
  // rather than an invented one -- a depot without a gazetted cap and price
  // behind it is exactly the guess this tool exists to replace.
  const countyDepot = depots.find(
    (depot) => depot.county.toLowerCase() === county.toLowerCase()
  );
  const otherDepots = depots.filter((depot) => depot.id !== countyDepot?.id);
  const selectedDepot = depots.find((depot) => depot.id === depotId);

  const canAdvance =
    step === 0 ? acresValid && county !== "" : step === 1 ? depotId !== "" : true;

  /**
   * Picking a county re-points the depot at that county's depot. It replaces
   * an earlier pick on purpose: someone who corrects their county meant to
   * change where they are travelling, and a stale depot from the old county
   * would be the wrong default to leave sitting there.
   */
  function chooseCounty(next: string) {
    setCounty(next);
    const match = depots.find(
      (depot) => depot.county.toLowerCase() === next.toLowerCase()
    );
    setDepotId(match?.id ?? "");
  }

  function toggleDocument(id: string, checked: boolean) {
    setHeld((current) =>
      checked ? [...current, id] : current.filter((d) => d !== id)
    );
  }

  async function submit() {
    setError(null);

    // Same schema the API re-runs server-side. Catching it here saves a
    // round trip on a weak connection; it is not the gate.
    const parsed = triageInputSchema.safeParse({
      acres: acresValue,
      depotId,
      heldDocuments: held,
    });
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? "Check your answers");
      return;
    }

    setSubmitting(true);
    try {
      const response = await fetch("/api/triage", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(parsed.data),
      });
      if (!response.ok) {
        setError("Could not get an answer. Check your connection and retry.");
        return;
      }
      setResult((await response.json()) as TriageResult);
    } catch {
      setError("Could not reach the service. Check your connection and retry.");
    } finally {
      setSubmitting(false);
    }
  }

  if (result) {
    return (
      <div className="flex flex-col gap-4">
        <VerdictCard result={result} />
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="outline"
            onClick={() => {
              setResult(null);
              setStep(0);
            }}
          >
            Check again
          </Button>
          {/* Signed-in only: there is nothing to go back to without an
              account, and the verdict itself never required one. */}
          {dashboardHref && (
            <Button asChild>
              <Link href={dashboardHref}>
                Go to my dashboard <ArrowRight />
              </Link>
            </Button>
          )}
        </div>
      </div>
    );
  }

  return (
    <Card>
      <CardHeader>
        <Progress value={((step + 1) / STEPS.length) * 100} className="mb-2" />
        <CardTitle>{STEPS[step]}</CardTitle>
        <CardDescription>
          Step {step + 1} of {STEPS.length}
        </CardDescription>
      </CardHeader>

      <CardContent className="flex flex-col gap-6">
        {step === 0 && (
          <>
            <div className="flex flex-col gap-2">
              <Label htmlFor="acres">How many acres do you farm?</Label>
              <Input
                id="acres"
                type="number"
                inputMode="decimal"
                min="0.1"
                step="0.1"
                placeholder="2"
                value={acres}
                onChange={(event) => setAcres(event.target.value)}
                className="h-12 text-lg"
              />
              <p className="text-muted-foreground text-sm">
                Your allocation is worked out from this.
              </p>
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="county">Which county do you farm in?</Label>
              {/* A picker, not a text box: the county has to match the rules
                  file exactly for your depot to be found. */}
              <Select value={county} onValueChange={chooseCounty}>
                <SelectTrigger id="county" className="!h-12 text-base">
                  <SelectValue placeholder="Choose your county" />
                </SelectTrigger>
                <SelectContent>
                  {COUNTIES_ALPHABETICAL.map((name) => (
                    <SelectItem key={name} value={name}>
                      {name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-muted-foreground text-sm">
                We use this to put your nearest depot up first.
              </p>
            </div>
          </>
        )}

        {step === 1 && (
          <div className="flex flex-col gap-5">
            {countyDepot ? (
              <div className="flex flex-col gap-2">
                <span className="text-muted-foreground text-sm">
                  The depot for {county} County
                </span>
                {/* Preselected, and shown as a stamped card rather than one
                    row in a list, because for most farmers this is the whole
                    answer to "which depot". */}
                <div
                  className={`flex items-center gap-3 rounded-md border p-4 ${
                    depotId === countyDepot.id
                      ? "border-primary bg-secondary"
                      : "border-border"
                  }`}
                >
                  <MapPin className="text-primary size-5 shrink-0" aria-hidden />
                  <span className="flex flex-col">
                    <span className="font-heading text-lg">
                      {countyDepot.name}
                    </span>
                    <span className="text-muted-foreground text-sm">
                      {countyDepot.county} County
                      {depotId === countyDepot.id && " — selected"}
                    </span>
                    {countyDepot.provisional && (
                      <span className="text-gate text-sm">
                        Figures not yet confirmed against a circular
                      </span>
                    )}
                  </span>
                  {depotId !== countyDepot.id && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="ml-auto"
                      onClick={() => setDepotId(countyDepot.id)}
                    >
                      Use this
                    </Button>
                  )}
                </div>
              </div>
            ) : (
              // Unreachable while every county has an entry, kept as the
              // honest fallback if a county is ever removed from the rules
              // file: no depot is better than the wrong depot.
              <div className="border-border flex flex-col gap-1 rounded-md border p-4">
                <span className="font-medium">
                  No depot listed for {county || "your"} County
                </span>
                <span className="text-muted-foreground text-sm">
                  The current circular ({/* rules version is in the footer */}
                  see below) covers the depots in the list. Pick the one you
                  plan to travel to.
                </span>
              </div>
            )}

            <div className="flex flex-col gap-2">
              <Label htmlFor="depot">
                {countyDepot ? "Travelling somewhere else?" : "Choose a depot"}
              </Label>
              <Select value={depotId} onValueChange={setDepotId}>
                <SelectTrigger id="depot" className="!h-12 text-base">
                  <SelectValue placeholder="Choose a depot">
                    {selectedDepot?.name}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {(countyDepot ? [countyDepot, ...otherDepots] : depots).map(
                    (depot) => (
                      <SelectItem key={depot.id} value={depot.id}>
                        {depot.name} — {depot.county} County
                      </SelectItem>
                    )
                  )}
                </SelectContent>
              </Select>
              <p className="text-muted-foreground text-sm">
                Each depot has its own document list and its own cap, so the
                answer changes with the depot.
              </p>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="flex flex-col gap-3">
            <p className="text-muted-foreground text-sm">
              Tick only what you have with you right now. Leave the rest
              unticked — that is how we work out what you are missing.
            </p>
            {documents.map((document) => (
              <Label
                key={document.id}
                htmlFor={document.id}
                className="border-border hover:bg-secondary flex cursor-pointer items-start gap-3 rounded-md border p-4"
              >
                <Checkbox
                  id={document.id}
                  checked={held.includes(document.id)}
                  onCheckedChange={(checked) =>
                    toggleDocument(document.id, checked === true)
                  }
                />
                <span className="flex flex-col">
                  <span className="font-medium">{document.label}</span>
                  <span className="text-muted-foreground text-sm">
                    {document.detail}
                  </span>
                </span>
              </Label>
            ))}
          </div>
        )}

        {error && <p className="text-gate text-sm">{error}</p>}

        <div className="flex items-center gap-2">
          {step > 0 && (
            <Button
              variant="outline"
              onClick={() => setStep((s) => s - 1)}
              disabled={submitting}
            >
              <ArrowLeft /> Back
            </Button>
          )}
          {step < STEPS.length - 1 ? (
            <Button onClick={() => setStep((s) => s + 1)} disabled={!canAdvance}>
              Next <ArrowRight />
            </Button>
          ) : (
            <Button onClick={submit} disabled={submitting}>
              {submitting ? <Loader2 className="animate-spin" /> : null}
              Get my answer
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
