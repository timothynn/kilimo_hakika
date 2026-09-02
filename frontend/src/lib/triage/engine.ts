import type {
  MissingRequirement,
  SchemeRules,
  TriageInput,
  TriageResult,
} from "./types";

export class UnknownDepotError extends Error {
  constructor(depotId: string) {
    super(`Unknown depot: ${depotId}`);
    this.name = "UnknownDepotError";
  }
}

export class UnknownRequirementError extends Error {
  constructor(requirementId: string, depotId: string) {
    super(
      `Depot ${depotId} requires "${requirementId}", which is not in documents or documentGroups`
    );
    this.name = "UnknownRequirementError";
  }
}

/**
 * NOT THE VERDICT PATH.
 *
 * Farmer-facing verdicts come from the FastAPI engine via `src/lib/depot-api.ts`
 * and `app/api/triage/route.ts`. This module survives only as a tested,
 * dependency-free reference implementation of the same statutory math, kept
 * because its `anyOf` document-group modelling is worth porting upstream.
 *
 * Do not reconnect it to a route. Two engines meant two verdicts for the same
 * farmer, and that is the one failure this product cannot survive. See
 * docs/design/integration.md.
 *
 * Evaluate a farmer's situation against the scheme rules.
 *
 * Pure and deterministic: same inputs, same output, every time. No I/O, no
 * clock, no randomness, no network. A farmer is spending bus fare on this
 * answer, so it must be reproducible and explainable from the rules file
 * alone.
 *
 * Throws rather than guessing when the rules file and the input disagree —
 * a silent fallback here would mean telling someone to travel on a rule we
 * could not actually find.
 */
export function triage(rules: SchemeRules, input: TriageInput): TriageResult {
  const depot = rules.depots.find((d) => d.id === input.depotId);
  if (!depot) {
    throw new UnknownDepotError(input.depotId);
  }

  const held = new Set(input.heldDocuments);
  const missing: MissingRequirement[] = [];
  const citations = new Set<string>([depot.source]);

  for (const requirementId of depot.requires) {
    const group = rules.documentGroups[requirementId];
    if (group) {
      citations.add(group.source);
      const satisfied = group.anyOf.some((id) => held.has(id));
      if (!satisfied) {
        missing.push({
          id: requirementId,
          label: group.label,
          detail: group.detail,
          source: group.source,
          satisfiedByAnyOf: group.anyOf.map((id) => ({
            id,
            label: rules.documents[id]?.label ?? id,
          })),
        });
      }
      continue;
    }

    const document = rules.documents[requirementId];
    if (!document) {
      throw new UnknownRequirementError(requirementId, depot.id);
    }

    citations.add(document.source);
    if (!held.has(requirementId)) {
      missing.push({
        id: requirementId,
        label: document.label,
        detail: document.detail,
        source: document.source,
      });
    }
  }

  const { bagsPerAcre, topDressingBagsPerAcre, maxBags, pricePerBagKes, unit } =
    depot.allocation;

  // Floor, not round: a farmer allocated a partial bag gets whole bags only,
  // and rounding up would quote a total the depot will refuse to honour.
  //
  // Round to 6dp before flooring. Acreage is a float, and 0.7 * 4 evaluates to
  // 2.8000000000000003 in binary floating point; naive flooring of similar
  // products can silently shave a whole bag off a farmer's entitlement.
  const entitledByAcreage = Math.floor(
    Number((input.acres * bagsPerAcre).toFixed(6))
  );
  const bags = Math.min(entitledByAcreage, maxBags);

  // Split the award back into its statutory halves. When the ceiling bites,
  // it is shared pro rata rather than taken off one half, and the planting
  // share absorbs any odd bag so the two always sum to `bags`.
  const topDressingBags = Math.floor(
    (bags * topDressingBagsPerAcre) / bagsPerAcre
  );
  const plantingBags = bags - topDressingBags;

  return {
    verdict: missing.length === 0 ? "PROCEED" : "DO_NOT_TRAVEL",
    depot: {
      id: depot.id,
      name: depot.name,
      county: depot.county,
      program: depot.program,
    },
    acres: input.acres,
    missing,
    costing: {
      bags,
      plantingBags,
      topDressingBags,
      unit,
      pricePerBagKes,
      totalKes: bags * pricePerBagKes,
      cappedByStatutoryCeiling: entitledByAcreage > maxBags,
      maxBags,
      bagsPerAcre,
    },
    citations: [...citations].sort(),
    rulesVersion: rules.version,
  };
}
