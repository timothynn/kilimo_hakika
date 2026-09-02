import Link from "next/link";

import { TriageWizard } from "@/components/triage-wizard";
import { listChecksForFarmer } from "@/lib/db";
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
    provisional: depot.provisional,
  }));

  // Depots in the farmer's own county first — the list is ordered by policy
  // file otherwise, which puts a depot three counties away at the top.
  if (farmer) {
    depots.sort((a, b) => {
      const home = (depot: (typeof depots)[number]) =>
        depot.county.toLowerCase() === farmer.county.toLowerCase() ? 0 : 1;
      return home(a) - home(b);
    });
  }

  // Their last depot, else the nearest one we can infer. A default, not an
  // answer: the radio group stays fully editable.
  const lastDepotId = farmer ? listChecksForFarmer(farmer.id)[0]?.depotId : null;
  const defaultDepotId =
    (lastDepotId && depots.some((d) => d.id === lastDepotId)
      ? lastDepotId
      : undefined) ??
    (farmer &&
    depots[0]?.county.toLowerCase() === farmer.county.toLowerCase()
      ? depots[0].id
      : undefined);

  const documents = Object.entries(rules.documents).map(([id, document]) => ({
    id,
    label: document.label,
    detail: document.detail,
  }));

  return (
    <main className="mx-auto flex w-full max-w-2xl flex-col gap-6 px-4 py-8">
      {/* The logo lives in the side menu on this screen -- one visible
          instance per screen. */}
      <header className="flex flex-col gap-4">
        <h1 className="text-3xl">Check a depot</h1>
        <p className="text-muted-foreground">
          {farmer ? (
            <>
              Signed in as {farmer.fullName}. Your land size and depot are
              filled in from{" "}
              <Link href="/check/profile" className="underline">
                your details
              </Link>
              . Change them here if this trip is different.
            </>
          ) : (
            "No account needed. Three questions, then your answer."
          )}
        </p>
      </header>

      {/* Acreage and depot are prefilled for a signed-in farmer, but still
          editable -- people farm different parcels, and the stored figure may
          be stale. Documents are never prefilled: see TriageWizard. */}
      <TriageWizard
        depots={depots}
        documents={documents}
        defaultAcres={farmer?.acres}
        defaultDepotId={defaultDepotId}
        defaultCounty={farmer?.county}
        dashboardHref={farmer ? "/dashboard" : undefined}
      />

      <footer className="text-muted-foreground text-sm">
        Rules version {rules.version}. Official government requirements and
        gazetted prices only. This tool sells nothing, takes no payments, and
        gives no farming advice.
      </footer>
    </main>
  );
}
