"use client";

import { useState } from "react";
import Link from "next/link";
import { CircleCheck, Loader2 } from "lucide-react";

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
import { farmerRegistrationSchema } from "@/lib/triage/schema";

export function RegisterForm() {
  const [fullName, setFullName] = useState("");
  const [nationalId, setNationalId] = useState("");
  const [phone, setPhone] = useState("");
  const [county, setCounty] = useState("");
  const [acres, setAcres] = useState("");
  const [consent, setConsent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);

    const parsed = farmerRegistrationSchema.safeParse({
      fullName,
      nationalId,
      phone,
      county,
      acres: Number(acres),
      consentGiven: consent,
    });
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? "Check your details");
      return;
    }

    setSubmitting(true);
    try {
      const response = await fetch("/api/farmers", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(parsed.data),
      });
      if (response.status === 409) {
        setError("These details are already registered.");
        return;
      }
      if (!response.ok) {
        setError("Could not register. Check your connection and retry.");
        return;
      }
      setDone(true);
    } catch {
      setError("Could not reach the service. Check your connection and retry.");
    } finally {
      setSubmitting(false);
    }
  }

  if (done) {
    return (
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <CircleCheck className="text-proceed size-5" aria-hidden />
            <CardTitle className="text-proceed">Registered</CardTitle>
          </div>
          <CardDescription>
            The depot can now find your details at the gate.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Link href="/" className="underline">
            Back to the depot check
          </Link>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Register your details</CardTitle>
        <CardDescription>
          Optional. You can check a depot without registering — this only helps
          the depot officer find you faster at the gate.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="flex flex-col gap-4">
          <Field label="Full name" id="fullName">
            <Input
              id="fullName"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="h-12"
              autoComplete="name"
            />
          </Field>

          <Field
            label="National ID number"
            id="nationalId"
            hint="Stored scrambled. The depot sees only the last four digits."
          >
            <Input
              id="nationalId"
              inputMode="numeric"
              value={nationalId}
              onChange={(e) => setNationalId(e.target.value)}
              className="h-12"
            />
          </Field>

          <Field label="Phone number" id="phone">
            <Input
              id="phone"
              inputMode="tel"
              placeholder="0712345678"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className="h-12"
              autoComplete="tel"
            />
          </Field>

          <Field label="County" id="county">
            <Input
              id="county"
              value={county}
              onChange={(e) => setCounty(e.target.value)}
              className="h-12"
            />
          </Field>

          <Field label="Land size in acres" id="acres">
            <Input
              id="acres"
              type="number"
              inputMode="decimal"
              min="0.1"
              step="0.1"
              value={acres}
              onChange={(e) => setAcres(e.target.value)}
              className="h-12"
            />
          </Field>

          <Label
            htmlFor="consent"
            className="border-border/60 flex cursor-pointer items-start gap-3 rounded-md border p-4"
          >
            <Checkbox
              id="consent"
              checked={consent}
              onCheckedChange={(checked) => setConsent(checked === true)}
            />
            <span className="text-sm font-normal">
              I agree that these details may be stored so a depot officer can
              confirm who I am at the gate.
            </span>
          </Label>

          {error && <p className="text-gate text-sm">{error}</p>}

          <Button type="submit" disabled={submitting} className="self-start">
            {submitting ? <Loader2 className="animate-spin" /> : null}
            Register
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

function Field({
  label,
  id,
  hint,
  children,
}: {
  label: string;
  id: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-2">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {hint && <p className="text-muted-foreground text-sm">{hint}</p>}
    </div>
  );
}
