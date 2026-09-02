"""End-to-end smoke test against the running API."""

import json
import sys

import httpx

BASE = "http://127.0.0.1:8000/api/v1"
ok = 0
fail = 0


def check(label, condition, detail=""):
    global ok, fail
    if condition:
        ok += 1
        print(f"  PASS  {label}")
    else:
        fail += 1
        print(f"  FAIL  {label}  {detail}")


c = httpx.Client(timeout=120)

print("\n== 1. public reference (no auth) ==")
r = c.get(f"{BASE}/reference")
ref = r.json()
check("reference 200", r.status_code == 200, r.text[:200])
check("depots present", len(ref["depots"]) == 8, len(ref.get("depots", [])))
check("documents split by relevance", {d["relevance"] for d in ref["documents"]} == {"ALWAYS", "CONDITIONAL"})
check("pack version header", r.headers.get("X-Rule-Pack-Version") == "NFSP-2026_SHORT_RAINS-0001")
check("cache header", "max-age=3600" in r.headers.get("Cache-Control", ""))
always = sorted(d["code"] for d in ref["documents"] if d["relevance"] == "ALWAYS")
print(f"        required always: {always}")

print("\n== 2. anonymous triage: a verdict without an account ==")
# Product rule, from CLAUDE.md: /check must stay usable with no account. A farmer
# deciding whether to spend bus fare should not first have to hand over an ID.
# Signing in adds history, gap tracking and the assistant — and only
# those. ALLOW_ANONYMOUS_TRIAGE=false inverts this in one line.
r = c.post(f"{BASE}/triage", json={"depot_code": "NCPB-NAKURU", "acreage_acres": 2, "held_documents": []})
check("anonymous triage 200", r.status_code == 200, r.text[:200])
anon = r.json()
check("anonymous verdict answered", anon["verdict"] in {"PROCEED", "DO_NOT_TRAVEL"}, anon.get("verdict"))
check("anonymous costing still answered", anon["allocation"] is not None)
# The anonymous log carries no user id by construction, so there is nothing to
# hand back to a farmer who has no account to read it from.
check("anonymous run is not filed as history", anon["history_id"] is None, anon.get("history_id"))

print("\n== 3. farmer OTP login ==")
r = c.post(f"{BASE}/auth/otp/start", json={"phone": "0712345678"})
check("otp start", r.status_code == 200 and r.json()["sent"], r.text[:200])
check("phone normalised to E.164", r.json()["phone"] == "+254712345678", r.json().get("phone"))

r = c.post(f"{BASE}/auth/otp/verify", json={"phone": "0712345678", "code": "000000"})
check("wrong code refused", r.status_code == 401, r.status_code)

r = c.post(f"{BASE}/auth/otp/start", json={"phone": "0712345678"})
r = c.post(f"{BASE}/auth/otp/verify", json={"phone": "0712345678", "code": "123456"})
check("correct code accepted", r.status_code == 200, r.text[:200])
token = r.json()["access_token"]
farmer_id = r.json()["user_id"]
H = {"Authorization": f"Bearer {token}"}

print("\n== 4. identity ==")
r = c.get(f"{BASE}/me", headers=H)
me = r.json()
check("me 200", r.status_code == 200, r.text[:300])
check("farmer role auto-granted", me["roles"] == ["farmer"], me.get("roles"))
check("triage.run granted", "triage.run" in me["permissions"])
check("no policy permission", not any(p.startswith("policy.") for p in me["permissions"]))
check("ACCOUNT consent recorded", me["consents"]["ACCOUNT"] is True)
# /me reports every known purpose, granted or not, so the UI can render a full
# consent screen without hardcoding the list. Whether ASSISTANT_AI is granted is
# durable state that survives runs, so the gate itself is asserted in section 12
# where this script controls it.
check(
    "consent map covers every purpose",
    set(me["consents"]) == {"ACCOUNT", "ANALYTICS", "ASSISTANT_AI"},
    sorted(me["consents"]),
)
check("consent values are booleans", all(isinstance(v, bool) for v in me["consents"].values()))
check("aal1", me["aal"] == "aal1")

r = c.put(
    f"{BASE}/me/profile",
    headers=H,
    json={
        "registration_county_code": "032",
        "default_acreage_acres": 2.5,
        "land_tenure": "LEASED",
        "kiamis_registered": True,
        "national_id": "12345678",
    },
)
check("profile saved", r.status_code == 200, r.text[:200])
check("national id stored as hash only", r.json()["national_id_on_file"] is True)

print("\n== 5. triage: red verdict ==")
r = c.post(f"{BASE}/triage", headers=H, json={"depot_code": "NCPB-NAKURU", "held_documents": []})
red = r.json()
check("200", r.status_code == 200, r.text[:300])
check("DO_NOT_TRAVEL", red["verdict"] == "DO_NOT_TRAVEL", red.get("verdict"))
check("reason MISSING_REQUIREMENTS", red["reason_kind"] == "MISSING_REQUIREMENTS")
check("5 blockers", len(red["blockers"]) == 5, len(red["blockers"]))
check("every blocker cites a source", all(b["citation"] for b in red["blockers"]))
check("cost answered on a red verdict", red["costing"] is not None and red["allocation"] is not None)
check(
    "acreage came from profile", red["allocation"]["acreage_acres"] == 2.5, red["allocation"]["acreage_acres"]
)
check("2.5 acres -> 10 bags", red["allocation"]["total_bags"] == 10, red["allocation"]["total_bags"])
check("history row created", red["history_id"] is not None)
check("leased-land advisories present", len(red["advisories"]) >= 2, len(red["advisories"]))
check(
    "unverified advisory flagged",
    any(a["citation_is_unverified"] for a in red["advisories"]),
)
print(f"        missing: {[b['document_code'] for b in red['blockers']]}")
print(f"        min official cost: KES {red['costing']['min_total_cost_kes']:,.0f}")
history_id = red["history_id"]

print("\n== 6. triage: green verdict ==")
held = always
r = c.post(
    f"{BASE}/triage",
    headers=H,
    json={"depot_code": "NCPB-NAKURU", "held_documents": held, "fertilizer_code": "DAP"},
)
green = r.json()
check("PROCEED", green["verdict"] == "PROCEED", json.dumps(green.get("blockers"))[:300])
check("no blockers", green["blockers"] == [])
check("selected fertilizer flagged", any(line["selected"] for line in green["costing"]["lines"]))
dap = next(line for line in green["costing"]["lines"] if line["fertilizer_code"] == "DAP")
check("DAP gazetted price 2500", dap["price_kes_per_bag"] == 2500.0, dap["price_kes_per_bag"])
check("DAP cites the ministry notice", dap["citation"] == "MOALD-NFSP-2025-LAUNCH", dap["citation"])
can = next(line for line in green["costing"]["lines"] if line["fertilizer_code"] == "CAN")
check("press-sourced price flagged unverified", can["citation_is_unverified"] is True)

print("\n== 7. fail-closed states ==")
r = c.post(f"{BASE}/triage", headers=H, json={"depot_code": "NCPB-NOWHERE", "held_documents": held})
check("unknown depot -> DO_NOT_TRAVEL", r.json()["verdict"] == "DO_NOT_TRAVEL")
check("reason DEPOT_UNKNOWN", r.json()["reason_kind"] == "DEPOT_UNKNOWN")
check("engine blocker has no citation", r.json()["blockers"][0]["citation"] is None)

r = c.post(
    f"{BASE}/triage",
    headers=H,
    json={"depot_code": "NCPB-NAKURU", "held_documents": held, "travel_date": "2027-06-01"},
)
check("date beyond horizon refused", r.status_code == 422, r.status_code)

r = c.post(f"{BASE}/triage", headers=H, json={"depot_code": "NCPB-BUNGOMA", "held_documents": held})
check("wrong county blocks", "ELIG_DEPOT_COUNTY_MISMATCH" in [b["code"] for b in r.json()["blockers"]])

print("\n== 8. swahili ==")
r = c.post(f"{BASE}/triage?lang=sw", headers=H, json={"depot_code": "NCPB-NAKURU", "held_documents": []})
check("swahili headline", r.json()["headline"] == "Usisafiri bado", r.json()["headline"])
check(
    "swahili blocker text",
    # Case-folded: the Swahili copy sentence-cases mid-sentence terms.
    "kitambulisho" in r.json()["blockers"][0]["message"].lower(),
)

print("\n== 9. gap tracking ==")
r = c.get(f"{BASE}/me/triage-history", headers=H)
check("history listed", len(r.json()["items"]) >= 2, len(r.json()["items"]))
r = c.patch(
    f"{BASE}/me/triage-history/{history_id}/gaps",
    headers=H,
    json={"gap_state": {"EVOUCHER_CODE": "RESOLVED"}},
)
check("gap marked resolved", r.json()["gap_state"]["EVOUCHER_CODE"] == "RESOLVED", r.text[:200])

print("\n== 11. citations ==")
r = c.get(f"{BASE}/citations/NCPB-FAQ-2022-10-Q8")
check("citation fetched", r.status_code == 200 and "two bags" in r.json()["verbatim_extract"], r.text[:200])
check("verified source not flagged", r.json()["is_unverified"] is False)
r = c.get(f"{BASE}/citations/SEED-SEASON-WINDOW")
check("seed citation flagged unverified", r.json()["is_unverified"] is True)

print("\n== 12. assistant consent gate ==")
# Consent is durable, and this account may already have granted it on an earlier
# run or through the web proxy. Withdraw first so the gate is actually exercised
# rather than accidentally passing on leftover state.
r = c.put(f"{BASE}/me/consent", headers=H, json={"purpose": "ASSISTANT_AI", "granted": False})
check("consent withdrawn", r.status_code == 200, r.text[:200])

r = c.post(f"{BASE}/assistant/messages", headers=H, json={"text": "Nini nahitaji?"})
check("403 without consent", r.status_code == 403, r.status_code)
check("CONSENT_REQUIRED", r.json()["detail"]["error"]["code"] == "CONSENT_REQUIRED", r.text[:200])

r = c.put(f"{BASE}/me/consent", headers=H, json={"purpose": "ASSISTANT_AI", "granted": True})
check("consent granted", r.status_code == 200, r.text[:200])

print("\n== 13. staff auth and the aal2 gate ==")
r = c.post(f"{BASE}/auth/staff/login", json={"email": "publisher@kilimohakika.test", "password": "wrong"})
check("bad password refused", r.status_code == 401)
r = c.post(
    f"{BASE}/auth/staff/login", json={"email": "publisher@kilimohakika.test", "password": "depot-dev-2026"}
)
check("password login ok", r.status_code == 200, r.text[:200])
check("aal1 without second factor", r.json()["aal"] == "aal1")
r = c.post(
    f"{BASE}/auth/staff/login",
    json={"email": "publisher@kilimohakika.test", "password": "depot-dev-2026", "totp_code": "123456"},
)
check("aal2 with second factor", r.json()["aal"] == "aal2", r.json().get("aal"))
staff_h = {"Authorization": f"Bearer {r.json()['access_token']}"}
r = c.get(f"{BASE}/me", headers=staff_h)
check("publisher has policy.publish", "policy.publish" in r.json()["permissions"])
check("publisher cannot author policy", "policy.author" not in r.json()["permissions"])
r = c.get(f"{BASE}/reference", headers=staff_h)
# Every account is granted the baseline `farmer` role at signup, and that role
# carries the base read permissions. Published policy is public by
# design, so a staff account reading them is correct, not a leak. The consent
# gate below is the assertion that actually guards something.
check("publisher can read published policy -> 200", r.status_code == 200, r.status_code)

print("\n== 14. RLS: one farmer cannot see another's history ==")
r = c.post(f"{BASE}/auth/otp/start", json={"phone": "0798765432"})
r = c.post(f"{BASE}/auth/otp/verify", json={"phone": "0798765432", "code": "123456"})
other_h = {"Authorization": f"Bearer {r.json()['access_token']}"}
r = c.get(f"{BASE}/me/triage-history", headers=other_h)
check("second farmer sees an empty history", r.json()["items"] == [], r.text[:200])
r = c.patch(
    f"{BASE}/me/triage-history/{history_id}/gaps",
    headers=other_h,
    json={"gap_state": {"EVOUCHER_CODE": "RESOLVED"}},
)
check("cannot touch another farmer's row", r.status_code == 404, r.status_code)

print(f"\n{'=' * 60}\n  {ok} passed, {fail} failed\n{'=' * 60}")
sys.exit(1 if fail else 0)
