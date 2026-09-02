/**
 * Server-side client for the Python triage service (`backend/`).
 *
 * Why this exists: there are two rules engines in this repo right now — the
 * TypeScript one in `src/lib/triage/` and the Python one in `backend/`. Two
 * engines means two verdicts for the same farmer, which is the one failure this
 * product cannot survive, so the Python engine is being made the single source
 * of truth (it holds the citation publish gate, the effective-dated seasons,
 * the depot-hours and county rules, and the audit trail).
 *
 * The migration is deliberately reversible: set `KILIMO_API_URL` and
 * `/api/triage` delegates to Python; leave it unset and the local TypeScript
 * engine answers exactly as before. See docs/design/integration.md.
 *
 * Only ever imported from server code, so no token or upstream URL reaches the
 * browser.
 */

export type ApiFinding = {
  code: string;
  document_code: string | null;
  label: string | null;
  message: string;
  remedy: string | null;
  citation: string | null;
  citation_is_unverified: boolean;
};

export type ApiTriageResponse = {
  verdict: "PROCEED" | "DO_NOT_TRAVEL";
  reason_kind: string;
  headline: string;
  summary: string;
  blockers: ApiFinding[];
  advisories: ApiFinding[];
  allocation: {
    acreage_acres: number;
    planting_bags: number;
    topdress_bags: number;
    total_bags: number;
    bag_weight_kg: number;
    cap_applied: boolean;
    max_total_bags: number;
    basis: string;
    citation: string;
  } | null;
  costing: {
    currency: string;
    min_total_cost_kes: number | null;
    lines: {
      fertilizer_code: string;
      fertilizer_name: string;
      purpose: string;
      bags: number;
      price_kes_per_bag: number;
      subtotal_kes: number;
      selected: boolean;
      citation: string;
      citation_is_unverified: boolean;
    }[];
  } | null;
  depot: {
    code: string;
    name: string;
    county_code: string;
    county_name: string;
    open_on_travel_date: boolean;
    opens_at: string | null;
    closes_at: string | null;
  } | null;
  history_id: string | null;
  meta: {
    rule_pack_version: string;
    engine_version: string;
    season_code: string | null;
    travel_date: string;
    pack_source: string;
    environment: string;
  };
};

export type ApiReference = {
  rule_pack_version: string;
  environment: string;
  season: { code: string; label: string; effective_from: string; effective_to: string };
  counties: { code: string; name: string }[];
  depots: {
    code: string;
    name: string;
    county_code: string;
    county_name: string;
    open_days: number[];
    opens_at: string | null;
    closes_at: string | null;
  }[];
  documents: {
    code: string;
    label: string;
    how_to_obtain: string | null;
    is_physical: boolean;
    relevance: "ALWAYS" | "CONDITIONAL";
  }[];
  fertilizers: { code: string; name: string }[];
  allocation: { min_acres: number; max_total_bags: number; bag_weight_kg: number };
};

export class KilimoApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string,
  ) {
    super(message);
    this.name = "KilimoApiError";
  }
}

export function apiBaseUrl(): string | null {
  const raw = process.env.KILIMO_API_URL?.trim();
  return raw ? raw.replace(/\/$/, "") : null;
}

export function isDelegating(): boolean {
  return apiBaseUrl() !== null;
}

async function call<T>(
  path: string,
  init: RequestInit & { token?: string | null } = {},
): Promise<T> {
  const base = apiBaseUrl();
  if (!base) {
    throw new KilimoApiError("KILIMO_API_URL is not set", 503, "NOT_CONFIGURED");
  }

  const { token, headers, ...rest } = init;
  const response = await fetch(`${base}${path}`, {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
    // Policy changes only when a rule pack is published, but a verdict must
    // never come from a cache.
    cache: "no-store",
  });

  const text = await response.text();
  const body = text ? JSON.parse(text) : null;

  if (!response.ok) {
    const detail = body?.detail?.error ?? body?.error;
    throw new KilimoApiError(
      detail?.message ?? `triage service returned ${response.status}`,
      response.status,
      detail?.code,
    );
  }
  return body as T;
}

export function getReference(lang = "en"): Promise<ApiReference> {
  return call<ApiReference>(`/api/v1/reference?lang=${lang}`);
}

export function runTriage(
  input: {
    depot_code: string;
    acreage_acres: number;
    held_documents: string[];
    land_tenure?: string;
    registration_county_code?: string | null;
    fertilizer_code?: string | null;
  },
  options: { token?: string | null; lang?: string } = {},
): Promise<ApiTriageResponse> {
  return call<ApiTriageResponse>(`/api/v1/triage?lang=${options.lang ?? "en"}`, {
    method: "POST",
    body: JSON.stringify(input),
    token: options.token ?? null,
  });
}

export function getHealth(): Promise<Record<string, unknown>> {
  return call<Record<string, unknown>>("/api/v1/health");
}
