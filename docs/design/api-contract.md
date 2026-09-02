# API contract v1

The interface between `frontend/` and `backend/`. Design rationale lives in
[backend-database.md](backend-database.md).

Base path `/api/v1`. JSON in, JSON out, UTF-8. All responses carry
`X-Rule-Pack-Version`.

**Authentication is required** on everything except `/reference` and `/health`.
Send the Supabase access token as `Authorization: Bearer <jwt>`. The client
obtains it from Supabase Auth directly (phone OTP for farmers, email for staff)
— the backend never sees a password or an OTP. Roles arrive in the token for UI
shaping only; the server re-checks every permission against the database, so a
revoked grant takes effect immediately. See
[auth-and-roles.md](auth-and-roles.md).

Language: pass `?lang=en` or `?lang=sw` (default `en`). Every farmer-facing
string is resolved server-side, so the frontend never assembles policy prose.

---

## `GET /api/v1/reference`

Everything the wizard needs to render itself. Cache it — it changes only when a
rule pack is published.

`Cache-Control: public, max-age=3600, stale-while-revalidate=86400`, plus an
`ETag`. Store the last successful response locally: the wizard must still render
its three steps with no network.

```json
{
  "rule_pack_version": "NFSP-2026_SHORT_RAINS-0001",
  "scheme": { "code": "NFSP", "name": "National Fertilizer Subsidy Programme" },
  "season": {
    "code": "2026_SHORT_RAINS",
    "label": "2026 Short Rains season",
    "effective_from": "2026-08-01",
    "effective_to": "2027-01-31"
  },
  "counties": [{ "code": "032", "name": "Nakuru" }],
  "depots": [
    {
      "code": "NCPB-NAKURU",
      "name": "Nakuru Depot",
      "county_code": "032",
      "county_name": "Nakuru",
      "open_days": [1, 2, 3, 4, 5],
      "opens_at": "08:00",
      "closes_at": "17:00"
    }
  ],
  "documents": [
    {
      "code": "NATIONAL_ID_ORIGINAL",
      "label": "Original National ID card (not a photocopy)",
      "how_to_obtain": "Replace a lost ID at your sub-county registration office...",
      "is_physical": true,
      "relevance": "ALWAYS"
    },
    {
      "code": "CHIEF_LETTER",
      "label": "Stamped letter from your Chief confirming you farm the land",
      "how_to_obtain": "Ask your Chief or Assistant Chief...",
      "is_physical": true,
      "relevance": "CONDITIONAL"
    }
  ],
  "fertilizers": [{ "code": "DAP", "name": "DAP (planting)" }],
  "land_tenures": [
    { "code": "OWNED", "label": "I own this land" },
    { "code": "LEASED", "label": "I lease this land" },
    { "code": "FAMILY_UNREGISTERED", "label": "Family land, not in my name" },
    { "code": "UNKNOWN", "label": "I would rather not say" }
  ]
}
```

`documents[].relevance` is `ALWAYS` when some rule requires the document
unconditionally and `CONDITIONAL` when it depends on other answers — render the
`ALWAYS` set as the step-3 checklist and reveal `CONDITIONAL` items once tenure
is known. Only documents named by a rule in the active pack are returned.

---

## `POST /api/v1/triage`

### Request

```json
{
  "acreage_acres": 2.5,
  "depot_code": "NCPB-NAKURU",
  "held_documents": ["NATIONAL_ID_ORIGINAL", "FARMER_REGISTER_ENTRY"],
  "land_tenure": "LEASED",
  "travel_date": "2026-09-04",
  "registration_county_code": "032",
  "collecting_in_person": true,
  "fertilizer_code": "DAP"
}
```

| Field | Required | Notes |
|---|---|---|
| `acreage_acres` | yes | `> 0`, `<= 10000`, at most 2 decimal places. |
| `depot_code` | yes | From `/reference`. Unknown code → `DO_NOT_TRAVEL`, not a 4xx. |
| `held_documents` | yes | Array of document codes; `[]` is valid and normal. Unknown codes are ignored, duplicates collapsed, order irrelevant. |
| `land_tenure` | no | Defaults `UNKNOWN`. |
| `travel_date` | no | Defaults to today in `Africa/Nairobi`; the resolved date is always echoed. Must be within 90 days. |
| `registration_county_code` | no | Omitted turns the county-match blocker into an advisory. |
| `collecting_in_person` | no | Defaults `true`. |
| `fertilizer_code` | no | Flags one costing line as `selected`. It never changes the verdict, and the API never picks one for the farmer. |

The backend re-validates all of it. The zod schema on the client is for
ergonomics; it is not trusted for a verdict.

### Response — `DO_NOT_TRAVEL`

```json
{
  "verdict": "DO_NOT_TRAVEL",
  "reason_kind": "MISSING_REQUIREMENTS",
  "headline": "Do not travel yet",
  "summary": "Two things are missing. Fix them before you spend money on transport.",
  "blockers": [
    {
      "code": "DOC_EVOUCHER_CODE",
      "document_code": "EVOUCHER_CODE",
      "label": "E-voucher code received by SMS",
      "message": "You need the e-voucher code sent to you by SMS. Without it the depot has nothing to redeem.",
      "remedy": "Check your SMS inbox before you travel. If no code has arrived, your registration is not yet verified.",
      "citation": "MOALD-NFSP-2025-LAUNCH"
    },
    {
      "code": "DOC_NON_CASH_PAYMENT_MEANS",
      "document_code": "NON_CASH_PAYMENT_MEANS",
      "label": "A way to pay without cash - M-Pesa on your own phone, or a bank deposit slip",
      "message": "Cash is not accepted at the depot, and you must pay before collecting...",
      "remedy": "Pay to the NCPB till number displayed at the depot...",
      "citation": "NCPB-FAQ-2022-10-Q10"
    }
  ],
  "advisories": [
    {
      "code": "ADVISORY_LEASED_LAND_PROOF",
      "document_code": "CHIEF_LETTER",
      "label": "Stamped letter from your Chief confirming you farm the land",
      "message": "Farmers on leased or unregistered family land are often asked for a stamped letter from the Chief...",
      "remedy": "Ask your Chief or Assistant Chief for a stamped letter.",
      "citation": "SEED-LEASED-LAND",
      "citation_is_unverified": true
    }
  ],
  "allocation": {
    "acreage_acres": 2.5,
    "planting_bags": 5,
    "topdress_bags": 5,
    "total_bags": 10,
    "bag_weight_kg": 50,
    "cap_applied": false,
    "max_total_bags": 100,
    "basis": "2 bags for planting and 2 for top dressing, per acre",
    "citation": "NCPB-FAQ-2022-10-Q8"
  },
  "costing": {
    "currency": "KES",
    "min_total_cost_kes": 20475.00,
    "lines": [
      {
        "fertilizer_code": "DAP",
        "fertilizer_name": "DAP (planting)",
        "purpose": "PLANTING",
        "bags": 5,
        "price_kes_per_bag": 2500.00,
        "subtotal_kes": 12500.00,
        "selected": true,
        "citation": "MOALD-NFSP-2025-LAUNCH"
      },
      {
        "fertilizer_code": "CAN",
        "fertilizer_name": "CAN (top dressing)",
        "purpose": "TOPDRESS",
        "bags": 5,
        "price_kes_per_bag": 2875.00,
        "subtotal_kes": 14375.00,
        "selected": false,
        "citation": "PRESS-PRICES-2025"
      }
    ]
  },
  "depot": {
    "code": "NCPB-NAKURU",
    "name": "Nakuru Depot",
    "county_name": "Nakuru",
    "open_on_travel_date": true,
    "opens_at": "08:00",
    "closes_at": "17:00"
  },
  "meta": {
    "rule_pack_version": "NFSP-2026_SHORT_RAINS-0001",
    "engine_version": "1.0.0",
    "season_code": "2026_SHORT_RAINS",
    "travel_date": "2026-09-04",
    "evaluated_at": "2026-09-02T09:14:03Z",
    "environment": "development-fixture"
  }
}
```

### Response — `PROCEED`

Identical shape. `blockers` is `[]`, `reason_kind` is `READY`, `headline` is
"You can travel". The frontend renders one result screen from one payload; it
never branches on anything but `verdict`.

### Contract guarantees

- `verdict` is exactly `PROCEED` or `DO_NOT_TRAVEL`. There is no third value and
  no `MAYBE`.
- `verdict == "PROCEED"` if and only if `blockers` is empty.
- `allocation` and `costing` are **always** present, including on a
  `DO_NOT_TRAVEL` — a farmer who is missing a document still needs to know the
  cap and the official price. Do not hide the cost panel behind a green verdict.
- `advisories` never affect `verdict`. Render them below the verdict, never as
  part of it.
- Every statutory number (`price_kes_per_bag`, `total_bags`, `max_total_bags`)
  arrives with a `citation`. Those are the only fields that get gazette brass.
- `citation_is_unverified: true` means the rule is not yet traced to a published
  source. Show it as an advisory, never as a hard requirement.
- Money is a JSON number with 2 decimal places, minor-unit exact. Format as
  `KES 20,475`; do not do arithmetic on it client-side.
- `reason_kind` values: `READY`, `MISSING_REQUIREMENTS`, `DEPOT_UNKNOWN`,
  `NO_EFFECTIVE_SEASON`, `PACK_INVALID`. The last three are fail-closed states —
  they return `DO_NOT_TRAVEL` with a `headline` explaining that the app cannot
  vouch for the trip, and `blockers` describing the gap. Treat them like any
  other red verdict.
- Additive changes (new fields, new rule codes, new documents) ship without a
  version bump. Removing or retyping a field means `/api/v2`.

### `GET /api/v1/citations/{id}`

The full citation record — title, issuer, source type, reference, URL, the
verbatim extract. Fetch on demand when a farmer taps a number to ask "who says
so"; keeping it out of the triage payload is what keeps that payload small on 2G.

---

## Errors

Only genuinely malformed requests get a 4xx. Anything that is a *policy* answer —
unknown depot, no season, expired pack — is a 200 with a red verdict, because
"do not travel" is the useful answer and an error screen is not.

```json
{ "error": { "code": "INVALID_INPUT", "message": "acreage_acres must be greater than 0", "field": "acreage_acres" } }
```

| Status | Code | When |
|---|---|---|
| 400 | `INVALID_INPUT` | Failed schema validation. |
| 422 | `TRAVEL_DATE_OUT_OF_RANGE` | More than 90 days out, or in the past. |
| 429 | `RATE_LIMITED` | Per-IP limit; `Retry-After` set. |
| 503 | `NO_ACTIVE_PACK` | No pack loaded at all. The client should show its cached reference data and say the service is unavailable — never guess a verdict. |

---

## `GET /api/v1/health`

```json
{
  "status": "ok",
  "rule_pack_version": "NFSP-2026_SHORT_RAINS-0001",
  "rule_pack_checksum": "9f2c...",
  "pack_loaded_at": "2026-09-02T08:00:00Z",
  "pack_source": "database",
  "engine_version": "1.0.0"
}
```

`pack_source` is `database` or `bundled_fixture`. A production instance serving
from `bundled_fixture` is an incident.

---

# Identity, market and assistant endpoints

Everything below requires a bearer token. A caller lacking the named permission
gets `403 FORBIDDEN` with the permission that was missing, so the client can
render an honest "you need X" rather than a dead button.

## Session and profile

### `GET /api/v1/me`

```json
{
  "user_id": "8f1c...",
  "display_name": "Wanjiku",
  "locale": "sw",
  "permissions": ["triage.run", "triage.history.read.self", "market.read", "assistant.chat"],
  "organisations": [
    { "id": "b2d1...", "name": "Rift Valley Agrovet", "kind": "RETAIL", "status": "VERIFIED", "roles": ["org_staff"] }
  ],
  "aal": "aal1",
  "consents": { "ACCOUNT": true, "ASSISTANT_AI": false, "ANALYTICS": true, "MARKET_NOTIFICATIONS": false },
  "farmer_profile": {
    "registration_county_code": "032",
    "default_acreage_acres": 2.5,
    "land_tenure": "LEASED",
    "kiamis_registered": true
  }
}
```

Drive the whole navigation from `permissions`. Do not infer capability from role
names — roles are bundles that will change, permissions are the contract. `aal`
is `aal1` for password/OTP-only and `aal2` once a TOTP factor is satisfied;
publishing prices and touching policy require `aal2`.

### `PUT /api/v1/me/profile` — permission `profile.write.self`

Body is the `farmer_profile` object above. These values pre-fill the triage
wizard, which is the point of asking a farmer to sign in: acreage, county and
tenure are answered once, not every season.

### `PUT /api/v1/me/consent`

```json
{ "purpose": "ASSISTANT_AI", "granted": true, "policy_version": "2026-09-01" }
```

Withdrawing `ASSISTANT_AI` stops assistant access at the database layer, not
just in the UI. `POST /api/v1/me/erasure` files an erasure request.

## Triage, with a session

`POST /api/v1/triage` keeps its shape, with two additions:

- Omitted `acreage_acres`, `land_tenure` and `registration_county_code` fall back
  to the caller's `farmer_profile`. The resolved values are always echoed in the
  response, so the result screen shows what was actually evaluated.
- The response gains `history_id`, the `identity.triage_history` row that the gap
  checklist below hangs off.

### `GET /api/v1/me/triage-history` — permission `triage.history.read.self`

```json
{
  "items": [
    {
      "history_id": "77aa...",
      "created_at": "2026-09-02T09:14:03Z",
      "verdict": "DO_NOT_TRAVEL",
      "depot_code": "NCPB-NAKURU",
      "total_bags": 10,
      "gap_state": { "EVOUCHER_CODE": "PENDING", "NON_CASH_PAYMENT_MEANS": "RESOLVED" }
    }
  ]
}
```

### `PATCH /api/v1/me/triage-history/{history_id}/gaps`

```json
{ "gap_state": { "EVOUCHER_CODE": "RESOLVED" } }
```

Values: `PENDING`, `RESOLVED`, `BLOCKED`. This is the tracking surface — a farmer
ticking off what they have since obtained. It never changes a stored verdict;
re-running triage is what produces a new one.

## Market

### `GET /api/v1/market/prices` — permission `market.read`

Query: `product`, `county`, `kind` (`RETAIL` / `WHOLESALE`), `on` (date).

```json
{
  "as_of": "2026-09-02",
  "quotes": [
    {
      "id": "c41f...",
      "product_code": "DAP",
      "product_name": "DAP (planting)",
      "price_kes": 4100.00,
      "unit": "BAG_50KG",
      "quote_kind": "RETAIL",
      "county_code": "032",
      "valid_from": "2026-09-01",
      "valid_to": "2026-09-30",
      "price_authority": "SUPPLIER_DECLARED",
      "organisation": { "id": "b2d1...", "name": "Rift Valley Agrovet", "kind": "RETAIL", "status": "VERIFIED" },
      "note": null
    }
  ]
}
```

**Rendering rules, not suggestions.** `price_authority` is always
`SUPPLIER_DECLARED` — the field exists so the client can never confuse these with
`kh` prices. A quote must be shown with its organisation's name attached, in body
text, in the ordinary foreground colour. It must never appear in gazette brass,
never be labelled official, gazetted, approved or a cap, and never share a table
with a statutory price without a heading that separates the two. The invariant is
in CLAUDE.md and the schema pins the column; this is the half of it that lives in
the UI.

### `GET /api/v1/market/signals` — permission `market.read`

```json
{
  "signals": [
    {
      "id": "91be...",
      "direction": "SUPPLY",
      "product_code": "DAP",
      "county_code": "026",
      "period_start": "2026-10-01",
      "period_end": "2026-11-30",
      "quantity": 12000,
      "unit": "BAG_50KG",
      "headline": "Additional DAP stock expected in Trans Nzoia from mid-October",
      "detail": null,
      "organisation": { "id": "aa10...", "name": "Supplier association name", "kind": "SUPPLIER_ASSOCIATION", "status": "VERIFIED" },
      "published_at": "2026-09-01T08:00:00Z"
    }
  ]
}
```

A signal is a notice. It carries no price, no counterparty and no accept action,
so there is nothing for the client to render as an offer.

### Publishing

| Endpoint | Permission | Notes |
|---|---|---|
| `POST /api/v1/market/prices` | `market.price.draft.own_org` | Creates a `DRAFT`. |
| `POST /api/v1/market/prices/{id}/publish` | `market.price.publish.own_org` + `aal2` | Refused if the organisation is not `VERIFIED`, or if it would overlap a live quote for the same product, unit, kind and county. |
| `POST /api/v1/market/prices/{id}/withdraw` | `market.price.publish.own_org` | |
| `POST /api/v1/market/signals` | `market.signal.publish.own_org` | |

`409 PRICE_OVERLAP` names the conflicting quote id: two live prices from one
organisation for one product is worse for a farmer than no price at all.

## Assistant

### `POST /api/v1/assistant/messages` — permission `assistant.chat`

Requires a live `ASSISTANT_AI` consent; without one the response is
`403 CONSENT_REQUIRED` with `"purpose": "ASSISTANT_AI"` so the client can prompt
for it.

Request: `{ "conversation_id": null, "text": "Nahitaji nini ili nipate mbolea?", "locale": "sw" }`

Streams Server-Sent Events:

```
event: message_start   data: {"conversation_id":"...","message_id":"..."}
event: text            data: {"delta":"Unahitaji ..."}
event: citation        data: {"cited_text":"appear in person ... original identity card","citation_id":"NCPB-FAQ-2022-10-Q3"}
event: tool_use        data: {"tool":"get_triage_verdict","triage_log_id":"..."}
event: message_stop    data: {"stop_reason":"end_turn","usage":{"input_tokens":8412,"output_tokens":246,"cache_read_input_tokens":8104}}
```

Contract guarantees for the assistant:

- **It never issues a verdict of its own.** If an answer states a verdict, a
  `tool_use` event for `get_triage_verdict` appeared in the same turn and the
  stated verdict matches that payload exactly. Render a verdict the assistant
  quotes with the same component as the triage result screen, never as prose.
- Every policy claim carries a `citation` event. Show the cited sentence on
  demand — `GET /api/v1/citations/{id}` returns the full record.
- Market figures in an answer name their organisation.
- `stop_reason` may be `refusal`. Show the fallback text; never surface an error
  screen for it.
- If the assistant is unavailable, everything else still works. It is a
  convenience layer over a product that must function without it.

### `GET /api/v1/assistant/recommendations`

```json
{
  "items": [
    {
      "id": "5d2a...",
      "kind": "GAP_PLAN",
      "body": "Start with the e-voucher: ...",
      "grounding_refs": ["NCPB-FAQ-2022-10-Q3", "MOALD-NFSP-2025-LAUNCH"],
      "model": "claude-opus-5",
      "generated": true,
      "created_at": "2026-09-02T09:15:00Z"
    }
  ]
}
```

`generated: true` is always present and always true. Recommendations render
**outside** the verdict panel, visibly labelled as generated, and never in
gazette brass. `POST /api/v1/assistant/recommendations/{id}/feedback` takes
`{ "accepted": true, "feedback": "..." }`.

## Additional error codes

| Status | Code | When |
|---|---|---|
| 401 | `UNAUTHENTICATED` | Missing, expired or unverifiable token. |
| 403 | `FORBIDDEN` | Authenticated but lacking the permission; the body names it. |
| 403 | `MFA_REQUIRED` | Permission held, but the action needs `aal2`. |
| 403 | `CONSENT_REQUIRED` | The body names the purpose. |
| 403 | `ORG_NOT_VERIFIED` | Publishing attempted from an unverified organisation. |
| 409 | `PRICE_OVERLAP` | The body names the conflicting quote. |
| 503 | `ASSISTANT_UNAVAILABLE` | Model API unreachable. Everything else keeps working. |
