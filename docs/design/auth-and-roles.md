# Authentication, roles and permissions

Status: proposed, 2 September 2026. Schema:
[`20260902091000_identity.sql`](../../database/migrations/20260902091000_identity.sql).

Login is **required** to run a triage (owner decision, 2 September 2026).

---

## 1. Who logs in, and how

| Audience | Identifier | Method | Second factor |
|---|---|---|---|
| Farmer | Phone number | Supabase Auth phone OTP | None |
| Retail / wholesale staff | Email | Password or magic link | Optional TOTP |
| Supplier association staff | Email | Password | **TOTP required** |
| Platform staff, developers | Email | Password | **TOTP required** |

Phone OTP is right for farmers: a phone number is the identifier they already
have, there is no password to forget, and it works on a low-end Android. Email
is right for staff, who have inboxes and desks.

TOTP is required for anyone who can publish a price or touch policy. Those two
capabilities are the ones an attacker would want: one lets you lie to farmers
about cost, the other lets you lie to them about the law.

**Assurance level gate.** Supabase reports the achieved factor level in the
JWT's `aal` claim. `policy.publish`, `policy.author`, `org.verify` and
`market.price.publish.own_org` all require `aal2`. A password-only session may
read those consoles and may not write to them.

### The cost of requiring a login, and what to do about it

Two real consequences, both worth designing around rather than discovering:

1. **Every OTP is an SMS with a price.** At scale, login SMS is a recurring
   per-farmer cost with no ceiling if sessions are short. Mitigation: issue long
   refresh tokens (90 days) so a farmer signs in about once a season, and never
   force a re-OTP for a read.
2. **Shared and borrowed phones are normal.** A farmer using a neighbour's
   handset must not leave a session behind. Mitigation: a prominent "finish and
   sign out" action on the result screen, and a "this is not my phone" choice at
   login that issues a session expiring in 30 minutes with no refresh token.

---

## 2. What each audience can do

Permissions are the unit; roles are bundles of them. Full grant table is in the
migration — the shape of it:

| | Farmer | Business staff | Business admin | Supplier editor | Supplier publisher | Policy author | Policy reviewer | Policy publisher | Moderator | Analyst | Developer | Platform admin |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Run triage | ● | ● | ● | | | ● | ● | ● | | | | |
| Own triage history | ● | | | | | | | | | | | |
| Read market data | ● | ● | ● | ● | ● | ● | | | ● | ● | ● | ● |
| Draft prices | | ● | ● | ● | ● | | | | | | | |
| Publish prices / signals | | | ● | | ● | | | | | | | |
| Manage own org members | | | ● | | | | | | | | | ● |
| Verify organisations | | | | | | | | | ● | | | ● |
| Author statutory policy | | | | | | ● | | | | | | |
| Review policy citations | | | | | | | ● | ● | | | | |
| Publish a rule pack | | | | | | | | ● | | | | |
| Read analytics | | | | | | | | | | ● | ● | ● |
| Read audit trail | | | | | | | | | | | ● | ● |
| Use the assistant | ● | ● | ● | ● | ● | | | | | | | |

### Three separations that matter more than the rest

**Author, reviewer, publisher are three different people.** No role holds
`policy.author` together with `policy.review` or `policy.publish` — not even
`platform_admin`. A rule decides whether a farmer spends a day's earnings on
transport; it gets two pairs of eyes, and the split is in the grant table rather
than in a process document. Combined with the publish gate that rejects
`UNVERIFIED` citations, a wrong rule has to get past a second human and the
database to reach a farmer.

**No supplier role holds any `policy.*` permission.** A supplier association can
set its own prices in `market` and nothing else. Nobody outside the platform can
edit what the app presents as the law — which is the whole reason a farmer
believes the app over the official at the gate.

**`platform_admin` is not a superuser.** It cannot author policy, cannot publish
a pack, and cannot write market data for an organisation it does not belong to.
The account most likely to be phished is the account least able to lie.

---

## 3. How authorization is enforced

Two layers, in this order:

1. **FastAPI dependency.** `require("market.price.publish.own_org")` resolves the
   caller's permissions and returns 403 before any handler runs. This is where a
   clear error message comes from.
2. **Row-level security.** Every request opens its transaction as the
   `authenticated` role with the caller's JWT claims set:

   ```sql
   set local role authenticated;
   set local request.jwt.claims = '<the verified claims as json>';
   ```

   `auth.uid()` then resolves inside policies, and `identity.has_permission()`
   and `identity.orgs_with_permission()` do the rest. If layer 1 has a bug, the
   database still refuses.

**Authorization reads the table, not the token.** The JWT carries roles so the
client can shape its UI, but `identity.has_permission()` queries `membership`.
A revoked grant therefore takes effect immediately instead of at token expiry —
which is what you want the moment you revoke someone in anger.

**Grants are revoked, never deleted.** `membership.revoked_at` preserves the
answer to "who could publish that price on the day it was published".

**JWT verification.** Supabase asymmetric signing keys; the backend verifies
against the project JWKS with a cached key set, so no shared secret exists to
leak. The `service_role` key is used for exactly one thing — reading the active
rule pack at startup — and never for user data.

---

## 4. Personal data

Requiring a login means the platform now processes personal data, and the Kenya
Data Protection Act 2019 applies in full.

- **Phone numbers and emails live only in `auth.users`**, managed by Supabase.
  `identity.app_user` holds profile and status. Not copying them is the cheapest
  privacy control available.
- **National ID numbers are stored as a keyed HMAC**, pepper held outside the
  database, and only where a farmer volunteers one. Enough to recognise a
  returning farmer or match an NCPB register export; useless in a dump. Plaintext
  only if a confirmed NCPB integration demands it, and then only in Supabase Vault.
- **Consent is per purpose and versioned** (`identity.consent`): `ACCOUNT`,
  `ASSISTANT_AI`, `ANALYTICS`, `MARKET_NOTIFICATIONS`. `ASSISTANT_AI` is a
  hard gate — the RLS policy on `ai.conversation` refuses to create one without a
  live consent row, so withdrawing consent stops model calls at the database
  rather than at whichever code path remembered to check.
- **Erasure keeps the audit trail.** `identity.triage_history` (the farmer's own
  view) is separate from `kh.triage_log` (the anonymous engine record). Erasure
  deletes the former; the latter survives with no link to a person. A farmer's
  right to be forgotten never costs the ability to replay a disputed verdict.
- **The audit log is append-only**, enforced by triggers on
  `identity.audit_event`. Every write to `kh.*`, every organisation verification,
  every role grant and every suspension lands there.

---

## 5. Open questions

1. **Which SMS provider for OTP?** Africa's Talking and Twilio both work with
   Supabase; deliverability and per-message cost in Kenya differ materially, and
   this is a recurring cost per login rather than a one-off.
2. **Who verifies organisations, and against what register?** `org.verify` exists;
   the evidence standard behind it does not. A business registration number
   checked against the Business Registration Service is the obvious bar, and a
   supplier association that publishes prices should meet a higher one.
3. **Do farmers need any of this?** Required login was your call and it is
   implemented as such. The one thing it buys the farmer is a saved profile and a
   tracked gap list; the thing it costs is a shared-phone farmer's ability to walk
   up and ask a question. If the walk-up case turns out to matter, the smallest
   change is to allow an anonymous triage that offers to save itself afterwards —
   the engine is already stateless, so that is a routing decision, not a redesign.
