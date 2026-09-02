"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, ArrowLeft, ArrowRight, Loader2 } from "lucide-react";

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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { VerdictCard } from "@/components/verdict-card";
import type { ApiTriageResponse } from "@/lib/depot-api";
import { triageInputSchema } from "@/lib/triage/schema";

export type CountyOption = { county_name: string };
export type DepotOption = {
  depot_id: string;
  name: string;
  town: string;
  county: string;
  status_label: string;
  serves_farmers: boolean;
  operating_hours: string;
};

const STEPS = ["Your land", "Your depot", "Your documents"] as const;

/**
 * The browser gives up before the user does. Slightly longer than the server's
 * own upstream timeout so a real backend error wins the race and produces a
 * useful message, rather than both sides timing out into a generic one.
 */
const REQUEST_TIMEOUT_MS = 12_000;

type IdState = "original" | "photocopy" | "none";

export function TriageWizard({
  counties,
  defaultAcres,
}: {
  counties: string[];
  /** Prefilled for a signed-in farmer. Still editable — the stored figure
      may be stale, and people farm more than one parcel. */
  defaultAcres?: number;
}) {
  const [step, setStep] = useState(0);

  // Step 0 — the holding
  const [acres, setAcres] = useState(defaultAcres ? String(defaultAcres) : "");
  const [county, setCounty] = useState("");
  const [constituency, setConstituency] = useState("");
  const [ward, setWard] = useState("");
  const [constituencies, setConstituencies] = useState<string[]>([]);
  const [wards, setWards] = useState<string[]>([]);

  // Step 1 — the depot, filtered to those whose catchment covers the county
  const [depots, setDepots] = useState<DepotOption[]>([]);
  const [depotsLoading, setDepotsLoading] = useState(false);
  const [depotId, setDepotId] = useState("");

  // Step 2 — the paperwork
  const [nationalId, setNationalId] = useState<IdState | "">("");
  const [hasEvoucher, setHasEvoucher] = useState(false);
  const [hasWaoForm, setHasWaoForm] = useState(false);
  const [isLandLeased, setIsLandLeased] = useState(false);
  const [hasStampedLease, setHasStampedLease] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<ApiTriageResponse | null>(null);

  const acresValue = Number(acres);
  const acresValid = acres.trim() !== "" && acresValue > 0 && acresValue <= 1000;

  /**
   * The cascade clears downstream answers in the change handlers rather than
   * in an effect. Clearing inside an effect body would set state during
   * render and cascade re-renders (`react-hooks/set-state-in-effect`), and it
   * would also briefly leave a stale ward paired with a fresh county. The
   * effects below only fetch.
   */
  function chooseCounty(next: string) {
    setCounty(next);
    setConstituency("");
    setWard("");
    setConstituencies([]);
    setWards([]);
    setDepotId("");
    setDepots([]);
    setDepotsLoading(next !== "");
    setError(null);
  }

  function chooseConstituency(next: string) {
    setConstituency(next);
    setWard("");
    setWards([]);
  }

  useEffect(() => {
    if (!county) return;
    let cancelled = false;
    fetchJson<{ constituencies: { constituency_name: string }[] }>(
      `/api/geo/constituencies?county=${encodeURIComponent(county)}`
    )
      .then((data) => {
        if (!cancelled) {
          setConstituencies(data.constituencies.map((c) => c.constituency_name));
        }
      })
      .catch(() => {
        if (!cancelled) setError(UNREACHABLE);
      });
    return () => {
      cancelled = true;
    };
  }, [county]);

  useEffect(() => {
    if (!county || !constituency) return;
    let cancelled = false;
    fetchJson<{ wards: { ward_name: string }[] }>(
      `/api/geo/wards?county=${encodeURIComponent(county)}&constituency=${encodeURIComponent(constituency)}`
    )
      .then((data) => {
        if (!cancelled) setWards(data.wards.map((w) => w.ward_name));
      })
      .catch(() => {
        if (!cancelled) setError(UNREACHABLE);
      });
    return () => {
      cancelled = true;
    };
  }, [county, constituency]);

  // Only depots whose gazetted catchment covers this county can serve them, so
  // there is no point offering the rest.
  useEffect(() => {
    if (!county) return;
    let cancelled = false;
    fetchJson<{ depots: DepotOption[] }>(
      `/api/depots?county=${encodeURIComponent(county)}`
    )
      .then((data) => {
        if (!cancelled) setDepots(data.depots);
      })
      .catch(() => {
        if (!cancelled) setError(UNREACHABLE);
      })
      .finally(() => {
        if (!cancelled) setDepotsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [county]);

  const locationComplete = county !== "" && constituency !== "" && ward !== "";
  const canAdvance =
    step === 0
      ? acresValid && locationComplete
      : step === 1
        ? depotId !== ""
        : nationalId !== "";

  async function submit() {
    setError(null);

    // Same schema the API re-runs server-side. Catching it here saves a round
    // trip on a weak connection; it is not the gate.
    const parsed = triageInputSchema.safeParse({
      acres: acresValue,
      county,
      constituency,
      ward,
      depotId,
      nationalId,
      hasEvoucher,
      hasWaoForm,
      isLandLeased,
      hasStampedLease,
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
        signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      });

      if (!response.ok) {
        // Never invent a verdict. Say what went wrong and let them retry.
        const body = await response.json().catch(() => null);
        setError(
          response.status === 503
            ? UNREACHABLE
            : (body?.error ??
              "Could not get an answer. Check your answers and retry.")
        );
        return;
      }
      setResult((await response.json()) as ApiTriageResponse);
    } catch (cause) {
      setError(
        cause instanceof Error && cause.name === "TimeoutError"
          ? "The check took too long to answer. Your connection may be slow — please retry."
          : UNREACHABLE
      );
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

            {/* A depot may only serve a farmer whose county is inside its
                gazetted catchment, so the verdict cannot be reached without
                knowing where the holding is. */}
            <Picker
              id="county"
              label="Which county is your land in?"
              placeholder="Choose your county"
              value={county}
              onChange={chooseCounty}
              options={counties}
            />
            <Picker
              id="constituency"
              label="Constituency"
              placeholder={county ? "Choose your constituency" : "Choose a county first"}
              value={constituency}
              onChange={chooseConstituency}
              options={constituencies}
              disabled={!county || constituencies.length === 0}
            />
            <Picker
              id="ward"
              label="Ward"
              placeholder={constituency ? "Choose your ward" : "Choose a constituency first"}
              value={ward}
              onChange={setWard}
              options={wards}
              disabled={!constituency || wards.length === 0}
            />
          </>
        )}

        {step === 1 && (
          <>
            <p className="text-muted-foreground text-sm">
              These are the Government depots whose catchment covers {county}{" "}
              County. Only these can serve you.
            </p>
            {depotsLoading && (
              <p className="text-muted-foreground flex items-center gap-2 text-sm">
                <Loader2 className="size-4 animate-spin" aria-hidden /> Loading
                depots…
              </p>
            )}
            {!depotsLoading && depots.length === 0 && (
              <p className="text-gate text-sm">
                No depots could be loaded for {county} County. Retry, or go back
                and check the county.
              </p>
            )}
            <RadioGroup
              value={depotId}
              onValueChange={setDepotId}
              className="flex flex-col gap-3"
            >
              {depots.map((depot) => (
                // Large hit area: this is used one-handed on a low-end phone.
                <Label
                  key={depot.depot_id}
                  htmlFor={depot.depot_id}
                  className="border-border hover:bg-secondary flex cursor-pointer items-center gap-3 rounded-md border p-4"
                >
                  <RadioGroupItem value={depot.depot_id} id={depot.depot_id} />
                  <span className="flex flex-col">
                    <span className="font-medium">{depot.name}</span>
                    <span className="text-muted-foreground text-sm">
                      {depot.town} — {depot.status_label}
                    </span>
                  </span>
                </Label>
              ))}
            </RadioGroup>
          </>
        )}

        {step === 2 && (
          <div className="flex flex-col gap-6">
            {/* Original versus photocopy is the commonest reason a farmer is
                turned away, so it is a three-way choice rather than a
                checkbox. An unticked box would mean both "I have nothing" and
                "I have a photocopy", and those need different advice. */}
            <fieldset className="flex flex-col gap-3">
              <legend className="mb-2 font-medium">
                What form of National ID will you carry?
              </legend>
              <RadioGroup
                value={nationalId}
                onValueChange={(value) => setNationalId(value as IdState)}
                className="flex flex-col gap-3"
              >
                <Choice
                  id="id-original"
                  value="original"
                  title="The original card"
                  detail="Accepted at the counter."
                />
                <Choice
                  id="id-photocopy"
                  value="photocopy"
                  title="Only a photocopy"
                  detail="Photocopies are refused at the counter."
                />
                <Choice
                  id="id-none"
                  value="none"
                  title="Neither"
                  detail="I will not have my ID with me."
                />
              </RadioGroup>
            </fieldset>

            <fieldset className="flex flex-col gap-3">
              <legend className="mb-2 font-medium">
                What else do you have with you?
              </legend>
              <p className="text-muted-foreground -mt-1 mb-1 text-sm">
                Tick only what you have right now. Leave the rest unticked —
                that is how we work out what you are missing.
              </p>
              <Toggle
                id="evoucher"
                checked={hasEvoucher}
                onChange={setHasEvoucher}
                title="KIAMIS E-Voucher SMS code"
                detail="The valid, unexpired code sent to your phone."
              />
              <Toggle
                id="wao"
                checked={hasWaoForm}
                onChange={setHasWaoForm}
                title="Duly signed Ward Agricultural Officer (WAO) form"
                detail="Countersigned by the WAO for your ward. A blank or unsigned form is refused."
              />
            </fieldset>

            {/* Leased land carries an extra mandatory document. The toggle is
                explicit so an unstamped lease produces a red verdict rather
                than passing unnoticed. */}
            <fieldset className="flex flex-col gap-3">
              <legend className="mb-2 font-medium">Your land</legend>
              <Toggle
                id="leased"
                checked={isLandLeased}
                onChange={(checked) => {
                  setIsLandLeased(checked);
                  if (!checked) setHasStampedLease(false);
                }}
                title="This land is leased, not owned"
                detail="Leased land needs an extra document."
              />
              {isLandLeased && (
                <div className="border-border ml-2 border-l-2 pl-4">
                  <Toggle
                    id="stamped-lease"
                    checked={hasStampedLease}
                    onChange={setHasStampedLease}
                    title="I have the Chief's stamped lease agreement"
                    detail="It must bear the Area Chief's official stamp. Without it you will be turned away."
                  />
                  {!hasStampedLease && (
                    <p className="text-gate mt-3 flex items-start gap-2 text-sm">
                      <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
                      Leased land without a stamped lease agreement will be
                      refused at the counter.
                    </p>
                  )}
                </div>
              )}
            </fieldset>
          </div>
        )}

        {error && (
          <p className="text-gate flex items-start gap-2 text-sm" role="alert">
            <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
            {error}
          </p>
        )}

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
            <Button onClick={submit} disabled={submitting || !canAdvance}>
              {submitting ? <Loader2 className="animate-spin" /> : null}
              Get my answer
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

const UNREACHABLE =
  "Could not reach the verdict service. It gives no answer rather than a guess — please check your connection and retry.";

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url, {
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  });
  if (!response.ok) throw new Error(String(response.status));
  return (await response.json()) as T;
}

function Picker({
  id,
  label,
  placeholder,
  value,
  onChange,
  options,
  disabled,
}: {
  id: string;
  label: string;
  placeholder: string;
  value: string;
  onChange: (value: string) => void;
  options: string[];
  disabled?: boolean;
}) {
  return (
    <div className="flex flex-col gap-2">
      <Label htmlFor={id}>{label}</Label>
      <Select value={value} onValueChange={onChange} disabled={disabled}>
        <SelectTrigger id={id} className="h-12 w-full">
          <SelectValue placeholder={placeholder} />
        </SelectTrigger>
        <SelectContent>
          {options.map((option) => (
            <SelectItem key={option} value={option}>
              {option}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

function Choice({
  id,
  value,
  title,
  detail,
}: {
  id: string;
  value: string;
  title: string;
  detail: string;
}) {
  return (
    <Label
      htmlFor={id}
      className="border-border hover:bg-secondary flex cursor-pointer items-start gap-3 rounded-md border p-4"
    >
      <RadioGroupItem value={value} id={id} />
      <span className="flex flex-col">
        <span className="font-medium">{title}</span>
        <span className="text-muted-foreground text-sm">{detail}</span>
      </span>
    </Label>
  );
}

function Toggle({
  id,
  checked,
  onChange,
  title,
  detail,
}: {
  id: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  title: string;
  detail: string;
}) {
  return (
    <Label
      htmlFor={id}
      className="border-border hover:bg-secondary flex cursor-pointer items-start gap-3 rounded-md border p-4"
    >
      <Checkbox
        id={id}
        checked={checked}
        onCheckedChange={(value) => onChange(value === true)}
      />
      <span className="flex flex-col">
        <span className="font-medium">{title}</span>
        <span className="text-muted-foreground text-sm">{detail}</span>
      </span>
    </Label>
  );
}
