import { describe, expect, it } from "vitest";

import { KENYA_COUNTIES, normaliseCounty } from "./counties";
import { loadRules } from "./triage/rules";

describe("KENYA_COUNTIES", () => {
  it("lists all 47 counties exactly once", () => {
    expect(KENYA_COUNTIES).toHaveLength(47);
    expect(new Set(KENYA_COUNTIES).size).toBe(47);
  });
});

describe("normaliseCounty", () => {
  it("matches a county typed in any case", () => {
    expect(normaliseCounty("nyeri")).toBe("Nyeri");
    expect(normaliseCounty("  UASIN GISHU ")).toBe("Uasin Gishu");
  });

  it("tolerates a trailing 'County'", () => {
    expect(normaliseCounty("Nakuru County")).toBe("Nakuru");
  });

  it("returns undefined for anything not on the list", () => {
    expect(normaliseCounty("Atlantis")).toBeUndefined();
    expect(normaliseCounty("")).toBeUndefined();
    expect(normaliseCounty(undefined)).toBeUndefined();
  });
});

describe("scheme_rules depots", () => {
  /**
   * The wizard finds a farmer's depot by matching their chosen county against
   * `depot.county`. A typo or a non-county value in the policy file would not
   * throw anywhere — the depot would just never be offered as the default for
   * the county it actually serves, silently.
   */
  it("every depot sits in a real county", () => {
    const invalid = loadRules()
      .depots.filter((depot) => !normaliseCounty(depot.county))
      .map((depot) => `${depot.id}: "${depot.county}"`);

    expect(invalid).toEqual([]);
  });

  it("covers every county exactly once", () => {
    const covered = loadRules().depots.map((depot) =>
      normaliseCounty(depot.county)
    );

    expect(new Set(covered).size).toBe(KENYA_COUNTIES.length);
  });

  /**
   * The load-bearing one. A depot whose figures are invented must carry
   * `provisional: true`, because that flag is what makes the UI warn the
   * farmer that the cap and price are not gazetted. Dropping the flag while
   * leaving the placeholder numbers would present a guess as statutory fact
   * — the single failure this product cannot have.
   */
  it("marks every depot without a real citation as provisional", () => {
    const unmarked = loadRules()
      .depots.filter(
        (depot) =>
          depot.source.startsWith("UNVERIFIED") && depot.provisional !== true
      )
      .map((depot) => depot.id);

    expect(unmarked).toEqual([]);
  });

  it("keeps every provisional depot's source explicitly unverified", () => {
    const lying = loadRules()
      .depots.filter(
        (depot) => depot.provisional && !depot.source.startsWith("UNVERIFIED")
      )
      .map((depot) => depot.id);

    expect(lying).toEqual([]);
  });

  it("keeps the three cited depots cited", () => {
    const cited = loadRules().depots.filter((depot) => !depot.provisional);

    expect(cited.map((depot) => depot.id).sort()).toEqual([
      "ncpb-eldoret",
      "ncpb-kitale",
      "ncpb-nakuru",
    ]);
    for (const depot of cited) {
      expect(depot.source).toMatch(/Circular/);
    }
  });

  it("no two depots claim the same county", () => {
    const counties = loadRules().depots.map((depot) =>
      normaliseCounty(depot.county)
    );

    expect(new Set(counties).size).toBe(counties.length);
  });
});
