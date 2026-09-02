# Backend and database design

Status: proposed, 2 September 2026. Covers `backend/` and `database/` only. The
frontend is owned by another team member; the contract between us is
[api-contract.md](api-contract.md).

---

## 1. Decisions landed

Filling in the *Stack — TBD* section of [CLAUDE.md](../../CLAUDE.md).

| Concern | Decision | Why |
|---|---|---|
| Backend language | Python 3.12+ | The rules engine stays Python; one language for engine and API. |
| Web framework | FastAPI + Pydantic v2 | The request/response models *are* the frontend contract, and generate OpenAPI for free. |
| Package manager | `uv` | Lockfile, fast cold installs, one tool for venv + deps. |
| Test runner | `pytest` (+ `hypothesis` for the allocation maths) | Golden-case tables and property tests both fit. |
| Lint / format | `ruff` (lint + format) + `mypy --strict` on `engine/` | The engine is the part where a type error costs a farmer money. |
| Database | Supabase Postgres 15+ | Managed, migrations via the Supabase CLI, and no ORM. |
| DB driver | `psycopg` 3, plain SQL | The backend runs about three queries. An ORM would be more machinery than schema. |
| Deployment | Container (Fly.io / Render / Cloud Run) + managed Supabase | Backend is stateless, so scaling is trivial. |

Rejected: SQLAlchemy (no object graph to map), Django (batteries we don't want),
a rules-engine library (they all invite non-determinism), Redis (the hot data is
one JSON document held in process memory).

---

## 2. The determinism model

The product promise is that the same inputs always yield the same verdict,
because a farmer is betting bus fare on it. Four mechanisms hold that up.

**Compiled rule packs.** Policy is *authored* in normalized Postgres tables, but
the engine never reads them. `kh.compile_pack()` flattens a scheme + season into
one self-contained JSON document; `kh.build_rule_pack()` stores it with a SHA-256
checksum; `kh.publish_rule_pack()` freezes it. A published pack is immutable —
triggers reject any UPDATE to its payload and any DELETE. Amending policy means
building version *n+1*, never editing *n*.

Every response carries `rule_pack_version`. Given that version and the echoed
inputs, any verdict is replayable forever.

**A pure engine.** `backend/src/kilimo_hakika/engine/` imports the standard
library and nothing else — no FastAPI, no psycopg, no `httpx`, and no
`datetime.now()`. The clock and the pack are arguments. A test enforces this by
walking the AST of every module in the package and failing on a forbidden
import or a wall-clock call. That is what keeps the engine testable in isolation
and honest about its inputs.

**Fail closed.** Any state the engine cannot resolve produces `DO_NOT_TRAVEL`
with `reason_kind` naming the gap — unknown depot, no season effective on the
travel date, a pack whose checksum does not match. The one direction the system
is allowed to be wrong in is the one that costs a farmer a bus fare instead of a
wasted journey and a lost day.

**No model, ever, in the verdict path.** No ML, no scoring, no LLM. The engine
is `evaluate(pack, input) -> TriageResult`: a predicate walk and two
multiplications.

### Why Postgres at all, if the engine reads JSON?

Because policy needs an *editor*, not a file. The tables give effective-dating
with a non-overlap constraint, referential integrity between rules, documents
and depots, `NOT NULL` citations, review history, and a publish gate. The JSON
gives the engine a frozen artifact. `database/scheme_rules.json` is the
committed compiled output of the development fixture — it lets the engine boot
and be unit-tested with no database at all, which is also the offline fallback
if Supabase is unreachable at startup.

---

## 3. Data layer

Full DDL: [`database/migrations/`](../../database/migrations). Fixture:
[`database/seed/0001_nfsp_development_fixture.sql`](../../database/seed/0001_nfsp_development_fixture.sql).

Four schemas, one per module:

| Schema | Contents | Access model |
|---|---|---|
| `kh` | Statutory policy, rule packs, anonymous triage log | RLS forced, **no policies** — denies every non-owner role. The backend reads packs as a role that bypasses RLS. Never exposed to PostgREST. |
| `identity` | Users, organisations, roles, consent, audit, per-farmer history | RLS with policies, evaluated under the caller's own JWT |
| `market` | Supplier-declared prices, demand/supply signals | RLS with policies; publishing requires a verified organisation |
| `ai` | Conversations, recommendations, prompt versions, grounding corpus | RLS with policies; conversations gated on live `ASSISTANT_AI` consent |

`kh` is the odd one out on purpose. It holds no personal data and answers to no
individual caller, so the strictest possible posture — deny everything, read it
once at startup — costs nothing. The other three are reached under the caller's
identity so that row-level security is a live control rather than decoration
(see [auth-and-roles.md](auth-and-roles.md) §3).

The policy tables in `kh`:

| Table | Role |
|---|---|
| `citation` | One row per discrete published statement, with the quote it carries. `source_type` runs `GAZETTE` → `CIRCULAR` → `AGENCY_FAQ` → `AGENCY_PUBLICATION` → `PRESS` → `UNVERIFIED`. |
| `county`, `depot`, `depot_hours`, `depot_closure` | Where a farmer can be served, and when. Hours and closures are data because "is it open on Saturday" is a policy question, not a code branch. |
| `document` | The physical artifacts. `is_physical = false` marks gate conditions that cannot be carried (being on the register). |
| `scheme`, `scheme_season` | Effective-dated policy. A GiST exclusion constraint forbids overlapping seasons in one scheme — two applicable rule sets would mean no deterministic verdict. |
| `allocation_rule` | Bags per acre, cap, rounding, cap split. One row per season. |
| `fertilizer_type`, `price` | The gazetted price per bag, per season, per purpose. |
| `rule` | The gate rules. `severity` decides the verdict; `applies_when` decides relevance. |
| `rule_pack` | The compiled immutable snapshot. One active pack per scheme, enforced by a partial unique index. |
| `triage_log` | Insert-only audit trail. |

### Citation discipline, enforced by the machine

CLAUDE.md says a rule without a citation is not a rule. Two mechanisms make that
mechanical rather than cultural:

1. `rule.citation_id`, `price.citation_id`, `allocation_rule.citation_id`,
   `scheme_season.citation_id` and the depot tables are all `NOT NULL` foreign
   keys. You cannot insert an uncited rule.
2. `kh.publish_rule_pack()` refuses to publish when any **BLOCKER** rule, any
   **price**, the **allocation rule** or the **season window** cites an
   `UNVERIFIED` source. Advisories may cite `UNVERIFIED` and are surfaced as
   advisories.

That gate is why the fixture cannot be published: its season dates are invented,
and its per-product prices come from press reporting rather than the season
circular. Replacing those citations is a prerequisite for going live, and the
database will keep saying so.

Known limitation: one rule carries exactly one citation. Real policy sometimes
rests on two sentences. If that bites, add a `rule_citation` join table — the
pack shape becomes `"citations": [...]` per rule and the engine's trace widens.

---

## 4. The predicate DSL

`rule.applies_when` is a closed, declarative predicate. No expressions, no
`eval`, no user-supplied code paths. `null` means the rule always applies.

**Input vocabulary** — the only fields a predicate may name:

| Field | Type | Source |
|---|---|---|
| `acreage_acres` | number | farmer input |
| `depot_code` | string | farmer input |
| `land_tenure` | `OWNED` / `LEASED` / `FAMILY_UNREGISTERED` / `UNKNOWN` | farmer input |
| `held_documents` | set of document codes | farmer input |
| `travel_date` | ISO date | farmer input, defaults to today in Africa/Nairobi |
| `collecting_in_person` | boolean | farmer input, defaults `true` |
| `registration_county_code` | string or null | farmer input, optional |
| `depot_county_code` | string | derived from the pack |
| `travel_weekday` | 1–7, Monday = 1 | derived from `travel_date` |
| `depot_open_on_travel_date` | boolean | derived from pack hours + closures |

**Operators:** `all`, `any`, `not` for composition; `eq`, `ne`, `in`, `not_in`,
`gt`, `gte`, `lt`, `lte` for values; `is_known` for optional fields;
`eq_field` / `ne_field` to compare two input fields; `has_document` /
`missing_document` for the held set.

An unknown field name or operator is a **pack validation error at load time**,
not a runtime shrug — a bad pack is rejected before it can serve a verdict.

**`DOCUMENT` rule semantics.** A `DOCUMENT` rule fails when its `document` is
absent from `held_documents`. `applies_when` only decides whether the
requirement is in play. So "a chief's letter, but only on leased land" is
`applies_when: {"field":"land_tenure","in":["LEASED","FAMILY_UNREGISTERED"]}`
with no mention of the document itself. `ELIGIBILITY`, `TEMPORAL` and
`LOGISTICS` rules fire when `applies_when` matches, or unconditionally if null.

---

## 5. The verdict algorithm

```
evaluate(pack, input, clock) -> TriageResult
```

1. **Validate the pack** — checksum, contract version, every predicate field and
   operator known. Failure → `DO_NOT_TRAVEL`, `reason_kind = PACK_INVALID`.
2. **Resolve the depot** from `depot_code`. Unknown or inactive →
   `DO_NOT_TRAVEL`, `reason_kind = DEPOT_UNKNOWN`.
3. **Resolve the season** for `travel_date`. None →
   `DO_NOT_TRAVEL`, `reason_kind = NO_EFFECTIVE_SEASON` with a plain-language
   message that the app has no published rules for that date, so do not travel
   on its word.
4. **Derive** `depot_county_code`, `travel_weekday`,
   `depot_open_on_travel_date` (a dated closure beats the weekly hours).
5. **Evaluate every rule** in `eval_order`. Collect matches into `blockers`
   (severity `BLOCKER`) and `advisories` (severity `ADVISORY`), each carrying
   its code, message, remedy, the document it names, and its citation.
6. **Verdict** = `PROCEED` if `blockers` is empty, else `DO_NOT_TRAVEL`.
   `reason_kind = READY` or `MISSING_REQUIREMENTS`.
7. **Compute allocation and costing unconditionally** — a farmer who is told
   "do not travel" still needs to know what to demand once they have fixed the
   gap, and what it should cost. Question 3 is answered on a "no".
8. **Emit a trace**: every rule evaluated, whether it matched, and why. This is
   what makes a disputed verdict auditable.

The result is a frozen dataclass. Nothing in step 5–8 touches I/O.

---

## 6. Allocation and costing

From the seeded `allocation_rule` (NCPB FAQ Q8):

```
per_acre    = planting_bags_per_acre + topdress_bags_per_acre     # 2 + 2
raw_bags    = round(acreage_acres * per_acre, rounding_mode)      # FLOOR
total_bags  = min(raw_bags, max_total_bags)                       # cap 100
planting/topdress split by cap_split                              # PRO_RATA
```

Every number above lives in the pack. Nothing is hardcoded in the engine — a cap
change is a JSON edit, as CLAUDE.md requires.

The three worked examples in NCPB's own FAQ are the golden tests, and this
formula reproduces all three: 3 acres → 12 bags, 15 acres → 60, over 25 → 100
(the 100-bag cap and the 4-bags-per-acre rate agree exactly at 25 acres, which is
a useful internal consistency check on any future edit).

`rounding_mode` is an **interpretation**, not gazetted: the source states a
per-acre rate and says nothing about 2.4 acres. `FLOOR` is the conservative
choice — never promise a bag the depot will not release — and it lives in data so
it can be corrected without a release.

### Costing without recommending

CLAUDE.md forbids fertilizer-choice advice, and question 3 demands the official
cost. The resolution: the response returns a **price table**, not a pick. Every
fertilizer priced for the season appears with its gazetted price per bag, the
farmer's bag entitlement, and the resulting subtotal. If the farmer names a
product, that line is flagged `selected: true` — but the engine never ranks,
recommends, or defaults to one.

`min_total_cost_kes` is included as the cheapest lawful combination, purely so
the farmer knows the floor an official could legitimately charge. It is labelled
as a floor, not a suggestion.

---

## 7. Backend layout

```
backend/
  pyproject.toml
  src/kilimo_hakika/
    api/
      main.py                 # app factory, middleware, error handlers
      routes/{triage,reference,health}.py       # the deterministic core
      routes/{profile,org,market,assistant}.py  # the surrounding modules
      schemas/                # Pydantic v2 DTOs == the frontend contract
      deps.py                 # require("<permission>") dependency, JWT verification
    engine/                   # PURE: stdlib only, no clock, no I/O
      types.py                # frozen dataclasses: TriageInput, TriageResult, ...
      pack.py                 # load + validate a pack dict
      predicates.py           # the DSL evaluator
      allocation.py           # bags
      costing.py              # money
      evaluate.py             # the single entry point
    packs/
      repository.py           # fetch active pack from Postgres, verify checksum,
                              # cache in memory, fall back to scheme_rules.json
    persistence/
      db.py                   # psycopg pool; per-request RLS session helper
      triage_log.py           # insert-only writer
    assistant/
      client.py               # Anthropic client, cached prompt prefix assembly
      tools.py                # the four read-only tools
      corpus.py               # rebuild ai.knowledge_chunk on pack publish
    settings.py               # pydantic-settings, env only
  tests/
    engine/                   # no DB, no network; golden cases + properties
    api/
    fixtures/packs/
```

The dependency rule is one-directional: `api` → `packs`/`persistence` → `engine`.
Nothing imports `api`.

**Pack lifecycle at runtime.** On startup the process reads the active pack for
the scheme, recomputes SHA-256 over the exact `payload::text` returned by
Postgres, compares it to the stored checksum, validates it, and holds it in
memory. A background refresh re-checks every five minutes; a failed refresh
keeps the last good pack and logs loudly. No request ever reads rules from the
database, so a database outage degrades to "serving the last known policy",
never to a wrong verdict.

---

## 8. API surface

Detailed in [api-contract.md](api-contract.md). The triage core is three
endpoints:

- `GET /api/v1/reference` — depots, counties, document checklist, fertilizers,
  active pack version. Cacheable; the client stores it for offline use.
- `POST /api/v1/triage` — the verdict.
- `GET /api/v1/health` — liveness plus loaded pack version and checksum.

Around them sit the identity, market and assistant endpoints. **A login is
required** to run a triage (owner decision, 2 September 2026) — see
[auth-and-roles.md](auth-and-roles.md) for the flows, the permission matrix and
the personal-data consequences.

The frontend does **not** talk to Supabase directly for a verdict. A verdict has
one source. User-scoped reads and writes do go through the backend under the
caller's own JWT, so RLS applies (see auth-and-roles.md §3).

---

## 9. Privacy and the audit log

`kh.triage_log` records `requested_at`, the pack version, the inputs, a hash of
the inputs, the verdict, the blocker codes, bag total and minimum cost. It
records **no** national ID, name, phone number or IP address, and — even though
accounts now exist — **no user id**.

That omission is deliberate. The farmer-facing history lives separately in
`identity.triage_history`, which links a user to a log row. Erasing a farmer
deletes that link and leaves the anonymous engine record intact, so a farmer's
right to be forgotten never costs us the ability to replay a disputed verdict.
Two tables, because the two records answer to different masters: one to the
farmer, one to correctness.

Why log at all: when a farmer says "it told me PROCEED and the gate turned me
away", the pack version plus the inputs replay the exact verdict, and that is how
a wrong rule gets found. Aggregate blocker counts also tell the Ministry which
missing artifact turns the most farmers away, which is the one genuinely useful
by-product of this system.

Retention is 90 days via `kh.prune_triage_log()`, on a daily Supabase cron. Data
minimisation and storage limitation under the Kenya Data Protection Act 2019.
The wider personal-data design — consent per purpose, HMAC'd ID numbers, the
append-only audit trail — is in [auth-and-roles.md](auth-and-roles.md) §4.

---

## 10. Supabase specifics

- **Migrations**: `supabase migration new <name>`, SQL under
  `database/migrations/`, applied with `supabase db push`. No ORM migrations.
- **Local dev**: `supabase start`, then the two migrations and the seed file.
- **Schema exposure**: keep `kh` out of the exposed schemas (Settings → API).
  Nothing in the product needs PostgREST.
- **Roles**: the backend uses a dedicated role with `USAGE` on `kh`, `SELECT` on
  the pack table and `INSERT` on `triage_log` — not the blanket `service_role`
  key. The `anon` key is never issued to anyone, because the browser never talks
  to the database.
- **Pooling**: connect through Supavisor in transaction mode; with psycopg 3 set
  `prepare_threshold=None`, since transaction pooling cannot hold prepared
  statements.
- **Secrets**: `.env`, git-ignored, with `.env.example` committed. The database
  password and any service key stay server-side only.

---

## 11. Testing

The engine needs tests before it needs polish, per CLAUDE.md.

1. **Golden cases** — a table of (input, expected verdict, expected blockers,
   expected bags, expected cost), including NCPB's three published worked
   examples and one case per rule in both directions.
2. **Property tests** (hypothesis) — bags never exceed `max_total_bags`; bags are
   monotonic in acreage; planting + topdress always equal the total; the verdict
   is `PROCEED` if and only if no blocker matched; `evaluate` is idempotent and
   order-independent across shuffled `held_documents`.
3. **Purity test** — AST walk over `engine/` asserting stdlib-only imports and no
   `datetime.now()` / `date.today()` / `time.time()`.
4. **Pack validation tests** — an unknown predicate field, an unknown operator,
   a bad checksum and a missing allocation rule must each be rejected at load.
5. **Migration tests** — apply migrations to a throwaway Postgres, run the seed,
   assert `kh.publish_rule_pack()` raises on the `UNVERIFIED` citations, and
   assert `kh.build_rule_pack()`'s payload equals `database/scheme_rules.json`
   with the `_`-prefixed annotation keys stripped. That last assertion is what
   stops the committed fixture drifting from the schema.
6. **Contract tests** — the OpenAPI schema is snapshotted, so a breaking change
   to the frontend contract fails CI rather than the frontend.

---

## 12. Invariant-compliance ledger

CLAUDE.md's original boundaries were rewritten on 2 September 2026 (marketplace
and AI are now in scope; payments are not). These are the invariants that
replaced them, and how the data layer holds each one up — structurally where
possible, because a boundary that depends on everyone remembering it is not a
boundary.

| Invariant | How the design enforces it |
|---|---|
| Deterministic verdict path | `engine/` imports stdlib only, has no database or network access, and takes its clock as an argument. There is nowhere for a model to interpose. The assistant reaches a verdict only through a tool call that records the `kh.triage_log` id. |
| Statutory and commercial prices never mix | Different schemas: `kh.price` carries a `citation_id`; `market.price_quote` carries an author and a `price_authority` column pinned to `SUPPLIER_DECLARED` by a CHECK constraint. No migration, admin console or code path can promote a supplier quote to official. |
| Every statutory rule cites its source | `NOT NULL` citation foreign keys, plus a publish gate that refuses `UNVERIFIED` sources behind any BLOCKER, price, allocation rule or season window. |
| No payments | No gateway, no transaction table, no order or cart anywhere in `market`. The one payment-adjacent rule states the statutory fact that cash is refused at the gate — displaying the rule, not moving money. |
| AI output is labelled and logged | `ai.recommendation` requires a model and prompt version on every row; `ai.message` requires them on every assistant turn; `ai.tool_invocation` requires a triage log id whenever the engine was consulted. |
| Suppliers cannot touch policy | No supplier role holds any `policy.*` permission, and `policy.author` / `review` / `publish` are never granted together to anyone — not even `platform_admin`. |
| Farmer PII stays minimal | Phone and email stay in `auth.users`. ID numbers are HMAC'd. Consent is per purpose and gates model calls at the RLS layer. |

One thing was considered and cut: a remaining-balance tracker. The season cap is
cumulative, the platform cannot see a farmer's prior draws without an NCPB
integration, and guessing would be worse than silence — so it ships as an
advisory telling the farmer to subtract what they have already collected.

---

## 13. Non-functional budget

- Verdict latency: p95 under 50 ms, since evaluation is in-memory.
- Triage response payload: under 8 KB gzipped. Farmers are on 2G; a fat JSON is a
  real cost. Full citation text is fetched only on demand, not inlined per rule.
- The backend is stateless; scale horizontally, no session affinity.
- Structured JSON logs to stdout and `logs/` (git-ignored), with the pack version
  on every line.

---

## 14. Open questions

These change the work; I have assumed an answer for each so nothing is blocked.

1. **Is `2026_SHORT_RAINS` the season to launch against, and what are its real
   gazetted dates?** Assumed a placeholder window and marked it `UNVERIFIED`,
   which blocks publishing until it is replaced.
2. **Can you get the season circular with the per-product price list?** Prices
   currently rest on press reporting. A wrong price defeats the anti-exploitation
   purpose of showing one, and the publish gate will not pass them.
3. **Is the chief's-letter requirement for leased land real, and is it a blocker
   or a soft ask?** Shipping as an advisory with an `UNVERIFIED` citation until
   traced; promoting it to `BLOCKER` will be refused by the publish gate.
4. **Is the full NCPB depot roster available in a machine-readable form?** Eight
   silo complexes are seeded; NCPB reports 110 depots across 46 counties, and a
   depot missing from the list reads to a farmer as "this app doesn't know my
   depot".
5. **Three inputs beyond the CLAUDE.md wizard** — travel date, land tenure, and
   registration county — each unlock a real turn-away cause (closed depot, lease
   proof, wrong county). All three degrade safely if omitted. Worth the extra
   wizard steps? The frontend contract treats them as optional.

## 15. Explicitly not in v1

Co-operative and farmer-organisation purchases (NCPB FAQ Q14 covers them, but
they need an organisation-registration input); SMS/USSD delivery of a verdict;
depot stock levels; any farmer account.
