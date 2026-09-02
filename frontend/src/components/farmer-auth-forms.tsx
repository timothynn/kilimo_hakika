"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Loader2 } from "lucide-react";

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
import { farmerSignInSchema, farmerSignUpSchema } from "@/lib/triage/schema";

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

export function FarmerSignInForm() {
  const router = useRouter();
  const [phone, setPhone] = useState("");
  const [pin, setPin] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);

    const parsed = farmerSignInSchema.safeParse({ phone, pin });
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? "Check your details");
      return;
    }

    setSubmitting(true);
    try {
      const response = await fetch("/api/farmer/sign-in", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(parsed.data),
      });
      const data = (await response.json()) as { error?: string };
      if (!response.ok) {
        setError(data.error ?? "Could not sign you in.");
        return;
      }
      router.push("/check");
      router.refresh();
    } catch {
      setError("Could not reach the service. Check your connection and retry.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Farmer sign in</CardTitle>
        <CardDescription>
          Your phone number and your 6-digit PIN.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="flex flex-col gap-4">
          <Field label="Phone number" id="phone">
            <Input
              id="phone"
              inputMode="tel"
              autoComplete="tel"
              placeholder="0712345678"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className="h-12"
            />
          </Field>

          <Field label="PIN" id="pin">
            <Input
              id="pin"
              type="password"
              inputMode="numeric"
              autoComplete="current-password"
              maxLength={6}
              value={pin}
              onChange={(e) => setPin(e.target.value)}
              className="h-12 tracking-[0.5em]"
            />
          </Field>

          {error && <p className="text-gate text-sm">{error}</p>}

          <Button type="submit" disabled={submitting} className="h-12">
            {submitting ? <Loader2 className="animate-spin" /> : null}
            Sign in
          </Button>

          <p className="text-muted-foreground text-sm">
            No account?{" "}
            <Link href="/signup" className="underline">
              Create one
            </Link>
            . Or{" "}
            <Link href="/check" className="underline">
              check a depot without signing in
            </Link>
            .
          </p>
        </form>
      </CardContent>
    </Card>
  );
}

export function FarmerSignUpForm() {
  const router = useRouter();
  const [values, setValues] = useState({
    fullName: "",
    nationalId: "",
    phone: "",
    county: "",
    acres: "",
    pin: "",
    confirmPin: "",
  });
  const [consent, setConsent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const set = (key: keyof typeof values) => (event: React.ChangeEvent<HTMLInputElement>) =>
    setValues((current) => ({ ...current, [key]: event.target.value }));

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);

    const parsed = farmerSignUpSchema.safeParse({
      ...values,
      acres: Number(values.acres),
      consentGiven: consent,
    });
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? "Check your details");
      return;
    }

    setSubmitting(true);
    try {
      const response = await fetch("/api/farmer/sign-up", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(parsed.data),
      });
      const data = (await response.json()) as { error?: string };
      if (!response.ok) {
        setError(data.error ?? "Could not create your account.");
        return;
      }
      router.push("/check");
      router.refresh();
    } catch {
      setError("Could not reach the service. Check your connection and retry.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Create a farmer account</CardTitle>
        <CardDescription>
          Optional — you can check a depot without one. An account lets the
          depot officer confirm who you are at the gate.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="flex flex-col gap-4">
          <Field label="Full name" id="fullName">
            <Input
              id="fullName"
              autoComplete="name"
              value={values.fullName}
              onChange={set("fullName")}
              className="h-12"
            />
          </Field>

          <Field
            label="National ID number"
            id="nationalId"
            hint="Stored scrambled. The depot only ever sees the last four digits."
          >
            <Input
              id="nationalId"
              inputMode="numeric"
              value={values.nationalId}
              onChange={set("nationalId")}
              className="h-12"
            />
          </Field>

          <Field label="Phone number" id="phone" hint="This is how you sign in.">
            <Input
              id="phone"
              inputMode="tel"
              autoComplete="tel"
              placeholder="0712345678"
              value={values.phone}
              onChange={set("phone")}
              className="h-12"
            />
          </Field>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="County" id="county">
              <Input
                id="county"
                value={values.county}
                onChange={set("county")}
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
                value={values.acres}
                onChange={set("acres")}
                className="h-12"
              />
            </Field>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Choose a 6-digit PIN" id="pin">
              <Input
                id="pin"
                type="password"
                inputMode="numeric"
                autoComplete="new-password"
                maxLength={6}
                value={values.pin}
                onChange={set("pin")}
                className="h-12 tracking-[0.5em]"
              />
            </Field>
            <Field label="Repeat the PIN" id="confirmPin">
              <Input
                id="confirmPin"
                type="password"
                inputMode="numeric"
                autoComplete="new-password"
                maxLength={6}
                value={values.confirmPin}
                onChange={set("confirmPin")}
                className="h-12 tracking-[0.5em]"
              />
            </Field>
          </div>

          <Label
            htmlFor="consent"
            className="border-border flex cursor-pointer items-start gap-3 rounded-md border p-4"
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

          <Button type="submit" disabled={submitting} className="h-12">
            {submitting ? <Loader2 className="animate-spin" /> : null}
            Create account
          </Button>

          <p className="text-muted-foreground text-sm">
            Already have an account?{" "}
            <Link href="/login" className="underline">
              Sign in
            </Link>
          </p>
        </form>
      </CardContent>
    </Card>
  );
}
