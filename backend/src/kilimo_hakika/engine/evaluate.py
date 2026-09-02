"""The single entry point: `evaluate(pack, triage_input, locale)`.

Pure. No clock (the travel date is an input), no database, no network, no model.
Fails closed: anything the engine cannot establish yields DO_NOT_TRAVEL with a
`reason_kind` naming the gap, because the only acceptable direction to be wrong
in is the one that costs a farmer a bus fare instead of a wasted journey.
"""

from __future__ import annotations

from typing import Any

from . import allocation as allocation_mod
from . import costing as costing_mod
from . import predicates
from .pack import RulePack, _text
from .types import (
    DepotView,
    Finding,
    ReasonKind,
    Severity,
    TraceEntry,
    TriageInput,
    TriageResult,
    Verdict,
)

# Engine-level UI copy. Policy prose lives in the pack; these are the frame
# around it, and they are the only strings the engine owns.
COPY: dict[str, dict[str, str]] = {
    "en": {
        "ready_headline": "You can travel",
        "ready_summary": "Your documents meet the requirements for this depot.",
        "blocked_headline": "Do not travel yet",
        "blocked_one": "One thing is missing. Fix it before you spend money on transport.",
        "blocked_many": "{count} things are missing. Fix them before you spend money on transport.",
        "depot_unknown_headline": "Do not travel",
        "depot_unknown_summary": "This app does not have rules for that depot, so it cannot promise you will be served.",
        "no_season_headline": "Do not travel",
        "no_season_summary": "There are no published rules for {date}. Do not travel on this app's word for that date.",
        "depot_unknown_rule": "Depot not recognised",
        "no_season_rule": "No published rules for that date",
        "basis": "{planting} bags for planting and {topdress} for top dressing, per acre",
    },
    "sw": {
        "ready_headline": "Unaweza kusafiri",
        "ready_summary": "Vitu ulivyo navyo vinakidhi mahitaji ya depo hii.",
        "blocked_headline": "Usisafiri bado",
        "blocked_one": "Kitu kimoja kinakosekana. Kirekebishe kabla ya kutumia pesa za usafiri.",
        "blocked_many": "Vitu {count} vinakosekana. Virekebishe kabla ya kutumia pesa za usafiri.",
        "depot_unknown_headline": "Usisafiri",
        "depot_unknown_summary": "Programu hii haina kanuni za depo hiyo, kwa hivyo haiwezi kuhakikisha utahudumiwa.",
        "no_season_headline": "Usisafiri",
        "no_season_summary": "Hakuna kanuni zilizochapishwa kwa tarehe {date}. Usisafiri kwa msingi wa programu hii siku hiyo.",
        "depot_unknown_rule": "Depo haijatambuliwa",
        "no_season_rule": "Hakuna kanuni zilizochapishwa kwa tarehe hiyo",
        "basis": "Mifuko {planting} ya kupanda na {topdress} ya kukuzia, kwa ekari",
    },
}


def _copy(locale: str, key: str, **kwargs: Any) -> str:
    table = COPY.get(locale) or COPY["en"]
    template = table.get(key) or COPY["en"][key]
    return template.format(**kwargs) if kwargs else template


def evaluate(pack: RulePack, triage_input: TriageInput, locale: str = "en") -> TriageResult:
    locale = locale if locale in COPY else "en"
    depot = pack.depots.get(triage_input.depot_code)

    if depot is None:
        return _fail_closed(
            pack,
            triage_input,
            locale,
            ReasonKind.DEPOT_UNKNOWN,
            headline=_copy(locale, "depot_unknown_headline"),
            summary=_copy(locale, "depot_unknown_summary"),
            rule_message=_copy(locale, "depot_unknown_rule"),
            with_costing=pack.season_covers(triage_input.travel_date),
        )

    if not pack.season_covers(triage_input.travel_date):
        return _fail_closed(
            pack,
            triage_input,
            locale,
            ReasonKind.NO_EFFECTIVE_SEASON,
            headline=_copy(locale, "no_season_headline"),
            summary=_copy(locale, "no_season_summary", date=triage_input.travel_date.isoformat()),
            rule_message=_copy(locale, "no_season_rule"),
            with_costing=False,
            depot_view=_depot_view(pack, triage_input, locale),
        )

    context = _context(pack, triage_input)

    blockers: list[Finding] = []
    advisories: list[Finding] = []
    trace: list[TraceEntry] = []

    for rule in pack.rules:
        applies = predicates.matches(rule.applies_when, context, triage_input.held_documents)

        # A DOCUMENT rule fires only when the artifact is actually absent;
        # applies_when decides whether the requirement is in play at all.
        if rule.kind == "DOCUMENT":
            matched = applies and rule.document_code not in triage_input.held_documents
        else:
            matched = applies

        trace.append(
            TraceEntry(
                rule_code=rule.code,
                applied=applies,
                matched=matched,
                severity=rule.severity,
                citation=rule.citation,
            )
        )
        if not matched:
            continue

        finding = Finding(
            code=rule.code,
            kind=rule.kind,
            severity=rule.severity,
            message=_text(rule.message, locale) or rule.code,
            document_code=rule.document_code,
            label=pack.document_label(rule.document_code, locale),
            remedy=_text(rule.remedy, locale),
            citation=rule.citation,
            citation_is_unverified=pack.citation_is_unverified(rule.citation),
        )
        (blockers if rule.severity is Severity.BLOCKER else advisories).append(finding)

    alloc = allocation_mod.compute(
        triage_input.acreage_acres,
        pack.allocation,
        basis=_copy(
            locale,
            "basis",
            planting=_plain(pack.allocation.planting_bags_per_acre),
            topdress=_plain(pack.allocation.topdress_bags_per_acre),
        ),
    )
    cost = costing_mod.compute(pack, alloc, selected_fertilizer=triage_input.fertilizer_code, locale=locale)

    if blockers:
        verdict, reason = Verdict.DO_NOT_TRAVEL, ReasonKind.MISSING_REQUIREMENTS
        headline = _copy(locale, "blocked_headline")
        summary = (
            _copy(locale, "blocked_one")
            if len(blockers) == 1
            else _copy(locale, "blocked_many", count=len(blockers))
        )
    else:
        verdict, reason = Verdict.PROCEED, ReasonKind.READY
        headline = _copy(locale, "ready_headline")
        summary = _copy(locale, "ready_summary")

    return TriageResult(
        verdict=verdict,
        reason_kind=reason,
        headline=headline,
        summary=summary,
        blockers=tuple(blockers),
        advisories=tuple(advisories),
        allocation=alloc,
        costing=cost,
        depot=_depot_view(pack, triage_input, locale),
        pack_version=pack.version,
        season_code=pack.season.code,
        travel_date=triage_input.travel_date,
        trace=tuple(trace),
    )


def _plain(value: Any) -> str:
    """Render 2.000 as '2' so generated prose reads like prose."""
    text = str(value)
    return text.rstrip("0").rstrip(".") if "." in text else text


def _context(pack: RulePack, triage_input: TriageInput) -> dict[str, Any]:
    depot = pack.depots.get(triage_input.depot_code)
    weekday = triage_input.travel_date.isoweekday()
    if depot is None:
        open_on_date: bool | None = None
        county: str | None = None
    else:
        # A dated closure beats the weekly timetable.
        open_on_date = triage_input.travel_date not in depot.closures and weekday in depot.hours
        county = depot.county_code

    return {
        "acreage_acres": triage_input.acreage_acres,
        "depot_code": triage_input.depot_code,
        "land_tenure": str(triage_input.land_tenure),
        "travel_date": triage_input.travel_date.isoformat(),
        "collecting_in_person": triage_input.collecting_in_person,
        "registration_county_code": triage_input.registration_county_code,
        "depot_county_code": county,
        "travel_weekday": weekday,
        "depot_open_on_travel_date": open_on_date,
    }


def _depot_view(pack: RulePack, triage_input: TriageInput, locale: str) -> DepotView | None:
    depot = pack.depots.get(triage_input.depot_code)
    if depot is None:
        return None
    weekday = triage_input.travel_date.isoweekday()
    window = depot.hours.get(weekday)
    closed = triage_input.travel_date in depot.closures
    return DepotView(
        code=depot.code,
        name=depot.name,
        county_code=depot.county_code,
        county_name=pack.counties.get(depot.county_code, depot.county_code),
        open_on_travel_date=bool(window) and not closed,
        opens_at=window[0] if window else None,
        closes_at=window[1] if window else None,
    )


def _fail_closed(
    pack: RulePack,
    triage_input: TriageInput,
    locale: str,
    reason: ReasonKind,
    *,
    headline: str,
    summary: str,
    rule_message: str,
    with_costing: bool,
    depot_view: DepotView | None = None,
) -> TriageResult:
    """Build a red verdict for something the engine could not establish.

    The blocker carries no citation: it is a statement about this app's
    knowledge, not about the law, and pretending otherwise would put a citation
    id on something no source says.
    """
    alloc = None
    cost = None
    if with_costing:
        alloc = allocation_mod.compute(
            triage_input.acreage_acres,
            pack.allocation,
            basis=_copy(
                locale,
                "basis",
                planting=_plain(pack.allocation.planting_bags_per_acre),
                topdress=_plain(pack.allocation.topdress_bags_per_acre),
            ),
        )
        cost = costing_mod.compute(
            pack, alloc, selected_fertilizer=triage_input.fertilizer_code, locale=locale
        )

    return TriageResult(
        verdict=Verdict.DO_NOT_TRAVEL,
        reason_kind=reason,
        headline=headline,
        summary=summary,
        blockers=(
            Finding(
                code=f"ENGINE_{reason.value}",
                kind="ENGINE",
                severity=Severity.BLOCKER,
                message=rule_message,
                document_code=None,
                label=None,
                remedy=None,
                citation=None,
                citation_is_unverified=False,
            ),
        ),
        advisories=(),
        allocation=alloc,
        costing=cost,
        depot=depot_view,
        pack_version=pack.version,
        season_code=pack.season.code if with_costing else None,
        travel_date=triage_input.travel_date,
        trace=(),
    )
