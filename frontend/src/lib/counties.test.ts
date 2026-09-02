import { describe, expect, it } from "vitest";

import { KENYA_COUNTIES, normaliseCounty } from "./counties";

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
