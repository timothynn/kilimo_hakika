import { Logo } from "@/components/logo";
import { TriageWizard } from "@/components/triage-wizard";
import { DepotApiError, getCounties } from "@/lib/depot-api";
import { currentFarmer } from "@/lib/session";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export default async function CheckPage() {
  const farmer = await currentFarmer();

  // The county list is the one piece of reference data the first step cannot
  // start without, so it is fetched server-side. Constituencies, wards and
  // depots load on demand as the farmer cascades down.
  let counties: string[] = [];
  let engineDown = false;
  try {
    counties = (await getCounties()).counties.map((c) => c.county_name);
  } catch (error) {
    if (error instanceof DepotApiError) {
      engineDown = true;
    } else {
      throw error;
    }
  }

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

      {engineDown ? (
        // Fail loudly rather than falling back to a second engine. Two engines
        // meant two verdicts for the same farmer, and a wrong verdict costs
        // real money — "I cannot check right now" is the honest answer.
        <div className="border-gate/40 bg-gate/5 rounded-md border-2 p-6">
          <h2 className="text-gate font-heading text-xl">
            The verdict service is not responding
          </h2>
          <p className="mt-2 text-sm">
            No check can be run right now. We will not guess an answer — a wrong
            verdict costs you a wasted journey. Please try again shortly.
          </p>
          <p className="text-muted-foreground mt-3 text-xs">
            If you are running this locally, start the engine with{" "}
            <code>uvicorn main:app --reload --port 8000</code> in{" "}
            <code>backend/</code>.
          </p>
        </div>
      ) : (
        /* Acreage is prefilled for a signed-in farmer, but still editable --
           people farm different parcels, and the stored figure may be stale. */
        <TriageWizard counties={counties} defaultAcres={farmer?.acres} />
      )}

      <footer className="text-muted-foreground text-sm">
        Verdicts come from MOALD Circular 2026/02 and NCPB Operating Circular
        4B. Official government requirements and gazetted prices only. This tool
        sells nothing, takes no payments, and gives no farming advice.
      </footer>
    </main>
  );
}
