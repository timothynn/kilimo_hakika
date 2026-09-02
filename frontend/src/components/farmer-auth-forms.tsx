"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowRight,
  IdCard,
  KeyRound,
  Landmark,
  Loader2,
  Ruler,
  Smartphone,
  User,
} from "lucide-react";

import { IconField } from "@/components/auth-split";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { farmerSignInSchema, farmerSignUpSchema } from "@/lib/triage/schema";

/** Shared field sizing: tall targets, room for the leading icon. */
const FIELD = "h-14 pl-11 text-base";

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
    <div className="flex flex-col gap-7">
      <div className="flex flex-col gap-2">
        <h2 className="text-4xl sm:text-5xl">Welcome back</h2>
        <p className="text-muted-foreground">
          Sign in with your phone number and PIN.
        </p>
      </div>

      <form onSubmit={submit} className="flex flex-col gap-5">
        <IconField
          id="phone"
          label="Phone number"
          icon={<Smartphone className="size-4" />}
        >
          <Input
            id="phone"
            inputMode="tel"
            autoComplete="tel"
            placeholder="0712345678"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            className={FIELD}
          />
        </IconField>

        <IconField id="pin" label="PIN" icon={<KeyRound className="size-4" />}>
          <Input
            id="pin"
            type="password"
            inputMode="numeric"
            autoComplete="current-password"
            maxLength={6}
            placeholder="••••••"
            value={pin}
            onChange={(e) => setPin(e.target.value)}
            className={`${FIELD} tracking-[0.4em]`}
          />
        </IconField>

        {error && (
          <p className="text-gate animate-fade-in text-sm" role="alert">
            {error}
          </p>
        )}

        <Button type="submit" disabled={submitting} className="h-14 text-base">
          {submitting ? <Loader2 className="animate-spin" /> : null}
          Sign in
        </Button>
      </form>

      {/* No password reset yet: there is no SMS gateway to send a code
          through, and a self-serve reset without one would be a way in for
          anyone who knows a farmer's phone number. */}
      <p className="text-muted-foreground text-sm">
        Forgotten your PIN? Ask a depot officer to reset it in person.
      </p>

      <div className="flex items-center gap-4">
        <span className="bg-border h-px flex-1" />
        <span className="text-muted-foreground text-xs tracking-widest uppercase">
          or
        </span>
        <span className="bg-border h-px flex-1" />
      </div>

      {/* The whole product works without an account. Keep this prominent. */}
      <Button asChild variant="outline" className="h-14 text-base">
        <Link href="/check">
          Check a depot without signing in <ArrowRight />
        </Link>
      </Button>

      <p className="text-muted-foreground text-sm">
        No account?{" "}
        <Link href="/signup" className="text-foreground underline">
          Create one
        </Link>
        {" · "}
        <Link href="/depot/sign-in" className="underline">
          Depot officer sign-in
        </Link>
      </p>
    </div>
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

  const set =
    (key: keyof typeof values) => (event: React.ChangeEvent<HTMLInputElement>) =>
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
    <div className="flex flex-col gap-7">
      <div className="flex flex-col gap-2">
        <h2 className="text-4xl">Create an account</h2>
        <p className="text-muted-foreground">
          Optional. It only exists so a depot officer can confirm who you are
          at the gate — you never need it to get an answer.
        </p>
      </div>

      <form onSubmit={submit} className="flex flex-col gap-5">
        <IconField
          id="fullName"
          label="Full name"
          icon={<User className="size-4" />}
        >
          <Input
            id="fullName"
            autoComplete="name"
            value={values.fullName}
            onChange={set("fullName")}
            className={FIELD}
          />
        </IconField>

        <IconField
          id="nationalId"
          label="National ID number"
          icon={<IdCard className="size-4" />}
          hint="Stored scrambled. The depot only ever sees the last four digits."
        >
          <Input
            id="nationalId"
            inputMode="numeric"
            value={values.nationalId}
            onChange={set("nationalId")}
            className={FIELD}
          />
        </IconField>

        <IconField
          id="phone"
          label="Phone number"
          icon={<Smartphone className="size-4" />}
          hint="This is how you sign in."
        >
          <Input
            id="phone"
            inputMode="tel"
            autoComplete="tel"
            placeholder="0712345678"
            value={values.phone}
            onChange={set("phone")}
            className={FIELD}
          />
        </IconField>

        <div className="grid gap-5 sm:grid-cols-2">
          <IconField
            id="county"
            label="County"
            icon={<Landmark className="size-4" />}
          >
            <Input
              id="county"
              value={values.county}
              onChange={set("county")}
              className={FIELD}
            />
          </IconField>

          <IconField
            id="acres"
            label="Acres farmed"
            icon={<Ruler className="size-4" />}
          >
            <Input
              id="acres"
              type="number"
              inputMode="decimal"
              min="0.1"
              step="0.1"
              value={values.acres}
              onChange={set("acres")}
              className={FIELD}
            />
          </IconField>
        </div>

        <div className="grid gap-5 sm:grid-cols-2">
          <IconField
            id="pin"
            label="Choose a 6-digit PIN"
            icon={<KeyRound className="size-4" />}
          >
            <Input
              id="pin"
              type="password"
              inputMode="numeric"
              autoComplete="new-password"
              maxLength={6}
              placeholder="••••••"
              value={values.pin}
              onChange={set("pin")}
              className={`${FIELD} tracking-[0.4em]`}
            />
          </IconField>

          <IconField
            id="confirmPin"
            label="Repeat the PIN"
            icon={<KeyRound className="size-4" />}
          >
            <Input
              id="confirmPin"
              type="password"
              inputMode="numeric"
              autoComplete="new-password"
              maxLength={6}
              placeholder="••••••"
              value={values.confirmPin}
              onChange={set("confirmPin")}
              className={`${FIELD} tracking-[0.4em]`}
            />
          </IconField>
        </div>

        <Label
          htmlFor="consent"
          className="border-border hover:bg-secondary flex cursor-pointer items-start gap-3 rounded-lg border p-4"
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

        {error && (
          <p className="text-gate animate-fade-in text-sm" role="alert">
            {error}
          </p>
        )}

        <Button type="submit" disabled={submitting} className="h-14 text-base">
          {submitting ? <Loader2 className="animate-spin" /> : null}
          Create account
        </Button>
      </form>

      <p className="text-muted-foreground text-sm">
        Already registered?{" "}
        <Link href="/login" className="text-foreground underline">
          Sign in
        </Link>
        {" · "}
        <Link href="/check" className="underline">
          Skip and check a depot
        </Link>
      </p>
    </div>
  );
}
