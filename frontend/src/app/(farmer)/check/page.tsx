import { Logo } from "@/components/logo";
import { TriageWizard } from "@/components/triage-wizard";
import { currentFarmer } from "@/lib/session";
import { loadRules } from "@/lib/triage/rules";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export default async function CheckPage() {
  const rules = loadRules();
  const farmer = await currentFarmer();

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
      <header className="flex flex-col gap-4">
        <Logo />
        <h1 className="text-3xl">Check a depot</h1>
        <p className="text-muted-foreground">
          {farmer
            ? `Signed in as ${farmer.fullName}. Your land size is filled in already.`
            : "No account needed. Three questions, then your answer."}
        </p>
      </header>

      {/* Acreage is prefilled for a signed-in farmer, but still editable --
          people farm different parcels, and the stored figure may be stale. */}
      <TriageWizard
        depots={depots}
        documents={documents}
        defaultAcres={farmer?.acres}
      />

      <footer className="text-muted-foreground text-sm">
        Rules version {rules.version}. Official government requirements and
        gazetted prices only. This tool sells nothing, takes no payments, and
        gives no farming advice.
      </footer>
    </main>
  );
}
