import Link from "next/link";

import { TriageWizard } from "@/components/triage-wizard";
import { loadRules } from "@/lib/triage/rules";

export const runtime = "nodejs";

export default function FarmerHome() {
  const rules = loadRules();

  const depots = rules.depots.map((depot) => ({
    id: depot.id,
    name: depot.name,
    county: depot.county,
  }));

  const documents = Object.entries(rules.documents).map(([id, document]) => ({
    id,
    label: document.label,
    detail: document.detail,
  }));

  return (
    <main className="mx-auto flex w-full max-w-2xl flex-col gap-6 px-4 py-8">
      <header className="flex flex-col gap-1">
        <h1 className="text-3xl">Kilimo Hakika</h1>
        <p className="text-muted-foreground">
          Find out whether the depot will serve you — before you spend money
          travelling there.
        </p>
      </header>

      <TriageWizard depots={depots} documents={documents} />

      <footer className="text-muted-foreground flex flex-col gap-2 text-sm">
        <p>
          Rules version {rules.version}. This tool shows official government
          requirements and gazetted prices only. It does not sell anything, take
          payments, or give farming advice.
        </p>
        <Link href="/register" className="underline">
          Register your details so the depot can find you
        </Link>
      </footer>
    </main>
  );
}
