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
| `(farmer)` | `/`, `/dashboard`, `/check`, `/check/history`, `/check/profile`, `/login`, `/signup` | Smallholder farmers. Public. |
| `(depot)` | `/depot/*` | Depot officers verifying arrivals. Passphrase-gated. |

**Landing page** (`/`) is the marketing surface: hero, the problem, the three questions, how it works, both sign-in doors, and the scope boundaries stated as a feature. Modelled on [agrivana.framer.ai](https://agrivana.framer.ai/). Sections animate in via `components/reveal.tsx`.

**Farmer platform.** `/check` is the wizard: acreage → depot → documents held → one result screen answering all three questions. `/dashboard` is where a signed-in farmer lands. `/check/history` is their own copy of past verdicts, read-only. `/check/profile` is the stored profile the wizard prefills from.

`/dashboard` and `/check/*` live in the `(farmer)/(app)/` route group, which is URL-invisible and exists only to hang the side menu on. A new page dropped in there gets the menu without changing its path; the landing page and the auth screens sit outside it and keep their own chrome.

**The dashboard is a summary, not a home for new features.** It shows the last verdict, the stored land size and county, and a large "Check a depot" button — nothing that does not already serve one of the three questions. It is the single destination for every "back into the app" path: sign-in, sign-up, the result screen's primary button, and the name chip in the landing header all send the farmer to `/dashboard`. Signed out it redirects to `/login`, and its menu entry is hidden.

### The farmer profile

Registration already captures land size and county, so a returning farmer should never retype them. `/check/profile` is where they live, and `/check` reads them on every render.

What gets prefilled, and what deliberately does not:

- **Land size** — from the profile. Editable in the wizard: people farm more than one parcel and the stored figure goes stale.
- **Depot** — their last checked depot, else the first depot in their county. The depot list is also sorted so their county comes first; the policy file's order otherwise puts a depot three counties away at the top.
- **Documents — never.** A pre-ticked box claims the farmer is holding a paper they may have lost, sold the lease on, or let expire since last month. The gap list has to describe what is in their hand right now, so step three always starts empty. This is the one prefill that would turn a convenience into a wrong verdict.

**A farmer may edit their land size and county, and nothing else.** Name, phone and national ID are what a depot officer reads back against the card at the gate — a self-service edit on those turns the registry into whatever the farmer last typed. They are shown read-only with "correct this in person", the same reasoning as the PIN reset. `farmerProfileSchema` is the enforced contract, and `updateFarmerProfile` in `lib/db.ts` only ever writes those two columns.

The save is a server action (`check/profile/actions.ts`) and **takes the farmer id from the session cookie, never from the form.** A hidden id field would let anyone edit anyone.

### County and depot

County is picked from `lib/counties.ts` — all 47, in the First Schedule order, sorted alphabetically for display. It is **reference data, not policy**, and no verdict, cap or price derives from it, which is why it sits in code rather than in `scheme_rules.json`.

**County is a picker everywhere it is captured** — the wizard, sign-up and the profile — because the string has to match `depot.county` exactly. A farmer who typed "nyeri county" would silently never be shown the depot that serves them. `normaliseCounty()` absorbs values stored free-text before this, and `counties.test.ts` asserts every depot in the rules file sits in a real county, since a typo there fails the same way: silently.

Choosing a county in step one preselects that county's depot in step two and shows it as a card; every other depot stays reachable from a dropdown below it. Changing the county re-points the depot on purpose — a stale depot from the previous county is the wrong thing to leave selected.

#### Provisional depots

`scheme_rules.json` now carries **one depot per county, 47 in total. Only three of them are real.** NCPB Eldoret, Kitale and Nakuru come from MOALD Circular 2024/02 with their own caps, prices and document lists. The other 44 were generated to make every county selectable, and their figures — 2 bags/acre, 10 max, 2,500 KES, the three baseline documents — are a placeholder copied from the programme, not a gazetted schedule.

Those 44 carry `"provisional": true` and a `source` beginning `UNVERIFIED —`. **That flag is load-bearing and four tests defend it:**

- every county is covered exactly once
- a depot whose source is `UNVERIFIED` must have `provisional: true`
- a `provisional` depot must not claim a real-looking source
- the three cited depots stay cited, with `Circular` in the source

The flag flows `Depot` → `TriageResult.depot.provisional` → the UI. A provisional verdict renders a warning above it ("Figures for NCPB Nyeri are not confirmed"), the costing card says "Provisional figures … not yet confirmed against a circular" instead of "Gazetted rates", and the depot card in step two of the wizard carries the same line. The `UNVERIFIED` string also lands in the citation list, so "Where this comes from" shows it.

**Deleting the flag while keeping the numbers is the worst change anyone can make to this repo.** It converts a labelled guess into a statutory claim, which is the one failure the product cannot survive. Promoting a depot means replacing its allocation block and `requires` with the real schedule, swapping `source` for the citation, and deleting `provisional` — a data edit, no code change.

**A signed-in farmer's check is attributed from their session**, not from a posted `nationalId` — the wizard never sends one, so before this was wired up every check by a signed-in farmer landed in `check_events` with a null `farmer_id`, leaving both the farmer's history and the officer's "what this farmer was told" panel permanently empty. The session wins over a posted `nationalId` because the cookie is the only identity claim on that endpoint that is actually signed. The result screen's "Go to my dashboard" button goes to `/dashboard`, and is hidden when signed out.

Phone is the sign-in identifier and is currently unchangeable by anyone — there is no officer-side edit either. A farmer who loses that number loses the account. That needs an officer-side correction flow before real deployment.

### Side menu

Both signed-in surfaces share `components/app-shell.tsx` — shadcn's `sidebar` in `collapsible="icon"` mode, which becomes a sheet on mobile. `variant="farmer"` wraps the `(farmer)/(app)/` group (`/dashboard`, `/check/*`); `variant="depot"` wraps the console group. The landing page keeps `SiteHeader` instead; a marketing page with a side menu reads as an app you have to log into.

- **The menu is navigation, not a gate.** The farmer variant renders for a signed-out visitor too — it swaps the footer for a sign-in link and hides the `FARMER_ACCOUNT_ONLY` entries — Dashboard, My past checks, My details — which need an account to mean anything. Do not make the shell require a session; `/check` without an account is a product rule.
- **The signed-in farmer's name in the landing header is a link into `/dashboard`**, not a label. It is the way back into the app for someone who arrives at the marketing page with a live session.
- **The logo moves into the sidebar header** on these screens, so the pages under them must not render their own. One visible instance per screen.
- **Sign-out stays a plain form post** in both variants, for the same reason the officer sign-in form is plain HTML: a gate terminal with a broken bundle still has to be able to get out.

**`/check` must stay usable with no account. This is a product rule, not a default.** A farmer deciding whether to spend bus fare should not first have to hand over their national ID. Accounts exist so a depot officer can find someone at the gate; that is the only reason. If a change would require signing in to get a verdict, the change is wrong.

### Logo

`components/logo.tsx` is the brand lockup — mark, then `KILIMO HAKIKA` in Oswald — and it links home from every screen. `tone="dark"` places it over a photograph. Every screen gets exactly one visible instance; the auth screens swap between the photo-side and panel copies at the `lg` breakpoint so a small screen never shows two.

Three things to know before touching it:

- **`public/img/logomark.png` is the Agrivana reference site's mark**, taken from the `logo.svg` that renders as their wordmark lockup. Using another company's mark as this project's brand is a trademark problem, not a licensing one. `SproutMark` in the same file is an original vector drawn for this project; setting `USE_SUPPLIED_MARK = false` swaps to it in one line. That swap should happen before this ships under its own name.
- **The supplied mark is lime `#83F675`, roughly 1.3:1 against the pale mint page — invisible unaided.** The deep-forest badge behind it is what makes it legible. Do not remove the badge and leave a bare lime mark on a light surface.
- **The PNG is 22×22.** Crisp at that size, soft on any retina display above it. `SproutMark` is vector and takes its colour from `currentColor`, so it stays sharp and adapts to the surrounding text colour.

### Sign-in screens

`/login`, `/signup` and `/depot/sign-in` share `components/auth-split.tsx`: full-screen split, photograph left, form panel right, stacked on small screens. `IconField` from the same file puts the label in a notch on the input border with a leading icon.

Rules that hold across all three:

- **No social sign-in buttons.** There are no OAuth providers wired up, and a button that fails on click is worse than no button. The farmer screen uses that space for "check a depot without signing in" instead.
- **No self-serve PIN reset.** There is no SMS gateway to send a code through, and a reset without one is a way in for anyone who knows a farmer's phone number. The copy directs them to a depot officer in person. Add the reset only when there is a channel to verify through.
- **The officer form is plain HTML with no JavaScript dependency.** A gate terminal on a bad connection still has to be able to sign in.
- **Photographs are decorative:** empty `alt`, `aria-hidden` overlay, and the panel works if the image never loads. A deep-forest gradient sits over the photo so white type stays legible regardless of the crop.

Entrance animation is keyframes in `globals.css` (`kh-fade-up`, `kh-fade-in`, `kh-slow-zoom`) exposed as `@utility` classes, all disabled inside a `prefers-reduced-motion` block. The photo drift is deliberately slow and small — fast movement behind someone typing a PIN is distracting.

**Depot officer platform.** `/depot` looks a farmer up by full national ID and shows what they were told before travelling. `/depot/farmers` lists the registry. `/depot/farmers/[id]` shows check history and records what the farmer actually collected. A service record is what happened; a check is what we predicted. They are separate tables on purpose, and they are allowed to differ.

## Architecture

| Path | Purpose |
|------|---------|
| `frontend/` | The Next.js app — both platforms, plus the API routes and the rules engine |
| `database/` | `scheme_rules.json` (policy), `schema.sql`, `seed.mjs`, and the git-ignored SQLite file |
| `backend/` | **Two** Python services, built in parallel: `app/` + `main.py` (FastAPI triage, ward-level catchments) and `src/kilimo_hakika/` (triage plus the policy database, identity model, market data and assistant). |
| `logs/` | Git-ignored |

**There are three rules engines in this repo, and they disagree.** The TypeScript one in `frontend/src/lib/triage/`, and the two Python ones under `backend/`. For 2.5 acres at NCPB Nakuru the TS engine says 5 bags / 12,500 KES and the `kilimo_hakika` engine says 10 bags / 23,600 KES. A verdict must have one source, so this needs resolving before anything ships. **Read `docs/design/integration.md` before touching any of them** — it has the comparison, the citation evidence, and a proposed migration order.

Data flow (as shipped today): farmer inputs → `POST /api/triage` → the TypeScript engine evaluates against `scheme_rules.json` → verdict + gap list + costing → result screen, and a row in `check_events` so the gate console can see it later.

### Routes

| Route | Method | Auth | Purpose |
|---|---|---|---|
| `/api/triage` | POST | none | Run a check. Links to the signed-in farmer, else to one matching a posted `nationalId`. |
| `/api/farmers` | GET | officer | List the registry |
| `/api/farmers` | POST | none | Registration without an account (no PIN) |
| `/api/farmers/[id]/serve` | POST | officer | Record a collection |
| `/api/farmer/sign-up` | POST | none | Create a farmer account, sets session |
| `/api/farmer/sign-in` | POST | none | Phone + PIN, rate limited |
| `/api/farmer/sign-out` | POST | — | Clear farmer session |
| `/api/depot/sign-in` \| `sign-out` | POST | — | Officer session |

`src/proxy.ts` (Next 16's replacement for `middleware.ts`) gates `/depot` page navigations with a negative-lookahead matcher, so a new officer page is protected by default rather than by remembering to add it.

**API routes and server actions re-check the session themselves.** The proxy covers page navigations only — it does not run for `/api/*`, and a server action is its own entry point. Never add an officer-only route that relies on the proxy alone.

## Data protection

The registry holds real personal data: names, phone numbers, counties, land sizes.

**National IDs are never stored in the clear.** We keep a SHA-256 hash peppered with `NATIONAL_ID_HASH_SECRET`, plus the last four digits for on-screen confirmation. Exact-match lookup still works — the officer types the full number, we hash and compare — so no flow is lost, but a leaked database does not hand over ID numbers. The pepper matters: a bare hash of a 7–9 digit number is brute-forceable in seconds. Changing the pepper makes every existing farmer unfindable.

**The passphrase gate is a sprint measure, not production auth.** One shared secret means no per-officer identity and therefore no audit trail of who viewed whom — which is the first thing a real deployment of an ID registry needs. Before this goes near real farmers: per-officer accounts, an access log, a retention policy, and a Kenya Data Protection Act 2019 review.

All four secrets fail closed. `ADMIN_PASSPHRASE`, `ADMIN_SESSION_SECRET`, `NATIONAL_ID_HASH_SECRET` and `FARMER_SESSION_SECRET` have no defaults and throw when unset, because a default would silently ship an unlocked console or a meaningless hash. See `frontend/.env.example`.

Consent is captured at registration (`consent_given_at`) and the API rejects a registration without it.

### Farmer accounts

Sign-in is **phone number + 6-digit PIN**, not email and password. That is the pattern farmers already use for mobile money, it types on a keypad, and it does not assume an email address.

A 6-digit PIN is only a million combinations, so two things are load-bearing and must not be removed:

- **PINs are scrypt-hashed** (`N=16384`), never stored or logged in the clear. Verified: the PIN does not appear in the database file, and no API response carries a `pin` field.
- **Sign-in is rate limited** to 5 attempts per phone per 15 minutes. Without it the PIN falls to brute force in minutes.

The rate limiter is **in-memory**, so it resets on deploy and does not work across instances. That is acceptable for a single-node sprint deployment and is the next thing to replace with a shared store before this scales out.

Sign-in failures return one message for "no such phone" and "wrong PIN" alike, so the endpoint cannot be used to discover which numbers are registered. Sign-up conflicts are equally vague for the same reason.

`FARMER_SESSION_SECRET` signs the farmer session cookie and, like the others, has no default.

### The data layer is the brain

`scheme_rules.json` is a **purely deterministic** policy engine. It maps exact government gazette rules, land caps, and document requirements to validation logic.

Rules for this file:

- **Deterministic only.** No ML, no heuristics, no probability, no LLM in the verdict path. Same inputs must always produce the same verdict. This is the core promise of the product — a farmer betting bus fare on the answer.
- **Every rule cites its source.** Each entry carries the official citation, e.g. `"source": "MOALD Circular 2024/02"`. A rule without a citation is not a rule.
- **Policy lives in data, not code.** Adding a depot, changing a cap, or amending a document requirement is a JSON edit — never a code change. If you find yourself hardcoding a cap or a document name in the engine, move it to the JSON.
- **The engine is UI-agnostic.** It must not import anything frontend-related, so it stays testable in isolation and reusable.

### The interface

Wizard-style, digital-kiosk feel. Minimal inputs, in this order:

1. Acreage and county
2. Target depot — the county's depot is preselected, with a dropdown for the others
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

Installed: `form`, `input`, `select`, `checkbox`, `radio-group`, `label`, `card`, `alert`, `badge`, `button`, `separator`, `progress`, `table`, `sidebar` (which pulls in `sheet`, `tooltip`, `skeleton` and `hooks/use-mobile.ts`).

Shared app components: `components/app-shell.tsx` (the side menu, both platforms), `components/verdict-card.tsx` (the answer screen, used by both platforms), `components/triage-wizard.tsx`, `components/register-form.tsx`.

## Design tokens

Green system, adapted from the [agrivana.framer.ai](https://agrivana.framer.ai/) reference. Pale mint page, near-black green ink, deep forest for stamped elements. Still restrained and official rather than consumer-bright.

The earlier manila/brass "ledger paper" palette is superseded for surfaces — but gazette brass survives for statutory numbers, for the reason given below.

### Color

| Name | Hex | Role |
|---|---|---|
| Pale mint | `#ECFEF0` | Page background |
| Near-black green | `#09190D` | Primary text |
| Deep forest | `#052118` | Primary buttons — stamped, not candy |
| Sage | `#526055` | Secondary text |
| Lime | `#83F675` | Action accent, small doses only |
| Proceed green | `#2E6B45` | Verdict: go. The only saturated green in the system. |
| Gate red | `#A3321F` | Verdict: stop (brick-toned ink-stamp red, not alarm red) |
| Gazette brass | `#A67C3D` | Statutory numbers only — prices, caps, allocations |

These live in `frontend/src/app/globals.css`, mapped onto shadcn's variable names. Tailwind v4 takes full color values, not the bare HSL triplets that Tailwind v3 shadcn used — so the vars hold hex directly.

Product vocabulary is registered in the `@theme inline` block so `bg-proceed`, `text-gate`, and `text-statutory` compile as utilities:

| Var | Value | Use |
|---|---|---|
| `--proceed` / `--proceed-foreground` | `#2E6B45` / `#ECFEF0` | Verdict: PROCEED |
| `--gate` / `--gate-foreground` | `#A3321F` / `#ECFEF0` | Verdict: DO NOT TRAVEL |
| `--statutory` | `#A67C3D` | Statutory numbers, large text only |
| `--statutory-strong` | `#7F5F2F` | Statutory numbers at body size (contrast-safe) |
| `--action-accent` | `#83F675` | Lime accent. Progress fill and similar, never buttons. |

Derived surfaces, all commented as derived in the CSS:

| Var | Value | Note |
|---|---|---|
| `--card` / `--popover` | `#F7FDF8` | Near-white, lifted off the mint page |
| `--muted` / `--secondary` / `--accent` | `#DDF5E2` | Mint darkened slightly |
| `--border` / `--input` | `#C3E3CB` | Light mint hairline |
| `--ring` | `#0A412F` | Deep forest. Not lime — lime on mint is too faint to see. |

**Green surfaces collide with the green verdict. Three rules keep them apart, and they are the load-bearing part of this palette:**

1. **Surfaces stay pale and desaturated.** `#ECFEF0` page, `#F7FDF8` cards. Saturated green is reserved for the verdict. If cards and buttons were also saturated green, PROCEED would stop meaning anything.
2. **The verdict is a filled band, not colored text.** `verdict-card.tsx` renders a solid `bg-proceed` / `bg-gate` block across the top of the card. On a green UI, green text reads as decoration; a solid band reads as a stamp.
3. **Buttons are deep forest `#052118`, not lime.** A lime button sitting next to a green verdict competes with it for the eye. Lime is an accent, not an action color.

**Keep derived surfaces close to white, not to the page tint.** Stretching a handful of swatches across shadcn's ~20 surface tokens tints every card, input and hover, and the result reads as flat wash rather than paperwork. The page carries the tint; near-white carries the surfaces; the accent colors then mean something. For the same reason `--border` is a light tint, not the secondary-text color — at full strength that outlines every card in dark gray.

Do not re-add opacity modifiers like `border-border/40` on top of these. They were needed when the border was a full-strength dark tone; against a light hairline they disappear.

`--destructive` (`#6E2214`, deep oxblood) is deliberately *not* gate red. Destructive means "you are about to lose data"; gate red means "the depot will turn you away." Different meanings must not share a swatch, so a delete button and a depot verdict can never be confused.

`--radius` is `0.375rem`, squarer than shadcn's `0.625rem` default — this is a government form, not a consumer app.

Token usage rules:

- **Gazette brass is reserved,** and it is kept from the old palette on purpose even though the green reference has no gold. It marks statutory numbers only — prices, bag caps, allocations — and it has to be distinguishable from the verdict green, which no green could be. Gold on green also reads as officialdom. Using it decoratively destroys the signal that "this number is the official government figure, not our estimate."
- Verdict colors appear on the verdict only. No proceed-green buttons, no red borders elsewhere.
- Color never carries meaning alone. Every verdict pairs its color with an icon and a text label.

### Contrast

Measured against pale mint `#ECFEF0`, except where noted:

| Token | Ratio | Verdict |
|---|---|---|
| Near-black green | 17.3:1 | passes AAA |
| Gate red | 6.7:1 | passes AA |
| Sage (secondary text) | 6.3:1 | passes AA |
| Proceed green | 6.1:1 | passes AA |
| `--proceed-foreground` on `--proceed` | 6.1:1 | passes AA — the filled band is legible |
| `--gate-foreground` on `--gate` | 6.7:1 | passes AA |
| Gazette brass, on `--card` | **3.6:1** | **fails AA for body text** |
| `--statutory-strong`, on `--card` | 5.7:1 | passes AA |

Gazette brass still fails normal-text AA, and it is still the token assigned to prices — the numbers a farmer most needs to read correctly. Use it only at large-text sizes (≥18.66px bold or ≥24px), which it passes at 3:1. For a brass price at body size use `--statutory-strong`.

### Typography

| Role | Typeface | Notes |
|---|---|---|
| Headers / labels | Oswald or Barlow Condensed | Condensed, authoritative — evokes depot/gate signage |
| Body copy | Source Sans 3 or Inter | Plain, highly legible — no serif or decorative faces |

Wired up as Oswald (`--font-heading`) and Source Sans 3 (`--font-sans`) via `next/font/google`, which downloads and self-hosts them at build time — no runtime CDN request. Farmers on intermittent connectivity should not wait on Google Fonts, and a condensed header falling back to a system font loses the signage feel entirely.

`h1`–`h6` get `font-heading` in the base layer. Labels can opt in with `font-heading`.

### Dark mode

This token set is light-only by design. Every ratio in the contrast table is measured against the pale mint page, and inverting the values invalidates all of them at once — the verdict tokens most of all, and those are the ones that have to stay legible. Do not add a `.dark` block by guessing values; if dark mode is wanted, the palette needs to be designed and re-measured, not derived. Earlier guidance to "support light and dark" is superseded by this.

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
| Images | Local files in `frontend/public/img/`, credited in `CREDITS.md` |
| Animation | `components/reveal.tsx` — IntersectionObserver + CSS. No animation library. |

Still TBD:

- Formatter (Prettier not installed)
- Deployment target
- Real officer authentication (see "Data protection")

### Running it

```
cp frontend/.env.example frontend/.env.local   # then fill in all four secrets
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
- Adding a column to `database/schema.sql` does **not** reach an existing database — `CREATE TABLE IF NOT EXISTS` is a no-op on a table that already exists, and SQLite has no `ADD COLUMN IF NOT EXISTS`. Add it to `migrate()` in `src/lib/db.ts`, which checks `pragma_table_info` first. This bit once already, with `pin_hash`.
- Images live in `public/img/` and are committed. Keep any replacement under ~250KB and credited in `CREDITS.md` — two of the four are CC BY / CC BY-SA, and the landing footer carries the attribution they require. Removing that footer without removing the photos is a licence violation.
- `hooks/use-mobile.ts` was rewritten off the shadcn default, which sets state inside an effect and so fails `react-hooks/set-state-in-effect` — the same rule that shapes `reveal.tsx`. It uses `useSyncExternalStore` instead. Re-running `shadcn add sidebar` will overwrite it and reintroduce the lint error.
- Animation is one small component using IntersectionObserver plus a CSS transition. Reduced motion is handled with Tailwind's `motion-reduce` variant rather than a JS branch, because `react-hooks/set-state-in-effect` rejects setting state directly in an effect.
- Update this section as decisions land.

## Conventions

- Keep frontend, backend, and database concerns in their own top-level directory.
- The rules engine needs unit tests before it needs polish. A wrong verdict costs a farmer real money. `engine.ts` is pure — no I/O, no clock, no randomness — so it stays trivially testable; keep it that way.
- The engine throws rather than guessing when the rules file and the input disagree. A silent fallback would mean telling someone to travel on a rule we could not find.
- Allocation floors partial bags. Rounding up would quote a total the depot refuses to honour.
- Show the official cost even on a `DO NOT TRAVEL`. A farmer who doesn't know the gazetted price can't tell they're being overcharged on the next trip.
- Motion is decoration, never information. Anything the reader must know has to survive `prefers-reduced-motion` and a failed image load.
- Do not commit anything under `logs/`.
- Do not commit secrets. Use `.env` files, git-ignored, with a committed `.env.example`.
