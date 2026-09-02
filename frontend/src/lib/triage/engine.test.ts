import { describe, expect, it } from "vitest";

import { triage, UnknownDepotError, UnknownRequirementError } from "./engine";
import realRules from "./scheme_rules.json";
import type { SchemeRules } from "./types";

/**
 * Statutory math under MOALD Circular 2026/02:
 *   2 planting bags + 2 top-dressing bags per acre = 4 bags/acre,
 *   floored to whole bags, capped at 100 bags per farmer,
 *   at a flat KES 2,500 per 50kg bag.
 *
 * The previous fixture encoded 2 bags/acre with per-depot ceilings of 8/10/12,
 * which under-quoted every farmer by roughly half. These tests now pin the
 * corrected figures so that regression cannot return quietly.
 */
const rules: SchemeRules = {
  version: "test-2026-02",
  documents: {
    national_id: { label: "Original National ID", detail: "", source: "MOALD Circular 2026/02, Part III (a)" },
    evoucher_code: { label: "KIAMIS E-Voucher SMS code", detail: "", source: "MOALD Circular 2026/02, Part III (b)" },
    wao_form: { label: "Duly signed Ward Agricultural Officer (WAO) form", detail: "", source: "MOALD Circular 2026/02, Part III (c)" },
    land_title: { label: "Title deed", detail: "", source: "MOALD Circular 2026/02, s.5(1)" },
    lease_agreement: { label: "Chief's stamped lease agreement", detail: "", source: "MOALD Circular 2026/02, s.5(2)" },
  },
  documentGroups: {
    proof_of_land: {
      label: "Proof of land",
      detail: "",
      anyOf: ["land_title", "lease_agreement"],
      source: "MOALD Circular 2026/02, s.5",
    },
  },
  depots: [
    {
      id: "depot-a",
      name: "Depot A",
      county: "Uasin Gishu",
      program: "National Fertilizer Subsidy Programme 2026",
      requires: ["national_id", "evoucher_code", "wao_form", "proof_of_land"],
      allocation: {
        unit: "50kg bag",
        plantingBagsPerAcre: 2,
        topDressingBagsPerAcre: 2,
        bagsPerAcre: 4,
        maxBags: 100,
        pricePerBagKes: 2500,
      },
      source: "MOALD Circular 2026/02, Schedule 1",
    },
  ],
};

const ALL_HELD = ["national_id", "evoucher_code", "wao_form", "land_title"];

const input = (overrides: Partial<Parameters<typeof triage>[1]> = {}) => ({
  acres: 2,
  depotId: "depot-a",
  heldDocuments: ALL_HELD,
  ...overrides,
});

describe("verdict", () => {
  it("proceeds when every requirement is held", () => {
    const result = triage(rules, input());
    expect(result.verdict).toBe("PROCEED");
    expect(result.missing).toEqual([]);
  });

  it("refuses and itemises what is missing", () => {
    const result = triage(rules, input({ heldDocuments: ["national_id"] }));
    expect(result.verdict).toBe("DO_NOT_TRAVEL");
    expect(result.missing.map((m) => m.id)).toEqual([
      "evoucher_code",
      "wao_form",
      "proof_of_land",
    ]);
  });

  it("treats the signed WAO form as mandatory", () => {
    const result = triage(
      rules,
      input({ heldDocuments: ["national_id", "evoucher_code", "land_title"] })
    );
    expect(result.verdict).toBe("DO_NOT_TRAVEL");
    expect(result.missing.map((m) => m.id)).toEqual(["wao_form"]);
  });

  it("carries the citation for every missing item", () => {
    const result = triage(rules, input({ heldDocuments: [] }));
    for (const item of result.missing) {
      expect(item.source).toContain("MOALD Circular 2026/02");
    }
  });
});

describe("proof of land (anyOf group)", () => {
  it("accepts a title deed", () => {
    expect(triage(rules, input()).verdict).toBe("PROCEED");
  });

  it("accepts a stamped lease agreement instead", () => {
    const result = triage(
      rules,
      input({ heldDocuments: ["national_id", "evoucher_code", "wao_form", "lease_agreement"] })
    );
    expect(result.verdict).toBe("PROCEED");
  });

  it("reports the alternatives when neither is held", () => {
    const result = triage(
      rules,
      input({ heldDocuments: ["national_id", "evoucher_code", "wao_form"] })
    );
    expect(result.missing).toHaveLength(1);
    expect(result.missing[0].satisfiedByAnyOf?.map((d) => d.id)).toEqual([
      "land_title",
      "lease_agreement",
    ]);
  });
});

describe("statutory allocation", () => {
  it("awards 4 bags per acre: 2 planting + 2 top-dressing", () => {
    const result = triage(rules, input({ acres: 2 }));
    expect(result.costing.bags).toBe(8);
    expect(result.costing.plantingBags).toBe(4);
    expect(result.costing.topDressingBags).toBe(4);
    expect(result.costing.totalKes).toBe(20_000);
  });

  it("prices every bag at the flat statutory KES 2,500", () => {
    const result = triage(rules, input({ acres: 3 }));
    expect(result.costing.pricePerBagKes).toBe(2500);
    expect(result.costing.totalKes).toBe(result.costing.bags * 2500);
  });

  it("floors partial bags rather than rounding up", () => {
    // 1.75 acres * 4 = 7 bags exactly; 1.8 * 4 = 7.2 must floor to 7.
    expect(triage(rules, input({ acres: 1.75 })).costing.bags).toBe(7);
    expect(triage(rules, input({ acres: 1.8 })).costing.bags).toBe(7);
  });

  it("does not lose a bag to floating-point representation error", () => {
    // 0.7 * 4 evaluates to 2.8000000000000003; naive flooring is still 2, but
    // products that land a hair under an integer are the real hazard.
    expect(triage(rules, input({ acres: 0.7 })).costing.bags).toBe(2);
    expect(triage(rules, input({ acres: 2.35 })).costing.bags).toBe(9);
    expect(triage(rules, input({ acres: 1.1 })).costing.bags).toBe(4);
  });

  it("caps at the statutory ceiling of 100 bags", () => {
    const result = triage(rules, input({ acres: 40 }));
    expect(result.costing.bags).toBe(100);
    expect(result.costing.cappedByStatutoryCeiling).toBe(true);
    expect(result.costing.totalKes).toBe(250_000);
  });

  it("reaches the ceiling at exactly 25 acres and not before", () => {
    expect(triage(rules, input({ acres: 24.75 })).costing.bags).toBe(99);
    expect(triage(rules, input({ acres: 25 })).costing.bags).toBe(100);
    expect(triage(rules, input({ acres: 25 })).costing.cappedByStatutoryCeiling).toBe(false);
    expect(triage(rules, input({ acres: 26 })).costing.cappedByStatutoryCeiling).toBe(true);
  });

  it("splits the award pro rata when the ceiling binds", () => {
    const { plantingBags, topDressingBags, bags } = triage(
      rules,
      input({ acres: 500 })
    ).costing;
    expect(bags).toBe(100);
    expect(plantingBags + topDressingBags).toBe(100);
    expect(plantingBags).toBe(50);
    expect(topDressingBags).toBe(50);
  });

  it("awards nothing below a quarter acre", () => {
    const result = triage(rules, input({ acres: 0.2 }));
    expect(result.costing.bags).toBe(0);
    expect(result.costing.totalKes).toBe(0);
  });

  it("quotes the official cost even on a DO NOT TRAVEL", () => {
    // A farmer who does not know the gazetted price cannot tell they are being
    // overcharged on the next trip.
    const result = triage(rules, input({ acres: 2, heldDocuments: [] }));
    expect(result.verdict).toBe("DO_NOT_TRAVEL");
    expect(result.costing.totalKes).toBe(20_000);
  });
});

describe("determinism", () => {
  it("returns an identical result for an identical input", () => {
    const first = triage(rules, input());
    for (let i = 0; i < 25; i += 1) {
      expect(triage(rules, input())).toEqual(first);
    }
  });

  it("does not depend on the order documents are listed in", () => {
    const baseline = triage(rules, input({ heldDocuments: ALL_HELD }));
    const reversed = triage(rules, input({ heldDocuments: [...ALL_HELD].reverse() }));
    expect(reversed).toEqual(baseline);
  });
});

describe("refuses to guess", () => {
  it("throws on an unknown depot rather than inventing a verdict", () => {
    expect(() => triage(rules, input({ depotId: "nope" }))).toThrow(UnknownDepotError);
  });

  it("throws when a depot requires something the rules file does not define", () => {
    const broken: SchemeRules = {
      ...rules,
      depots: [{ ...rules.depots[0], requires: ["ghost_document"] }],
    };
    expect(() => triage(broken, input())).toThrow(UnknownRequirementError);
  });
});

describe("the shipped rules file", () => {
  const shipped = realRules as unknown as SchemeRules;

  it("matches the statutory allocation at every depot", () => {
    expect(shipped.depots.length).toBeGreaterThan(0);
    for (const depot of shipped.depots) {
      expect(depot.allocation.plantingBagsPerAcre).toBe(2);
      expect(depot.allocation.topDressingBagsPerAcre).toBe(2);
      expect(depot.allocation.bagsPerAcre).toBe(4);
      expect(depot.allocation.maxBags).toBe(100);
      expect(depot.allocation.pricePerBagKes).toBe(2500);
    }
  });

  it("requires the signed WAO form at every depot", () => {
    for (const depot of shipped.depots) {
      expect(depot.requires).toContain("wao_form");
    }
  });

  it("cites the 2026 circular, never the superseded 2024 one", () => {
    const json = JSON.stringify(shipped);
    expect(json).toContain("MOALD Circular 2026/02");
    expect(json).not.toContain("2024/02");
  });

  it("carries the no-cash rule with its citation", () => {
    expect(shipped.paymentAtDepot?.cashAccepted).toBe(false);
    expect(shipped.paymentAtDepot?.source).toContain("NCPB Operating Circular 4B");
  });
});
