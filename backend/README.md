# Kilimo Hakika (DepotReady) — Backend

A **deterministic Government Subsidy & Depot Triage Engine** for Kenyan farmers.

It answers one question before a farmer spends a day and a matatu fare
travelling to an NCPB depot: **will I actually be served?**

There is no model, no scoring and no randomness. Identical requests always
produce identical verdicts, and every rejection cites the circular clause it
rests on, so a Ward Agricultural Officer can audit any answer by hand.

---

## Quick start

```bash
cd backend

# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the server
uvicorn main:app --reload --port 8000
```

Then open **<http://localhost:8000/docs>**.

> **Note:** on the machine this was built on, ports 8000 and 8001 were already
> occupied by unrelated processes, so the live smoke test ran on `--port 8123`.
> If you see `[Errno 98] Address already in use`, pick another port:
> `uvicorn main:app --reload --port 8123`.

### For the frontend developer

| URL | What it is |
| --- | --- |
| <http://localhost:8000/docs> | **Swagger UI** — interactive, with a pre-filled "Try it out" example on `POST /api/triage` |
| <http://localhost:8000/redoc> | ReDoc — cleaner for reading the schemas |
| <http://localhost:8000/openapi.json> | Raw OpenAPI schema — feed this to a client generator |
| <http://localhost:8000/api> | Machine-readable endpoint index |

CORS is open to **all origins**, so any dev server port (Vite 5173, CRA 3000,
Next 3000, …) connects without configuration. `allow_credentials` is
deliberately `False`: browsers reject a wildcard origin combined with
credentials, and that combination would silently break the frontend. The
service holds no sessions, cookies or personal records, so nothing needs them.

---

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness plus a count of the reference data loaded |
| `GET` | `/api/geo/hierarchy` | Full County → Constituency → Ward tree for cascading dropdowns |
| `GET` | `/api/geo/counties` | Flat county list (lighter first dropdown) |
| `GET` | `/api/geo/wards?county=&constituency=` | Wards of one constituency |
| `GET` | `/api/depots?county=&serving_only=` | Gazetted NCPB depots, filterable |
| `GET` | `/api/depots/{depot_id}` | One depot |
| `GET` | `/api/schemes/current` | The gazetted circular: pricing, allocation, checklists, rejection criteria |
| `POST` | `/api/triage` | **The core engine** — `PROCEED` / `DO_NOT_TRAVEL` |

### Suggested frontend flow

1. `GET /api/geo/hierarchy` → populate the three cascading dropdowns.
2. `GET /api/depots?county={selected}` → depot picker.
3. `GET /api/schemes/current` → render the cost table and document checklist
   from policy instead of hard-coding figures.
4. `POST /api/triage` → show the verdict.

### Name matching is forgiving

County, constituency, ward, depot, document and crop names are matched
case-, spacing- and punctuation-insensitively. `"Moi's Bridge"`,
`"MOI'S BRIDGE"` and `"mois bridge"` all resolve to the same ward. Matching is
**exact on a normalized key**, never fuzzy, so determinism is preserved. Every
level of the hierarchy also ships a `lookup_key` if you want to pre-normalize
client-side.

---

## `POST /api/triage`

### Request

```json
{
  "county": "Uasin Gishu",
  "constituency": "Soy",
  "ward": "Moi's Bridge",
  "target_depot_id": "ncpb_eldoret",
  "acreage": 4.5,
  "crop_type": "maize",
  "documents_held": [
    "Original National ID",
    "KIAMIS E-Voucher SMS Code",
    "Signed Ward Agricultural Officer (WAO) Form"
  ],
  "is_land_leased": false,
  "has_stamped_lease": false
}
```

`documents_held`, `is_land_leased` and `has_stamped_lease` may be omitted; they
default to the conservative case (nothing held, not leased), so an incomplete
request can never earn an undeserved `PROCEED`.

`documents_held` accepts canonical codes (`original_national_id`), official
labels (`Original National ID`) or aliases (`national id`, `kitambulisho`).
Disqualifying items can be declared here too — `"ID Photocopy"`,
`"expired voucher"` — and raise the matching rejection criterion.

### Response

The four specified blocks, plus additive detail for the UI:

```json
{
  "verdict":              { "will_be_served": true, "status": "PROCEED", "summary": "..." },
  "gap_analysis":         { "missing_documents": [], "rejection_reasons": [] },
  "financial_breakdown":  { "allocated_bags": 18, "price_per_bag": 2500,
                            "total_cost_kes": 45000, "statutory_notice": "..." },
  "policy_grounding":     { "circular": "MOALD Circular 2026/02",
                            "depot_status": "ACTIVE - Open and issuing subsidised fertilizer",
                            "operating_procedure": "NCPB Operating Circular 4B" },

  "resolved_location":    { "county": "Uasin Gishu", "county_code": 27, "ward_id": 701, "...": "" },
  "depot":                { "...": "full depot record" },
  "document_checklist":   [ { "code": "...", "label": "...", "required": true, "held": true } ],
  "allocation_basis":     { "...": "the arithmetic, for auditability" },
  "alternative_depots":   [ ],
  "declared_crop":        "maize",
  "crop_within_gazetted_scope": true,
  "next_steps":           [ "..." ],
  "compliance":           { "no_agronomic_advice": "...", "no_payments": "...", "no_marketplace": "..." }
}
```

`document_checklist` is the easiest thing to render as a tick list.
`next_steps` is an ordered, purely procedural to-do list.

### Two behaviours worth knowing

**Blockers are never short-circuited.** A farmer missing two documents at a
closed depot is told all three problems at once, so a single follow-up trip
fixes everything.

**Entitlement is always reported**, even on `DO_NOT_TRAVEL`, because the farmer
still needs to know what they are owed once the blockers clear.

### Status codes

| Code | Meaning |
| --- | --- |
| `200` | A verdict was produced. **`DO_NOT_TRAVEL` is a 200**, not an error |
| `404` | `target_depot_id` does not exist |
| `422` | Location unresolvable, field validation failed, or the request sought agronomic advice |

`422`/`404` bodies carry `detail.field`, `detail.message` and often
`detail.valid_options`, so a form can highlight the offending input directly.

---

## The policy it applies

From `data/scheme_rules.json` — `MOALD Circular 2026/02 & NCPB Operating Circular 4B`.

**Pricing** — KES 2,500 per 50kg bag (statutory).

**Allocation** — 2 bags planting + 2 bags top-dressing per acre = 4 bags/acre,
floored to whole bags, capped at **100 bags per farmer** (reached at 25 acres).
Flooring is deliberate: fertilizer is issued only in sealed bags, and flooring
prevents over-allocation of a capped public subsidy. Below 0.25 acres no whole
bag is due and the farmer cannot be served.

**Mandatory documents** — Original National ID · KIAMIS E-Voucher SMS Code ·
Signed Ward Agricultural Officer (WAO) Form.

**Leased land** — additionally requires an Official Chief's Stamped Lease
Agreement.

**Rejection criteria** — ID photocopies (NCPB 4B §2.1) · expired vouchers
(§2.4) · unstamped lease agreements (§3.2).

**Depot readiness** — the depot must be `ACTIVE` *and* have the farmer's county
in its gazetted catchment. Catchments cross county lines, so a Nandi farmer may
legitimately collect at NCPB Eldoret in Uasin Gishu.

---

## Track compliance

**1 · No agronomic advice.** No crop, soil, seed or fertilizer recommendations
anywhere. `crop_type` is used for exactly one thing: confirming the holding
falls inside the circular's gazetted crop schedule — a statutory scope fact.
A `crop_type` phrased as an agronomy question (`"what fertilizer is best for
maize?"`) is **refused with HTTP 422** and redirected to the Ward Agricultural
Officer, rather than answered. Enforced in `app/compliance.py` and asserted in
`tests/test_api.py`.

**2 · No payments / e-commerce.** No M-Pesa, mobile money, card or banking
integration exists — there is no payment client and no credentials in the
codebase. `financial_breakdown` publishes statutory prices for planning only;
payment happens in person at the NCPB counter. A test asserts no
payment-shaped route can be added by accident.

**3 · No marketplace.** No buying, selling, bidding or third-party vendor
listings. Only gazetted Government (NCPB) depots appear, including in
`alternative_depots`, which is depot routing rather than a vendor list.

Constraints 2 and 3 are *structural* — the capability is absent, not merely
disabled. Every triage response also carries a `compliance` block stating these
boundaries, so the limits are visible to any client, not just documented here.

---

## Verification

```bash
# Full test suite — 141 tests
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest

# Readable end-to-end walkthrough — 61 checks, passing + failing triage cases
.venv/bin/python verify.py                              # in-process, no server needed
.venv/bin/python verify.py --url http://localhost:8000  # against a running server
```

`verify.py` prints what it asserted, so its output doubles as a demo of the
engine. Both suites cover a passing case, a failing case, the allocation cap,
sub-minimum acreage, closed depots, out-of-catchment depots, leased land with
and without a stamped lease, alias tolerance, determinism across repeated
calls, and all three track constraints.

Test layout:

| File | Covers |
| --- | --- |
| `tests/test_data_quality.py` | Reference-data integrity; locks in every defect the normalizer removes |
| `tests/test_triage.py` | The engine's decision rules |
| `tests/test_api.py` | HTTP contract, status codes, CORS, OpenAPI, compliance |

---

## Layout

```
backend/
├── main.py                      FastAPI app, CORS, router wiring
├── requirements.txt             runtime dependencies
├── requirements-dev.txt         + pytest, httpx
├── pytest.ini
├── verify.py                    end-to-end verification / demo script
├── app/
│   ├── config.py                paths, CORS, the three track constraints
│   ├── repository.py            data loading, indexes, tolerant name resolution
│   ├── schemas.py               Pydantic models = the OpenAPI contract
│   ├── compliance.py            agronomic-advice refusal guard
│   ├── triage.py                the deterministic engine
│   └── routers/                 health · geo · depots · schemes · triage
├── data/
│   ├── counties.json            47 / 290 / 1450, normalized  (generated)
│   ├── data_quality_report.json audit trail of the cleanup    (generated)
│   ├── scheme_rules.json        the gazetted circular
│   └── ncpb_depots.json         56 depots, catchments, statuses
└── scripts/
    └── build_data.py            the normalizer
```

No database. The reference data is static gazetted material, loaded once at
import and held in memory. There is no write path in the service.

---

## Reference data

`data/counties.json` is **generated** — regenerate with:

```bash
python scripts/build_data.py
```

It is built from the two files in the repository root, with
`csv-Kenya-Counties-Constituencies-Wards.csv` as the structural authority.
That CSV is internally consistent: 47 / 290 / 1450, contiguous ward IDs
1–1450, no duplicate ward names within a constituency, no stray whitespace.

`county.json` was audited and rejected as the backbone because it carries:

- **Stray whitespace** — 18 cases, e.g. `"  Tsimba Golini"`, `"Tharaka "`
- **A duplicate constituency** — Nyeri `"Tetu"` listed twice with identical wards
- **Merged ward names** — two wards fused into one string:
  - `"MATAYOS SOUTHBUSIBWABO"` → `Matayos South` + `Busibwabo`
  - `"MARACHI WESTKINGANDOLE"` → `Marachi West` + `Kingandole`
- **Shouted casing** — 74 cases; whole blocks of Busia and Kisii wards
- **Wards on the wrong constituency** — Kakamega `Shinyalu` is populated with
  Lugari's wards; Siaya `Ugenya` holds Rarieda's wards

Rebuilding from the CSV removes every one of those classes at the source
rather than patching them individually. `county.json` is still loaded during
the build so the run can *prove* the defects are gone; the evidence lands in
`data/data_quality_report.json`.

Two defects in the CSV itself were repaired, both recorded in that report:

- All five Baringo North rows carried the literal `#N/A` as their constituency
  ID. The correct value is unambiguous — Tiaty is 157, Baringo Central is 159,
  and **158** was the only gap in the otherwise contiguous 1–290 sequence.
- A small curated table fixes clear typos, e.g. `NJABINI\KIBURU` (backslash
  used as a separator) and `DEDAN KIMANTHI` → `Dedan Kimathi`.

Title casing preserves Kenyan orthography: Swahili particles stay lowercase
(`Mji wa Kale/Makadara`, `Ziwa la Ng'ombe`), the velar-nasal apostrophe does
not capitalize what follows (`Ang'urai North`, `Moi's Bridge`), quoted single
letters do (`Manyatta 'B'`), and hyphens and Roman numerals survive
(`Iria-Ini`, `Umoja II`, `Dandora Area III`).

The build script **asserts** the 47 / 290 / 1450 totals, ID contiguity and the
absence of every defect class, so it fails loudly rather than emitting damaged
data. `tests/test_data_quality.py` re-checks the same invariants against the
committed file.

### Not used

`geoBoundaries-KEN-ADM3_simplified.geojson` (3 MB of ward polygons) is not
loaded. Nothing in the triage rules is geometric — depot eligibility is decided
by gazetted **catchment lists**, not distance or point-in-polygon. Serving 3 MB
per request on a rural mobile connection would cost more than it delivers. It
is available if the frontend later wants a choropleth; serve it as a static
asset rather than through this API.

Depot records deliberately carry **no GPS coordinates**. Inventing plausible
ones for a triage tool a farmer will act on would be fabricating data. Add them
only from an authoritative NCPB source.
