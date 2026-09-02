/**
 * Kenya's 47 counties, in the order of the First Schedule to the Constitution
 * of Kenya 2010.
 *
 * This is administrative reference data, not policy, which is why it lives in
 * code rather than in `scheme_rules.json` — no verdict, cap or price is
 * derived from it. It exists so that county is picked from a fixed list
 * instead of typed: a farmer who writes "nyeri county" and a rules file that
 * says "Nyeri" would otherwise never match, and the depot for their county
 * would silently fail to appear.
 */
export const KENYA_COUNTIES = [
  "Mombasa",
  "Kwale",
  "Kilifi",
  "Tana River",
  "Lamu",
  "Taita Taveta",
  "Garissa",
  "Wajir",
  "Mandera",
  "Marsabit",
  "Isiolo",
  "Meru",
  "Tharaka-Nithi",
  "Embu",
  "Kitui",
  "Machakos",
  "Makueni",
  "Nyandarua",
  "Nyeri",
  "Kirinyaga",
  "Murang'a",
  "Kiambu",
  "Turkana",
  "West Pokot",
  "Samburu",
  "Trans Nzoia",
  "Uasin Gishu",
  "Elgeyo-Marakwet",
  "Nandi",
  "Baringo",
  "Laikipia",
  "Nakuru",
  "Narok",
  "Kajiado",
  "Kericho",
  "Bomet",
  "Kakamega",
  "Vihiga",
  "Bungoma",
  "Busia",
  "Siaya",
  "Kisumu",
  "Homa Bay",
  "Migori",
  "Kisii",
  "Nyamira",
  "Nairobi City",
] as const;

export type KenyaCounty = (typeof KENYA_COUNTIES)[number];

/** Sorted for display. The schedule order means nothing to a farmer. */
export const COUNTIES_ALPHABETICAL = [...KENYA_COUNTIES].sort((a, b) =>
  a.localeCompare(b)
);

/**
 * Tolerant match against the list — handles a stored value that was typed
 * free-text before county became a picker ("nyeri", "Nyeri County").
 */
export function normaliseCounty(value: string | undefined): string | undefined {
  if (!value) return undefined;
  const cleaned = value.trim().replace(/\s+county$/i, "").toLowerCase();
  return KENYA_COUNTIES.find((county) => county.toLowerCase() === cleaned);
}
