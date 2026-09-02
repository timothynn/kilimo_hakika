/**
 * Server-side client for the FastAPI verdict engine (`backend/`, `app/` + `main.py`).
 *
 * This is the single source of truth for verdicts. The TypeScript engine in
 * `src/lib/triage/` no longer answers `/api/triage`; it survives only as a
 * tested reference implementation of the same statutory math. See
 * `docs/design/integration.md`.
 *
 * Only ever imported from server code, so the upstream URL never reaches the
 * browser.
 */

const DEFAULT_BASE_URL = "http://127.0.0.1:8000";

/**
 * Every upstream call is bounded. Without this a hung backend hangs the
 * farmer's wizard forever behind a spinner, which is worse than an error: they
 * cannot tell whether to wait or to give up.
 */
const TIMEOUT_MS = 8000;

export function triageApiBaseUrl(): string {
  const raw = process.env.KILIMO_TRIAGE_API_URL?.trim();
  return (raw || DEFAULT_BASE_URL).replace(/\/$/, "");
}

export class DepotApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly detail?: unknown,
    /** True when we never got an answer at all, as opposed to a refusal. */
    readonly unreachable = false,
  ) {
    super(message);
    this.name = "DepotApiError";
  }
}

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const url = `${triageApiBaseUrl()}${path}`;

  let response: Response;
  try {
    response = await fetch(url, {
      ...init,
      headers: { "Content-Type": "application/json", ...init.headers },
      signal: AbortSignal.timeout(TIMEOUT_MS),
      // A verdict must never come from a cache.
      cache: "no-store",
    });
  } catch (cause) {
    const timedOut = cause instanceof Error && cause.name === "TimeoutError";
    throw new DepotApiError(
      timedOut
        ? `The verdict service did not answer within ${TIMEOUT_MS / 1000} seconds.`
        : "The verdict service could not be reached.",
      503,
      String(cause),
      true,
    );
  }

  const text = await response.text();
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      throw new DepotApiError("The verdict service returned malformed JSON.", 502);
    }
  }

  if (!response.ok) {
    const detail = (body as { detail?: unknown } | null)?.detail;
    throw new DepotApiError(
      messageFromDetail(detail) ?? `The verdict service returned ${response.status}.`,
      response.status,
      detail,
    );
  }
  return body as T;
}

function messageFromDetail(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "message" in detail) {
    const message = (detail as { message?: unknown }).message;
    if (typeof message === "string") return message;
  }
  return null;
}

// ---------------------------------------------------------------------------
// Response shapes (the subset the UI uses)
// ---------------------------------------------------------------------------

export type ApiCounty = {
  county_code: number;
  county_name: string;
  constituency_count: number;
  ward_count: number;
};

export type ApiConstituency = {
  constituency_id: number;
  constituency_name: string;
  ward_count: number;
};

export type ApiWard = { ward_id: number; ward_name: string };

export type ApiDepot = {
  depot_id: string;
  name: string;
  town: string;
  county: string;
  region: string;
  status: string;
  status_label: string;
  serves_farmers: boolean;
  catchment_counties: string[];
  operating_hours: string;
  notes: string;
};

export type ApiTriageRequest = {
  county: string;
  constituency: string;
  ward: string;
  target_depot_id: string;
  acreage: number;
  documents_held: string[];
  is_land_leased: boolean;
  has_stamped_lease: boolean;
};

export type ApiTriageResponse = {
  verdict: { will_be_served: boolean; status: "PROCEED" | "DO_NOT_TRAVEL"; summary: string };
  gap_analysis: { missing_documents: string[]; rejection_reasons: string[] };
  financial_breakdown: {
    allocated_bags: number;
    price_per_bag: number;
    total_cost_kes: number;
    statutory_notice: string;
  };
  policy_grounding: {
    circular: string;
    depot_status: string;
    operating_procedure: string;
  };
  payment_notice: {
    headline: string;
    notice: string;
    accepted_means: string[];
    authority: string;
    cash_accepted_at_depot: boolean;
  };
  resolved_location: {
    county: string;
    county_code: number;
    constituency: string;
    constituency_id: number;
    ward: string;
    ward_id: number;
  };
  depot: ApiDepot;
  document_checklist: {
    code: string;
    label: string;
    required: boolean;
    held: boolean;
    requirement_type: string;
    authority: string;
  }[];
  allocation_basis: {
    declared_acreage: number;
    bags_per_acre: number;
    planting_bags_per_acre: number;
    top_dressing_bags_per_acre: number;
    uncapped_entitlement_bags: number;
    max_bags_per_farmer: number;
    cap_applied: boolean;
    explanation: string;
  };
  alternative_depots: ApiDepot[];
  next_steps: string[];
  compliance: Record<string, string>;
};

// ---------------------------------------------------------------------------
// Calls
// ---------------------------------------------------------------------------

export function getCounties(): Promise<{ count: number; counties: ApiCounty[] }> {
  return call("/api/geo/counties");
}

export function getConstituencies(
  county: string,
): Promise<{ county: string; constituencies: ApiConstituency[] }> {
  return call(`/api/geo/constituencies?county=${encodeURIComponent(county)}`);
}

export function getWards(
  county: string,
  constituency: string,
): Promise<{ wards: ApiWard[] }> {
  return call(
    `/api/geo/wards?county=${encodeURIComponent(county)}` +
      `&constituency=${encodeURIComponent(constituency)}`,
  );
}

export function getDepots(county?: string): Promise<{ count: number; depots: ApiDepot[] }> {
  const query = county ? `?county=${encodeURIComponent(county)}` : "";
  return call(`/api/depots${query}`);
}

export function getScheme(): Promise<Record<string, unknown>> {
  return call("/api/schemes/current");
}

export function runTriage(input: ApiTriageRequest): Promise<ApiTriageResponse> {
  return call("/api/triage", { method: "POST", body: JSON.stringify(input) });
}

export async function isReachable(): Promise<boolean> {
  try {
    await call("/health");
    return true;
  } catch {
    return false;
  }
}
