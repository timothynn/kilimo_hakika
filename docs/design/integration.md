# Integration: three engines, one verdict

Status: 2 September 2026. Written after merging `feat/depot-registry` (PR #4),
then revised after PR #5 merged a *second* Python triage service into
`backend/` while this one was being written.

## The headline

**Three rules engines now exist in this repo and they do not agree.** Asked
about 2.5 acres at NCPB Nakuru:

| Engine | Allocation | Official total |
|---|---|---|
| `frontend/src/lib/triage/` (TypeScript) | 5 bags | 12,500 KES |
| `backend/src/kilimo_hakika/` (Python) | 10 bags | 23,600 KES |
| `backend/app/` (Python, PR #5) | its own rules and depot ids again | — |

A farmer betting bus fare on the answer cannot be given three answers, and
whichever is wrong costs them money. **This is the most important open
decision in the project** and it should be settled before anything ships.

A third service also means `backend/` now hosts two Python projects at one
root: `requirements.txt` + `pytest.ini` beside `pyproject.toml` + `uv.lock`,
and two suites sharing `tests/conftest.py`. They are made to coexist (229
tests pass together, and `pytest.ini` now carries both paths because it
silently overrides `pyproject.toml`) but coexisting is not the same as being
right.

## What happened

Implementations built in parallel, without a shared decision on ownership: the
Next app's engine, this Python service, and then a third in PR #5.

| | Next.js app (`frontend/`) | Python service (`backend/`) |
|---|---|---|
| Rules engine | `src/lib/triage/engine.ts` | `src/kilimo_hakika/engine/` |
| Policy data | `database/scheme_rules.json` | `database/rule_pack.json` (generated) |
| Store | SQLite registry (`database/schema.sql`, `seed.mjs`) | Postgres, 4 schemas, RLS |
| Farmer identity | phone + 6-digit scrypt PIN | phone OTP → JWT, `identity.*` |
| Officer identity | shared passphrase | per-user roles and permissions |
| Verdict route | `POST /api/triage` | `POST /api/v1/triage` |

Both are competently built and neither is throwaway. But **two engines means two
verdicts for the same farmer**, and that is the one failure this product cannot
survive. CLAUDE.md already says it: a verdict has one source.

## The decision

**The Python engine becomes the single source of truth for verdicts. The Next.js
app remains the entire user interface.** Nothing of the frontend work is
discarded — the landing page, the wizard, the verdict card, the officer console,
the farmer accounts and the palette all stay.

Why that direction, on the merits rather than by seniority:

- **Provenance.** Every rule, price, cap and depot in the Python pack cites a
  traced source with the quoted sentence, and `kh.publish_rule_pack()` refuses to
  publish when a BLOCKER, price, allocation rule or season window rests on an
  `UNVERIFIED` one. The TS rules file cites `MOALD Circular 2024/02, s.4(1)` —
  which is the example string from CLAUDE.md, not a document anyone has read.
- **Rules the TS engine has no model for.** Depot opening hours (a Sunday trip is
  a wasted trip), dated closures, the registration-county match, in-person-only
  collection, effective-dated seasons, and non-cash payment. All are real
  turn-away causes traced to NCPB's own FAQ.
- **Reproducibility.** Verdicts are pinned to an immutable checksummed pack
  version and logged, so a disputed verdict can be replayed years later.
- **The numbers.** The published NCPB rate is 2 bags planting + 2 top-dressing
  per acre, capped at 100 per season. The TS file caps at 8, 10 and 12 bags per
  depot — plausible-looking figures with no traceable source.

## What the TS engine gets right, and mine must absorb

Two modelling ideas in `frontend/src/lib/triage/` are better than mine and are
now on the backlog:

1. **Document groups (`anyOf`).** "Proof of land" satisfied by *either* a title
   deed or a lease agreement. My pack can only demand a specific document, which
   would wrongly block a farmer holding the other one. This needs a
   `kh.requirement_group` table and an `anyOf` requirement kind.
2. **Per-depot requirement and allocation overrides.** Their Nakuru depot demands
   co-operative membership; Kitale demands a chief's letter. My rules are
   season-wide. Depots really do differ, so this needs a per-depot override
   layer — with each override carrying its own citation, since "this depot also
   asks for X" is exactly the kind of claim that needs a source.

Both are genuine gaps. Neither is a reason to keep a second engine.

## Migration, in order

1. **Done — the assistant.** `/api/assistant` streams from the Python service
   through this server, so the service token never reaches the browser. The chat
   pill is live. This is additive: nothing existing changed.
2. **Done — anonymous verdicts.** The Python `/api/v1/triage` accepts no token
   (`ALLOW_ANONYMOUS_TRIAGE`, default on), honouring the merged product rule that
   `/check` must work with no account. Signing in adds history, gap tracking,
   market data and the assistant — and only those.
3. **Next — the wizard reads `/api/v1/reference`.** This is the blocking step for
   verdict delegation, and it is why `/api/triage` still uses the TS engine
   today. The document checklist in the wizard comes from the TS rules file, so
   it has no checkbox for three requirements the Python pack demands (NCPB
   register entry, KIAMIS registration, a non-cash means of payment). Point the
   wizard at `/reference` and the checklist, depot list and county list all come
   from the packed policy, after which delegation is a one-line change through
   `src/lib/kilimo-api.ts`.
4. **Then — port `anyOf` and per-depot overrides** into the Postgres authoring
   tables, with citations, and re-export the pack.
5. **Then — one identity system.** `src/lib/kilimo-session.ts` is a labelled dev
   bridge that swaps a signed-in farmer's phone number for a service token. It
   exists only because there are two identity systems. Supabase Auth issuing one
   token both sides trust deletes that file; the Python side already verifies the
   Supabase claim shape.
6. **Then — retire the second engine.** `src/lib/triage/*` becomes a thin client;
   `engine.test.ts` moves to asserting the API contract instead of local rules.
   `database/scheme_rules.json` becomes reference material for the port, and
   `database/rule_pack.json` is the only policy artifact.

## Two contradictions to resolve, not code around

**Login.** The owner asked for required login; the merged CLAUDE.md says
`/check` must work without an account and that "if a change would require
signing in to get a verdict, the change is wrong." Both are recorded, and the
code currently honours the written product rule: anonymous verdicts allowed,
`ALLOW_ANONYMOUS_TRIAGE=false` flips it in one line. This needs a ruling.

**`backend/` is not empty.** The merged CLAUDE.md says "`backend/` — Empty.
Reserved for a future non-Next service." It now holds the triage service, the
identity model, the market module and the assistant. That line needs updating
whichever way the decision above goes.

## File ownership after this change

| Path | Owner |
|---|---|
| `database/rule_pack.json` | Generated by `database/export_pack.py`. Never hand-edited. |
| `database/scheme_rules.json` | The Next app's policy file. Reference material until step 4 lands. |
| `database/migrations/`, `database/seed/` | Postgres policy, identity, market, assistant. |
| `database/schema.sql`, `database/seed.mjs` | The SQLite registry behind the officer console. |
| `frontend/src/lib/kilimo-api.ts`, `kilimo-session.ts` | The seam between the two. |
