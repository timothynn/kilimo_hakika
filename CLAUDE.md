# Kilimo Hakika (DepotReady)

## What this is

A deterministic **triage and validation engine** for farmers dealing with government subsidy programs and state-run agricultural depots (e.g. NCPB).

It is a digital checkpoint, not an ecosystem. Its whole job: give a farmer certainty **before** they spend time and transport money traveling to a depot.

**The problem it solves:** farmers travel to centralized depots and get turned away at the gate — missing a chief's stamp on a land lease, missing an e-voucher code — or get exploited by officials because they don't know the official gazetted caps and prices.

## The three questions (the entire product)

Every feature must map to one of these. If it doesn't, it doesn't belong.

1. **Will I be served?** — Cross-reference the farmer's held documents against official government circulars. Output a definitive depot status: green `PROCEED` or red `DO NOT TRAVEL`. Binary, no maybes.
2. **What am I lacking?** — On a "no", return an explicit itemized checklist of missing *physical artifacts*. e.g. `Missing: Original National ID`, `Missing: E-Voucher SMS Code`.
3. **What is the official cost?** — From the farmer's land size, compute the exact allowable allocation and total cost at official gazetted rates. e.g. `Cap: 4 bags for 2 acres. Official Total: 10,000 KES`.

## Hard scope boundaries (track compliance)

These are non-negotiable. Do not add them, do not suggest them, do not scaffold toward them.

- **No agronomic advice.** Zero crop, planting, fertilizer-choice, or yield recommendations.
- **No payments.** Zero M-Pesa or any payment API. Zero transaction handling. The system *displays* the statutory truth; it never moves money.
- **No marketplace.** Zero vendor listings, zero e-commerce, zero price comparison between sellers.

Scope creep is the primary risk on this project. When in doubt, cut.

## Two platforms

One Next.js app serves both audiences, as route groups sharing the token set and components.

| Group | Routes | Audience |
|---|---|---|
| `(farmer)` | `/`, `/register` | Smallholder farmers. Public, no auth. |
| `(depot)` | `/depot/*` | Depot officers verifying arrivals. Passphrase-gated. |

**Farmer platform.** The wizard: acreage → depot → documents held → one result screen answering all three questions. Registration is optional and exists only so a depot officer can find the farmer at the gate — a farmer must never have to register to get an answer.

**Depot officer platform.** `/depot` looks a farmer up by full national ID and shows what they were told before travelling. `/depot/farmers` lists the registry. `/depot/farmers/[id]` shows check history and records what the farmer actually collected. A service record is what happened; a check is what we predicted. They are separate tables on purpose, and they are allowed to differ.

## Architecture

| Path | Purpose |
|------|---------|
| `frontend/` | The Next.js app — both platforms, plus the API routes and the rules engine |
| `database/` | `scheme_rules.json` (policy), `schema.sql`, `seed.mjs`, and the git-ignored SQLite file |
| `backend/` | Empty. Reserved for a future non-Next service (SMS/USSD gateway). Next route handlers are the backend today. |
| `logs/` | Git-ignored |

Data flow: farmer inputs → `POST /api/triage` → engine evaluates against `scheme_rules.json` → verdict + gap list + costing → result screen, and a row in `check_events` so the gate console can see it later.

### Routes

| Route | Method | Auth | Purpose |
|---|---|---|---|
| `/api/triage` | POST | none | Run a check. Links to a farmer if `nationalId` matches one. |
| `/api/farmers` | GET | officer | List the registry |
| `/api/farmers` | POST | none | Farmer self-registration |
| `/api/farmers/[id]/serve` | POST | officer | Record a collection |
| `/api/depot/sign-in` \| `sign-out` | POST | — | Officer session |

`src/proxy.ts` (Next 16's replacement for `middleware.ts`) gates `/depot` page navigations with a negative-lookahead matcher, so a new officer page is protected by default rather than by remembering to add it.

**API routes and server actions re-check the session themselves.** The proxy covers page navigations only — it does not run for `/api/*`, and a server action is its own entry point. Never add an officer-only route that relies on the proxy alone.

## Data protection

The registry holds real personal data: names, phone numbers, counties, land sizes.

**National IDs are never stored in the clear.** We keep a SHA-256 hash peppered with `NATIONAL_ID_HASH_SECRET`, plus the last four digits for on-screen confirmation. Exact-match lookup still works — the officer types the full number, we hash and compare — so no flow is lost, but a leaked database does not hand over ID numbers. The pepper matters: a bare hash of a 7–9 digit number is brute-forceable in seconds. Changing the pepper makes every existing farmer unfindable.

**The passphrase gate is a sprint measure, not production auth.** One shared secret means no per-officer identity and therefore no audit trail of who viewed whom — which is the first thing a real deployment of an ID registry needs. Before this goes near real farmers: per-officer accounts, an access log, a retention policy, and a Kenya Data Protection Act 2019 review.

All three secrets fail closed. `ADMIN_PASSPHRASE`, `ADMIN_SESSION_SECRET`, and `NATIONAL_ID_HASH_SECRET` have no defaults and throw when unset, because a default would silently ship an unlocked console or a meaningless hash. See `frontend/.env.example`.

Consent is captured at registration (`consent_given_at`) and the API rejects a registration without it.

### The data layer is the brain

`scheme_rules.json` is a **purely deterministic** policy engine. It maps exact government gazette rules, land caps, and document requirements to validation logic.

Rules for this file:

- **Deterministic only.** No ML, no heuristics, no probability, no LLM in the verdict path. Same inputs must always produce the same verdict. This is the core promise of the product — a farmer betting bus fare on the answer.
- **Every rule cites its source.** Each entry carries the official citation, e.g. `"source": "MOALD Circular 2024/02"`. A rule without a citation is not a rule.
- **Policy lives in data, not code.** Adding a depot, changing a cap, or amending a document requirement is a JSON edit — never a code change. If you find yourself hardcoding a cap or a document name in the engine, move it to the JSON.
- **The engine is UI-agnostic.** It must not import anything frontend-related, so it stays testable in isolation and reusable.

### The interface

Wizard-style, digital-kiosk feel. Minimal inputs, in this order:

1. Acreage
2. Target depot
3. Checkbox list of documents currently held

Then one result screen answering all three questions at once.

Design constraints: assume low-end Android, intermittent connectivity, and users who may be reading a screen like this for the first time. Big touch targets. Plain language. The verdict must be legible at a glance and must not rely on color alone (icon + text label alongside it).

## UI kit (decided)

**shadcn/ui + Tailwind CSS.** This is the project's design system. Do not introduce a second component library (no MUI, Chakra, Ant, Bootstrap, DaisyUI).

Note: an earlier draft of the project overview specified a Streamlit UI. That is superseded — the frontend is React with shadcn/ui.

Rules:

- Components come from shadcn/ui, added via `npx shadcn@latest add <component>`. They land in the repo as source — edit them in place rather than wrapping them in adapters.
- Style with Tailwind utility classes. No CSS-in-JS, no separate `.css` modules except the Tailwind entry file and genuine global styles.
- Theme via CSS custom properties in the Tailwind layer (shadcn's `--background`, `--foreground`, `--primary`, … convention). Reference semantic tokens (`bg-background`, `text-muted-foreground`), not raw palette values (`bg-slate-900`).
- Never hardcode a hex color in a component. Every color comes from the token set below.
- Merge conditional classes with `cn()` (`clsx` + `tailwind-merge`) from `lib/utils`.
- Compose variants with `class-variance-authority` (cva), matching how shadcn's own components are written.
- Icons: `lucide-react` (shadcn's default).
- Forms: `react-hook-form` + `zod` via shadcn's `Form` components. The zod schema for farmer inputs is the frontend's input contract; the backend still validates independently — never trust client validation for a verdict.
- Accessibility is not optional — shadcn builds on Radix primitives; keep the primitive's semantics and keyboard behavior intact when customizing.

Installed: `form`, `input`, `select`, `checkbox`, `radio-group`, `label`, `card`, `alert`, `badge`, `button`, `separator`, `progress`, `table`.

Shared app components: `components/verdict-card.tsx` (the answer screen, used by both platforms), `components/triage-wizard.tsx`, `components/register-form.tsx`.

## Design tokens

The visual language is government paperwork — a gazette notice, a depot gate sign, an ink stamp. Deliberately not a consumer fintech app. Muted, printed, official.

### Color

| Name | Hex | Role |
|---|---|---|
| Ledger paper | `#EDE6D3` | Background — sun-bleached manila, not stock cream |
| Depot ink | `#1C2620` | Primary text — dark bottle-green-black, not pure black |
| Proceed green | `#2E6B45` | Status: go (muted signal green, not candy-bright) |
| Gate red | `#A3321F` | Status: stop (brick-toned ink-stamp red, not alarm red) |
| Gazette brass | `#A67C3D` | Statutory numbers only — prices, caps, allocations |
| Ash gray | `#6E6656` | Secondary text, borders, dividers |

These live in `frontend/src/app/globals.css`, mapped onto shadcn's variable names. Tailwind v4 takes full color values, not the bare HSL triplets that Tailwind v3 shadcn used — so the vars hold hex directly.

Product vocabulary is registered in the `@theme inline` block so `bg-proceed`, `text-gate`, and `text-statutory` compile as utilities:

| Var | Value | Use |
|---|---|---|
| `--proceed` | `#2E6B45` | Verdict: PROCEED |
| `--gate` | `#A3321F` | Verdict: DO NOT TRAVEL |
| `--statutory` | `#A67C3D` | Statutory numbers, large text only |
| `--statutory-strong` | `#7F5F2F` | Statutory numbers at body size (contrast-safe) |

Anything outside the six named colors is derived from ledger paper by lightening (`--card` `#F5F1E4`) or darkening (`--muted` / `--secondary` `#E0D7BF`), and is commented as derived in the CSS.

`--destructive` (`#6E2214`, deep oxblood) is deliberately *not* gate red. Destructive means "you are about to lose data"; gate red means "the depot will turn you away." Different meanings must not share a swatch, so a delete button and a depot verdict can never be confused.

`--radius` is `0.375rem`, squarer than shadcn's `0.625rem` default — this is a government form, not a consumer app.

Token usage rules:

- **Gazette brass is reserved.** It marks statutory numbers only — prices, bag caps, allocations. Using it for decoration destroys the signal that "this number is the official government figure, not our estimate."
- Verdict colors appear on the verdict only. No green buttons, no red borders elsewhere.
- Color never carries meaning alone. Every verdict pairs its color with an icon and a text label.

### Contrast — known issue

Measured against ledger paper `#EDE6D3`:

| Token | Ratio | Verdict |
|---|---|---|
| Depot ink | 12.5:1 | passes AAA |
| Gate red | 5.6:1 | passes AA |
| Proceed green | 5.1:1 | passes AA |
| Ash gray | 4.6:1 | passes AA, barely — do not lighten |
| Gazette brass | **3.0:1** | **fails AA for body text** |

Gazette brass fails normal-text AA, and it's the token assigned to prices — the numbers a farmer most needs to read correctly. Use it only at large-text sizes (≥18.66px bold or ≥24px), which it does pass at 3:1. For a brass price in body-size text use `--statutory-strong` (`#7F5F2F`, ~4.7:1) instead of shipping the fail.

### Typography

| Role | Typeface | Notes |
|---|---|---|
| Headers / labels | Oswald or Barlow Condensed | Condensed, authoritative — evokes depot/gate signage |
| Body copy | Source Sans 3 or Inter | Plain, highly legible — no serif or decorative faces |

Wired up as Oswald (`--font-heading`) and Source Sans 3 (`--font-sans`) via `next/font/google`, which downloads and self-hosts them at build time — no runtime CDN request. Farmers on intermittent connectivity should not wait on Google Fonts, and a condensed header falling back to a system font loses the signage feel entirely.

`h1`–`h6` get `font-heading` in the base layer. Labels can opt in with `font-heading`.

### Dark mode

This token set is light-only by design — it's printed paper. There is no dark equivalent yet, and inverting it would break the whole metaphor. Do not add a `.dark` block by guessing values; if dark mode is wanted, the palette needs to be designed, not derived. Earlier guidance to "support light and dark" is superseded by this.

## Stack

Decided:

| Piece | Choice |
|---|---|
| Frontend | Next.js 16, App Router, TypeScript, `src/` dir, `@/*` alias |
| Styling | Tailwind CSS v4 (CSS-first config, no `tailwind.config.js`) |
| Components | shadcn/ui, `radix-nova` style, radix base, lucide icons |
| Forms | `react-hook-form` + `zod` + `@hookform/resolvers` |
| Package manager | npm |
| Lint | ESLint via `eslint-config-next` (`npm run lint`) |
| Tests | Vitest (`npm test`) |
| Backend | Next route handlers + server actions. No separate service. |
| Store | SQLite via `node:sqlite` — a Node builtin, so no native module and no ORM |

Still TBD:

- Formatter (Prettier not installed)
- Deployment target
- Real officer authentication (see "Data protection")

### Running it

```
cp frontend/.env.example frontend/.env.local   # then fill in all three secrets
cd frontend && npm install && npm run dev
NATIONAL_ID_HASH_SECRET=<same value> node database/seed.mjs   # optional demo data
```

The seed prints an ID to try in the gate console. `frontend/.env*` is git-ignored; `database/*.db` too.

### Frontend gotchas

- `frontend/AGENTS.md` and `frontend/CLAUDE.md` are generated by Next 16 and rewritten by `next dev`. They are not the project brief — this file is. Don't bother deleting them.
- Components import from the unified `radix-ui` package (`import { Slot } from "radix-ui"`), not per-primitive `@radix-ui/react-*` packages. Match that style when hand-writing a component.
- `src/components/ui/form.tsx` was hand-written: the shadcn CLI silently no-ops on `add form` under this preset. If you regenerate components, don't expect the CLI to produce it.
- `npx tsc --noEmit` alone reports `Cannot find name 'LayoutProps'`. That global comes from Next's generated types, so typecheck via `npm run build` instead.
- Next 16 deprecated `middleware.ts` in favour of `proxy.ts` exporting `proxy`. Don't reintroduce the old convention.
- `src/lib/triage/scheme_rules.json` is a **generated copy** of `database/scheme_rules.json`, written by `scripts/sync-rules.mjs` via `predev`/`prebuild`/`pretest` and git-ignored. Edit the one in `database/`. It exists because reading the policy with `readFileSync` at runtime makes Turbopack trace the whole project into the server bundle; a static import avoids that and bakes the policy into the build.
- `node:sqlite` types need `@types/node` ≥ 24. On ^20 the build fails with `Cannot find module 'node:sqlite'`.
- Update this section as decisions land.

## Conventions

- Keep frontend, backend, and database concerns in their own top-level directory.
- The rules engine needs unit tests before it needs polish. A wrong verdict costs a farmer real money. `engine.ts` is pure — no I/O, no clock, no randomness — so it stays trivially testable; keep it that way.
- The engine throws rather than guessing when the rules file and the input disagree. A silent fallback would mean telling someone to travel on a rule we could not find.
- Allocation floors partial bags. Rounding up would quote a total the depot refuses to honour.
- Show the official cost even on a `DO NOT TRAVEL`. A farmer who doesn't know the gazetted price can't tell they're being overcharged on the next trip.
- Do not commit anything under `logs/`.
- Do not commit secrets. Use `.env` files, git-ignored, with a committed `.env.example`.
