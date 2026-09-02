"use client";

import { useState } from "react";
import { ArrowLeft, ArrowRight, Loader2 } from "lucide-react";

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
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { VerdictCard } from "@/components/verdict-card";
import { triageInputSchema } from "@/lib/triage/schema";
import type { TriageResult } from "@/lib/triage/types";

export type DepotOption = {
  id: string;
  name: string;
  county: string;
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
}: {
  depots: DepotOption[];
  documents: DocumentOption[];
  /** Prefilled for a signed-in farmer. Still editable — the stored figure
      may be stale, and people farm more than one parcel. */
  defaultAcres?: number;
}) {
  const [step, setStep] = useState(0);
  const [acres, setAcres] = useState(defaultAcres ? String(defaultAcres) : "");
  const [depotId, setDepotId] = useState("");
  const [held, setHeld] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<TriageResult | null>(null);

  const acresValue = Number(acres);
  const acresValid = acres.trim() !== "" && acresValue > 0 && acresValue <= 1000;

  const canAdvance = step === 0 ? acresValid : step === 1 ? depotId !== "" : true;

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
        <Button
          variant="outline"
          className="self-start"
          onClick={() => {
            setResult(null);
            setStep(0);
          }}
        >
          Check again
        </Button>
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
        )}

        {step === 1 && (
          <RadioGroup
            value={depotId}
            onValueChange={setDepotId}
            className="flex flex-col gap-3"
          >
            {depots.map((depot) => (
              // Large hit area: this is used one-handed on a low-end phone.
              <Label
                key={depot.id}
                htmlFor={depot.id}
                className="border-border hover:bg-secondary flex cursor-pointer items-center gap-3 rounded-md border p-4"
              >
                <RadioGroupItem value={depot.id} id={depot.id} />
                <span className="flex flex-col">
                  <span className="font-medium">{depot.name}</span>
                  <span className="text-muted-foreground text-sm">
                    {depot.county} County
                  </span>
                </span>
              </Label>
            ))}
          </RadioGroup>
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
