"""
The deterministic triage engine.

Given a farmer's location, target depot, acreage, declared crop and the
documents they physically hold, this module decides one thing: will the NCPB
counter serve them today, or would the journey be wasted?

Determinism is the whole point. There is no model, no scoring, no randomness
and no I/O. The same request always produces the same verdict, and every
rejection cites the circular clause it rests on, so a Ward Agricultural Officer
can audit any answer by hand.

Evaluation order
----------------
1. Resolve and validate the location and the depot. Bad references are caller
   errors (HTTP 422/404), not verdicts - the frontend builds its dropdowns from
   this same data, so an invalid combination means a bug, not a farmer problem.
2. Compute the statutory entitlement. This is reported even when the verdict is
   DO_NOT_TRAVEL, because the farmer still needs to know what they are owed
   once the blockers are cleared.
3. Collect every blocker. The engine never short-circuits: a farmer missing two
   documents at a closed depot is told all three facts at once, so one trip
   fixes everything.
4. PROCEED only when the blocker list is empty.
"""

from __future__ import annotations

import math
from typing import Any

from . import repository as repo
from .compliance import compliance_notice
from .schemas import TriageStatus


class TriageInputError(Exception):
    """
    A reference in the request does not exist (unknown county, ward outside the
    named constituency, unknown depot id). Surfaced by the router as an HTTP
    error rather than as a DO_NOT_TRAVEL verdict, because it is a caller
    problem, not a finding about the farmer.
    """

    def __init__(
        self,
        field: str,
        message: str,
        *,
        status_code: int = 422,
        valid_options: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.field = field
        self.message = message
        self.status_code = status_code
        # Capped: some of these lists run to hundreds of entries and the point
        # is to help a developer, not to mirror the whole dataset into an error.
        self.valid_options = (valid_options or [])[:60]

    def as_detail(self) -> dict[str, Any]:
        detail: dict[str, Any] = {"field": self.field, "message": self.message}
        if self.valid_options:
            detail["valid_options"] = self.valid_options
        return detail


class Blocker:
    """
    One reason the farmer would be turned away.

    `code` keeps blockers de-duplicable (the unstamped-lease finding can arrive
    from either a declared document or the leased-without-stamp condition, and
    must be reported once). `document_code` is set only for a missing mandatory
    document, so `gap_analysis.missing_documents` can be derived from the same
    single pass that builds `rejection_reasons`.
    """

    __slots__ = ("code", "reason", "document_code", "next_step")

    def __init__(
        self,
        code: str,
        reason: str,
        *,
        document_code: str | None = None,
        next_step: str | None = None,
    ) -> None:
        self.code = code
        self.reason = reason
        self.document_code = document_code
        self.next_step = next_step


# --------------------------------------------------------------------------
# Step 1 - resolve references
# --------------------------------------------------------------------------


def _resolve_location(county: str, constituency: str, ward: str) -> dict[str, Any]:
    county_record = repo.find_county(county)
    if county_record is None:
        raise TriageInputError(
            "county",
            f"Unknown county {county!r}. Use a county from GET /api/geo/hierarchy.",
            valid_options=repo.county_names(),
        )

    constituency_record = repo.find_constituency(county, constituency)
    if constituency_record is None:
        raise TriageInputError(
            "constituency",
            f"{constituency!r} is not a constituency of "
            f"{county_record['county_name']}.",
            valid_options=repo.constituency_names(county),
        )

    ward_record = repo.find_ward(county, constituency, ward)
    if ward_record is None:
        raise TriageInputError(
            "ward",
            f"{ward!r} is not a ward of "
            f"{constituency_record['constituency_name']} constituency.",
            valid_options=repo.ward_names(county, constituency),
        )

    return {
        "county": county_record["county_name"],
        "county_code": county_record["county_code"],
        "constituency": constituency_record["constituency_name"],
        "constituency_id": constituency_record["constituency_id"],
        "ward": ward_record["ward_name"],
        "ward_id": ward_record["ward_id"],
    }


def _resolve_depot(target_depot_id: str) -> dict[str, Any]:
    depot = repo.find_depot(target_depot_id)
    if depot is None:
        raise TriageInputError(
            "target_depot_id",
            f"Unknown depot {target_depot_id!r}. Use a depot_id from GET /api/depots.",
            status_code=404,
            valid_options=[d["depot_id"] for d in repo.DEPOTS],
        )
    return depot


# --------------------------------------------------------------------------
# Step 2 - statutory entitlement
# --------------------------------------------------------------------------


def _calculate_allocation(acreage: float) -> dict[str, Any]:
    """
    Bags due under the circular: 4 per acre (2 planting + 2 top-dressing),
    floored to whole bags, then capped at the per-farmer ceiling.
    """
    per_acre = repo.ALLOCATION["bags_per_acre_total"]
    ceiling = repo.ALLOCATION["max_bags_per_farmer"]

    # Round before flooring: acreage arrives as a float, and a value such as
    # 0.7 * 4 evaluates to 2.8000000000000003 while 2.35 * 4 can land a hair
    # under 9.4. Rounding to 6dp first keeps the floor honest instead of
    # letting binary representation error silently shave off a bag.
    raw = round(acreage * per_acre, 6)
    uncapped = math.floor(raw)
    allocated = min(uncapped, ceiling)

    return {
        "declared_acreage": acreage,
        "bags_per_acre": per_acre,
        "planting_bags_per_acre": repo.ALLOCATION["bags_per_acre_planting"],
        "top_dressing_bags_per_acre": repo.ALLOCATION["bags_per_acre_top_dressing"],
        "uncapped_entitlement_bags": uncapped,
        "max_bags_per_farmer": ceiling,
        "cap_applied": uncapped > ceiling,
        "rounding_rule": repo.ALLOCATION["rounding_rule"],
        "allocated_bags": allocated,
        "explanation": _allocation_explanation(acreage, per_acre, uncapped, allocated),
    }


def _allocation_explanation(
    acreage: float, per_acre: int, uncapped: int, allocated: int
) -> str:
    base = (
        f"{_fmt_acres(acreage)} acres x {per_acre} bags per acre "
        f"({repo.ALLOCATION['bags_per_acre_planting']} planting + "
        f"{repo.ALLOCATION['bags_per_acre_top_dressing']} top-dressing) "
        f"= {uncapped} bags"
    )
    if allocated < uncapped:
        return (
            f"{base}, reduced to the statutory ceiling of {allocated} bags "
            f"per farmer."
        )
    return f"{base}."


def _fmt_acres(acreage: float) -> str:
    """Render acreage without a trailing '.0' on whole numbers."""
    return f"{acreage:g}"


def _fmt_kes(amount: int) -> str:
    return f"KES {amount:,}"


# --------------------------------------------------------------------------
# Step 3 - collect blockers
# --------------------------------------------------------------------------


def _classify_documents(
    documents_held: list[str],
) -> tuple[set[str], set[str], list[str]]:
    """
    Sort the declared strings into: canonical documents held, rejection criteria
    triggered, and anything unrecognised.

    Unrecognised entries are returned rather than ignored so they can be
    reported back; silently dropping a farmer's "I have this" claim is how a
    triage engine ends up confidently wrong.
    """
    held: set[str] = set()
    triggered: set[str] = set()
    unrecognised: list[str] = []

    for raw in documents_held:
        if not raw or not raw.strip():
            continue

        document_code = repo.resolve_document(raw)
        if document_code is not None:
            held.add(document_code)
            continue

        criterion_code = repo.resolve_rejection_trigger(raw)
        if criterion_code is not None:
            triggered.add(criterion_code)
            continue

        unrecognised.append(raw.strip())

    return held, triggered, unrecognised


def _depot_blockers(depot: dict[str, Any], county: str) -> list[Blocker]:
    blockers: list[Blocker] = []

    if not repo.depot_serves_farmers(depot):
        # The depot's own note is preferred over the generic status description,
        # which would otherwise restate the status label almost verbatim. The
        # full description stays available in `status_definitions`.
        detail = depot.get("notes") or repo.STATUS_DEFINITIONS.get(
            depot["status"], {}
        ).get("description", "")
        reason = (
            f"{depot['name']} is not issuing subsidised fertilizer: "
            f"{repo.depot_status_label(depot).lower()}. {detail}"
        ).strip()
        blockers.append(
            Blocker(
                f"depot_not_serving:{depot['status'].lower()}",
                reason,
                next_step=(
                    f"Do not travel to {depot['name']}. Confirm an alternative "
                    "serving depot in your county before setting out."
                ),
            )
        )

    if not repo.depot_covers_county(depot, county):
        blockers.append(
            Blocker(
                "depot_outside_catchment",
                (
                    f"{depot['name']} does not serve {county} County. Its gazetted "
                    f"catchment is {_join(depot['catchment_counties'])}. Under NCPB "
                    "Circular 4B a farmer may only collect at a depot whose "
                    "catchment includes their county of registration."
                ),
                next_step=(
                    f"Select a depot whose catchment includes {county} County."
                ),
            )
        )

    return blockers


def _document_blockers(
    held: set[str],
    triggered: set[str],
    *,
    is_land_leased: bool,
    has_stamped_lease: bool,
) -> tuple[list[Blocker], list[dict[str, Any]]]:
    """Missing mandatory paperwork, declared disqualifying items, and the checklist."""
    blockers: list[Blocker] = []
    checklist: list[dict[str, Any]] = []

    for document in repo.REQUIRED_DOCUMENTS:
        code = document["code"]
        is_held = code in held
        checklist.append(
            {
                "code": code,
                "label": document["label"],
                "required": True,
                "held": is_held,
                "requirement_type": "mandatory",
                "authority": document["authority"],
            }
        )
        if not is_held:
            blockers.append(
                Blocker(
                    f"missing_document:{code}",
                    (
                        f"{document['label']} is mandatory and was not declared. "
                        f"Required by {document['authority']}."
                    ),
                    document_code=code,
                    next_step=f"Obtain your {document['label']} before travelling.",
                )
            )

    # The conditional lease document. `has_stamped_lease` is the explicit flag,
    # but a farmer may equally have named the document in documents_held, so
    # either satisfies the requirement.
    for document in repo.CONDITIONAL_DOCUMENTS:
        code = document["code"]
        is_held = has_stamped_lease or code in held
        checklist.append(
            {
                "code": code,
                "label": document["label"],
                "required": is_land_leased,
                "held": is_held,
                "requirement_type": "conditional",
                "authority": document["authority"],
            }
        )

    if is_land_leased:
        lease_code = "chiefs_stamped_lease_agreement"
        if not (has_stamped_lease or lease_code in held):
            # Reported under the circular's own rejection criterion so the
            # farmer sees the same wording a depot clerk would use.
            criterion = repo.rejection_criterion("unstamped_lease_agreement")
            blockers.append(
                Blocker(
                    "unstamped_lease_agreement",
                    (
                        "The land is declared as leased but no Official Chief's "
                        f"Stamped Lease Agreement is held. {criterion['reason']} "
                        f"({criterion['authority']})."
                    ),
                    document_code=lease_code,
                    next_step=(
                        "Have your lease agreement stamped by the Area Chief "
                        "before travelling."
                    ),
                )
            )

    # Items the farmer declared that actively disqualify them at the counter.
    for criterion_code in sorted(triggered):
        criterion = repo.rejection_criterion(criterion_code)
        if criterion is None:
            continue
        # Criteria scoped to leased land are irrelevant on owned holdings,
        # where no lease agreement is required in the first place.
        if criterion.get("scope") == "leased_land_only" and not is_land_leased:
            continue
        blockers.append(
            Blocker(
                criterion_code,
                f"{criterion['label']}. {criterion['reason']} "
                f"({criterion['authority']}).",
                next_step=_criterion_next_step(criterion_code),
            )
        )

    return blockers, checklist


def _criterion_next_step(criterion_code: str) -> str:
    steps = {
        "id_photocopy_presented": (
            "Carry your original National ID, not a photocopy."
        ),
        "expired_evoucher": (
            "Request a fresh KIAMIS e-voucher and wait for the new SMS code."
        ),
        "unstamped_lease_agreement": (
            "Have your lease agreement stamped by the Area Chief before travelling."
        ),
    }
    return steps.get(criterion_code, "Resolve this issue before travelling.")


def _entitlement_blockers(allocation: dict[str, Any]) -> list[Blocker]:
    if allocation["allocated_bags"] > 0:
        return []

    minimum = repo.ALLOCATION["min_acreage_acres"]
    return [
        Blocker(
            "below_minimum_acreage",
            (
                f"A declared acreage of {_fmt_acres(allocation['declared_acreage'])} "
                f"acres does not attract a whole 50kg bag. The circular issues "
                f"fertilizer only in sealed bags, so a minimum of {minimum} acres "
                "is needed to qualify for one bag."
            ),
            next_step=(
                "This holding is below the minimum acreage for the scheme. "
                "Confirm your registered acreage with your Ward Agricultural "
                "Officer."
            ),
        )
    ]


def _crop_scope_blockers(crop_type: str | None) -> tuple[list[Blocker], bool | None]:
    """
    Confirm the declared crop is inside the circular's crop schedule.

    This is a scope-of-entitlement check against a published list, not an
    agronomic assessment. No alternative crop is ever suggested.

    The crop is optional. The farmer wizard deliberately does not ask for it -
    none of the three questions the product answers depends on it, and putting
    a crop question in front of a farmer invites the reading that the service
    is assessing their farming choices. When it is omitted the check is skipped
    and `crop_within_gazetted_scope` is null rather than false, so "not
    declared" is never confused with "outside the schedule".
    """
    if crop_type is None or not crop_type.strip():
        return [], None

    if not repo.CROP_SCOPE.get("enforced"):
        return [], True

    if repo.resolve_crop(crop_type) is not None:
        return [], True

    return [
        Blocker(
            "crop_outside_gazetted_scope",
            (
                f"{crop_type!r} is not listed in the gazetted crop schedule for "
                f"this subsidy ({repo.CROP_SCOPE['basis']}), so no entitlement "
                "arises for this holding under the current circular."
            ),
            next_step=(
                "Confirm your registered crop with your Ward Agricultural "
                "Officer. Only crops listed in the circular's schedule attract "
                "this subsidy."
            ),
        )
    ], False


# --------------------------------------------------------------------------
# Narrative
# --------------------------------------------------------------------------


def _join(items: list[str]) -> str:
    """'A', 'A and B', 'A, B and C'."""
    items = [str(i) for i in items]
    if not items:
        return "none"
    if len(items) == 1:
        return items[0]
    return f"{', '.join(items[:-1])} and {items[-1]}"


def _proceed_summary(
    depot: dict[str, Any],
    location: dict[str, Any],
    allocation: dict[str, Any],
    total_cost: int,
    is_land_leased: bool,
) -> str:
    bags = allocation["allocated_bags"]
    parts = [
        f"Proceed to {depot['name']} in {depot['town']}.",
        (
            f"On {_fmt_acres(allocation['declared_acreage'])} declared acres in "
            f"{location['ward']} Ward you are entitled to {bags} x 50kg "
            f"{'bag' if bags == 1 else 'bags'} at "
            f"{_fmt_kes(repo.PRICING['price_per_bag_kes'])} per bag, "
            f"{_fmt_kes(total_cost)} in total."
        ),
        (
            f"The depot is {repo.depot_status_label(depot).lower()} and its "
            f"catchment covers {location['county']} County."
        ),
        (
            "All mandatory documents are accounted for"
            + (
                ", including the Chief's stamped lease agreement for the leased "
                "holding"
                if is_land_leased
                else ""
            )
            + "."
        ),
        (
            "Carry the original documents and pay at the depot counter; this "
            "service processes no payments."
        ),
    ]
    if allocation["cap_applied"]:
        parts.insert(
            2,
            (
                f"Your entitlement is capped at the statutory maximum of "
                f"{allocation['max_bags_per_farmer']} bags per farmer."
            ),
        )
    return " ".join(parts)


def _do_not_travel_summary(
    depot: dict[str, Any],
    blockers: list[Blocker],
    alternatives: list[dict[str, Any]],
) -> str:
    count = len(blockers)
    issue_word = "issue" if count == 1 else "issues"
    summary = (
        f"Do not travel to {depot['name']}. {count} {issue_word} would stop you "
        f"being served at the counter today: {_numbered(blockers)}"
    )
    if alternatives:
        names = [d["name"] for d in alternatives[:3]]
        summary += (
            f" Once resolved, {_join(names)} "
            f"{'is' if len(names) == 1 else 'are'} currently serving your county."
        )
    return summary


def _numbered(blockers: list[Blocker]) -> str:
    return " ".join(f"({i}) {b.reason}" for i, b in enumerate(blockers, start=1))


def _build_next_steps(
    blockers: list[Blocker],
    depot: dict[str, Any],
    served: bool,
) -> list[str]:
    """Ordered, purely procedural actions. Never agronomic guidance."""
    if served:
        return [
            f"Travel to {depot['name']} in {depot['town']} during counter hours "
            f"({depot['operating_hours']}).",
            "Present your original National ID, KIAMIS e-voucher SMS code and "
            "signed WAO form at the counter.",
            "Do NOT carry cash - it is not accepted. Pay to the NCPB till "
            "number displayed at the depot, or deposit at the bank the depot "
            "manager names, and keep the receipt.",
            "Collect your fertilizer and an official NCPB receipt.",
        ]

    steps: list[str] = []
    for blocker in blockers:
        if blocker.next_step and blocker.next_step not in steps:
            steps.append(blocker.next_step)
    steps.append(
        "Re-run this check once the issues above are cleared, then travel."
    )
    return steps


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def run_triage(
    *,
    county: str,
    constituency: str,
    ward: str,
    target_depot_id: str,
    acreage: float,
    crop_type: str | None = None,
    documents_held: list[str],
    is_land_leased: bool,
    has_stamped_lease: bool,
) -> dict[str, Any]:
    """
    Execute the full triage. Raises TriageInputError for unresolvable
    references; otherwise always returns a complete verdict.
    """
    # 1. references
    location = _resolve_location(county, constituency, ward)
    depot = _resolve_depot(target_depot_id)

    # 2. entitlement
    allocation = _calculate_allocation(acreage)
    allocated_bags = allocation["allocated_bags"]
    price_per_bag = repo.PRICING["price_per_bag_kes"]
    total_cost = allocated_bags * price_per_bag

    # 3. blockers, gathered in a stable, human-sensible order: where you are
    #    going, what you are carrying, then what you are entitled to.
    held, triggered, unrecognised = _classify_documents(documents_held)
    crop_blockers, crop_in_scope = _crop_scope_blockers(crop_type)

    document_blockers, checklist = _document_blockers(
        held,
        triggered,
        is_land_leased=is_land_leased,
        has_stamped_lease=has_stamped_lease,
    )

    blockers: list[Blocker] = [
        *_depot_blockers(depot, location["county"]),
        *document_blockers,
        *_entitlement_blockers(allocation),
        *crop_blockers,
    ]

    # De-duplicate by code while preserving order.
    seen: set[str] = set()
    unique_blockers: list[Blocker] = []
    for blocker in blockers:
        if blocker.code in seen:
            continue
        seen.add(blocker.code)
        unique_blockers.append(blocker)

    # 4. verdict
    will_be_served = not unique_blockers

    alternatives: list[dict[str, Any]] = []
    if not will_be_served:
        # Only offer alternatives when the chosen depot itself is the problem.
        depot_is_blocked = any(
            b.code.startswith("depot_not_serving") or b.code == "depot_outside_catchment"
            for b in unique_blockers
        )
        if depot_is_blocked:
            alternatives = [
                d
                for d in repo.serving_depots_for_county(location["county"])
                if d["depot_id"] != depot["depot_id"]
            ]

    summary = (
        _proceed_summary(depot, location, allocation, total_cost, is_land_leased)
        if will_be_served
        else _do_not_travel_summary(depot, unique_blockers, alternatives)
    )

    missing_documents = [
        repo.document_label(b.document_code)
        for b in unique_blockers
        if b.document_code is not None
    ]

    response: dict[str, Any] = {
        "verdict": {
            "will_be_served": will_be_served,
            "status": (
                TriageStatus.PROCEED if will_be_served else TriageStatus.DO_NOT_TRAVEL
            ),
            "summary": summary,
        },
        "gap_analysis": {
            "missing_documents": missing_documents,
            "rejection_reasons": [b.reason for b in unique_blockers],
        },
        "financial_breakdown": {
            "allocated_bags": allocated_bags,
            "price_per_bag": price_per_bag,
            "total_cost_kes": total_cost,
            "statutory_notice": repo.PRICING["statutory_notice"],
        },
        "policy_grounding": {
            "circular": repo.SCHEME["circular"],
            "depot_status": f"{depot['status']} - {repo.depot_status_label(depot)}",
            "operating_procedure": repo.SCHEME["operating_procedure"],
        },
        "resolved_location": location,
        "depot": _serialize_depot(depot),
        "document_checklist": checklist,
        "allocation_basis": {
            key: value
            for key, value in allocation.items()
            if key != "allocated_bags"
        },
        "alternative_depots": [_serialize_depot(d) for d in alternatives],
        "declared_crop": crop_type,
        "crop_within_gazetted_scope": crop_in_scope,
        # Always present, on PROCEED as much as on DO_NOT_TRAVEL. A farmer who
        # has just been told to travel is exactly the one about to set off with
        # the wrong means of payment.
        "payment_notice": {
            "headline": repo.PAYMENT_AT_DEPOT["headline"],
            "notice": repo.PAYMENT_AT_DEPOT["notice"],
            "accepted_means": list(repo.PAYMENT_AT_DEPOT["accepted_means"]),
            "authority": repo.PAYMENT_AT_DEPOT["authority"],
            "cash_accepted_at_depot": repo.PAYMENT_AT_DEPOT["cash_accepted_at_depot"],
        },
        "next_steps": _build_next_steps(unique_blockers, depot, will_be_served),
        "compliance": compliance_notice(),
    }

    if unrecognised:
        # Additive and advisory: an unrecognised string is never treated as a
        # held document, so it cannot flip a verdict to PROCEED.
        response["unrecognised_documents"] = unrecognised

    return response


def _serialize_depot(depot: dict[str, Any]) -> dict[str, Any]:
    """Add the derived status fields the API exposes on every depot."""
    return {
        **depot,
        "status_label": repo.depot_status_label(depot),
        "serves_farmers": repo.depot_serves_farmers(depot),
    }
