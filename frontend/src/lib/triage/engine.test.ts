import { describe, expect, it } from "vitest";

import {
  triage,
  UnknownDepotError,
  UnknownRequirementError,
} from "./engine";
import type { SchemeRules } from "./types";

const rules: SchemeRules = {
  version: "test-1",
  documents: {
    national_id: { label: "Original National ID", detail: "", source: "s.4(1)" },
    evoucher_code: { label: "E-Voucher SMS code", detail: "", source: "s.6(2)" },
    land_title: { label: "Title deed", detail: "", source: "s.5(1)" },
    lease_agreement: { label: "Lease agreement", detail: "", source: "s.5(2)" },
  },
  documentGroups: {
    proof_of_land: {
      label: "Proof of land",
      detail: "",
      anyOf: ["land_title", "lease_agreement"],
      source: "s.5",
    },
  },
  depots: [
    {
      id: "depot-a",
      name: "Depot A",
      county: "Uasin Gishu",
      program: "Programme 2024",
      requires: ["national_id", "evoucher_code", "proof_of_land"],
      allocation: {
        unit: "50kg bag",
        bagsPerAcre: 2,
        maxBags: 10,
        pricePerBagKes: 2500,
      },
      source: "Schedule 1",
    },
  ],
};

const input = (overrides: Partial<Parameters<typeof triage>[1]> = {}) => ({
  acres: 2,
  depotId: "depot-a",
  heldDocuments: ["national_id", "evoucher_code", "land_title"],
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
      "proof_of_land",
    ]);
  });

  it("accepts either document in an anyOf group", () => {
    for (const proof of ["land_title", "lease_agreement"]) {
      const result = triage(
        rules,
        input({ heldDocuments: ["national_id", "evoucher_code", proof] })
      );
      expect(result.verdict).toBe("PROCEED");
    }
  });

  it("reports the group, and how to satisfy it, when no member is held", () => {
    const result = triage(
      rules,
      input({ heldDocuments: ["national_id", "evoucher_code"] })
    );
    const group = result.missing.find((m) => m.id === "proof_of_land");
    expect(group?.satisfiedByAnyOf?.map((o) => o.label)).toEqual([
      "Title deed",
      "Lease agreement",
    ]);
  });

  it("ignores documents the depot does not ask for", () => {
    const result = triage(
      rules,
      input({
        heldDocuments: [
          "national_id",
          "evoucher_code",
          "land_title",
          "lease_agreement",
        ],
      })
    );
    expect(result.verdict).toBe("PROCEED");
  });
});

describe("costing", () => {
  it("multiplies acreage by the per-acre rate", () => {
    const result = triage(rules, input({ acres: 2 }));
    expect(result.costing.bags).toBe(4);
    expect(result.costing.totalKes).toBe(10_000);
  });

  it("floors partial bags rather than rounding up", () => {
    // 1.75 acres * 2 = 3.5 bags. Quoting 4 would promise a bag the depot
    // will not hand over.
    const result = triage(rules, input({ acres: 1.75 }));
    expect(result.costing.bags).toBe(3);
    expect(result.costing.totalKes).toBe(7_500);
  });

  it("applies the depot ceiling and says that it did", () => {
    const result = triage(rules, input({ acres: 40 }));
    expect(result.costing.bags).toBe(10);
    expect(result.costing.cappedByDepotCeiling).toBe(true);
    expect(result.costing.totalKes).toBe(25_000);
  });

  it("does not flag a cap when acreage is the binding limit", () => {
    expect(triage(rules, input({ acres: 5 })).costing).toMatchObject({
      bags: 10,
      cappedByDepotCeiling: false,
    });
  });

  it("costs a sub-bag holding at zero rather than negative", () => {
    const result = triage(rules, input({ acres: 0.25 }));
    expect(result.costing.bags).toBe(0);
    expect(result.costing.totalKes).toBe(0);
  });

  it("still costs the allocation when the verdict is DO_NOT_TRAVEL", () => {
    // The farmer needs to know the official price even on a refusal —
    // otherwise they cannot tell whether they are being overcharged later.
    const result = triage(rules, input({ heldDocuments: [] }));
    expect(result.verdict).toBe("DO_NOT_TRAVEL");
    expect(result.costing.totalKes).toBe(10_000);
  });
});

describe("citations", () => {
  it("returns every source the verdict rests on, deduplicated and sorted", () => {
    const result = triage(rules, input());
    expect(result.citations).toEqual([
      "Schedule 1",
      "s.4(1)",
      "s.5",
      "s.6(2)",
    ]);
  });

  it("cites the depot and requirements even when nothing is missing", () => {
    expect(triage(rules, input()).citations).toContain("Schedule 1");
  });
});

describe("determinism", () => {
  it("returns an identical result for identical input", () => {
    expect(triage(rules, input())).toEqual(triage(rules, input()));
  });

  it("does not depend on the order documents were ticked", () => {
    const a = triage(
      rules,
      input({ heldDocuments: ["national_id", "evoucher_code", "land_title"] })
    );
    const b = triage(
      rules,
      input({ heldDocuments: ["land_title", "evoucher_code", "national_id"] })
    );
    expect(a).toEqual(b);
  });
});

describe("bad rules and bad input", () => {
  it("throws on an unknown depot rather than guessing", () => {
    expect(() => triage(rules, input({ depotId: "nope" }))).toThrow(
      UnknownDepotError
    );
  });

  it("throws when a depot requires something the rules file does not define", () => {
    const broken: SchemeRules = {
      ...rules,
      depots: [{ ...rules.depots[0], requires: ["ghost_document"] }],
    };
    expect(() => triage(broken, input())).toThrow(UnknownRequirementError);
  });
});
