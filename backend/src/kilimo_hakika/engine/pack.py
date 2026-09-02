"""Loading and validating a compiled rule pack.

A pack is the engine's entire world: rules, depots, documents, prices, caps and
citations, frozen together under one version. Validation happens once at load,
and a pack that fails it is never allowed to serve a verdict.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from . import predicates
from .types import PackValidationError, Severity

SUPPORTED_CONTRACTS = frozenset({"1.0"})
ROUNDING_MODES = frozenset({"FLOOR", "CEIL", "NEAREST"})
CAP_SPLITS = frozenset({"PRO_RATA", "PLANTING_FIRST", "TOPDRESS_FIRST"})
RULE_KINDS = frozenset({"DOCUMENT", "ELIGIBILITY", "TEMPORAL", "LOGISTICS"})
PURPOSES = frozenset({"PLANTING", "TOPDRESS", "ANY"})


def _dec(value: Any, where: str) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception as exc:
        raise PackValidationError(f"{where}: {value!r} is not a number") from exc


def _text(block: Any, locale: str) -> str | None:
    """Pull a localised string, falling back to English rather than to nothing."""
    if not isinstance(block, dict):
        return None
    value = block.get(locale) or block.get("en")
    return value if isinstance(value, str) and value.strip() else None


@dataclass(frozen=True, slots=True)
class Depot:
    code: str
    name: str
    county_code: str
    hours: dict[int, tuple[str, str]]
    closures: dict[date, str]


@dataclass(frozen=True, slots=True)
class Document:
    code: str
    label: dict[str, str]
    how_to_obtain: dict[str, str | None]
    is_physical: bool


@dataclass(frozen=True, slots=True)
class Rule:
    code: str
    kind: str
    document_code: str | None
    applies_when: Any
    severity: Severity
    message: dict[str, str]
    remedy: dict[str, str | None]
    citation: str


@dataclass(frozen=True, slots=True)
class PriceRow:
    fertilizer_code: str
    purpose: str
    price_kes_per_bag: Decimal
    citation: str


@dataclass(frozen=True, slots=True)
class AllocationRule:
    planting_bags_per_acre: Decimal
    topdress_bags_per_acre: Decimal
    max_total_bags: int
    bag_weight_kg: Decimal
    rounding_mode: str
    cap_split: str
    min_acres: Decimal
    citation: str


@dataclass(frozen=True, slots=True)
class Season:
    code: str
    label: dict[str, str]
    effective_from: date
    effective_to: date
    citation: str


@dataclass(frozen=True, slots=True)
class RulePack:
    version: str
    engine_contract: str
    scheme_code: str
    scheme_name: str
    season: Season
    counties: dict[str, str]
    depots: dict[str, Depot]
    documents: dict[str, Document]
    fertilizers: dict[str, dict[str, str]]
    allocation: AllocationRule
    prices: tuple[PriceRow, ...]
    rules: tuple[Rule, ...]
    citations: dict[str, dict[str, Any]]
    environment: str

    def citation_is_unverified(self, citation_id: str) -> bool:
        """PRESS counts as unverified for display: it is not a gazette."""
        source = self.citations.get(citation_id, {}).get("source_type")
        return source in ("UNVERIFIED", "PRESS")

    def document_label(self, code: str | None, locale: str) -> str | None:
        if code is None:
            return None
        doc = self.documents.get(code)
        return _text(doc.label, locale) if doc else None

    def season_covers(self, on: date) -> bool:
        return self.season.effective_from <= on <= self.season.effective_to


def _parse_date(value: Any, where: str) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError as exc:
            raise PackValidationError(f"{where}: {value!r} is not an ISO date") from exc
    raise PackValidationError(f"{where}: {value!r} is not a date")


def load(payload: dict[str, Any]) -> RulePack:
    """Parse and validate a compiled pack. Raises PackValidationError."""
    if not isinstance(payload, dict):
        raise PackValidationError("pack must be an object")

    contract = payload.get("engine_contract")
    if contract not in SUPPORTED_CONTRACTS:
        raise PackValidationError(
            f"engine_contract {contract!r} unsupported; this engine speaks {sorted(SUPPORTED_CONTRACTS)}"
        )

    version = payload.get("pack_version")
    if not isinstance(version, str) or not version:
        raise PackValidationError("pack_version is required")

    scheme = payload.get("scheme") or {}
    season_raw = payload.get("season")
    if not isinstance(season_raw, dict):
        raise PackValidationError("season is required; without it no date resolves to a rule set")

    citations = payload.get("citations") or {}
    if not isinstance(citations, dict):
        raise PackValidationError("citations must be an object")

    def require_citation(cid: Any, where: str) -> str:
        if not isinstance(cid, str) or not cid:
            raise PackValidationError(f"{where}: missing citation - a rule without a citation is not a rule")
        if cid not in citations:
            raise PackValidationError(f"{where}: citation {cid!r} is not in the pack")
        return cid

    season = Season(
        code=str(season_raw.get("code")),
        label=season_raw.get("label") or {},
        effective_from=_parse_date(season_raw.get("effective_from"), "season.effective_from"),
        effective_to=_parse_date(season_raw.get("effective_to"), "season.effective_to"),
        citation=require_citation(season_raw.get("citation"), "season"),
    )
    if season.effective_to < season.effective_from:
        raise PackValidationError("season.effective_to is before effective_from")

    counties = {c["code"]: c["name"] for c in payload.get("counties") or []}

    depots: dict[str, Depot] = {}
    for raw in payload.get("depots") or []:
        code = raw["code"]
        county = raw.get("county")
        if county not in counties:
            raise PackValidationError(f"depot {code}: county {county!r} is not in the pack")
        require_citation(raw.get("citation"), f"depot {code}")
        hours: dict[int, tuple[str, str]] = {}
        for weekday, window in (raw.get("hours") or {}).items():
            try:
                day = int(weekday)
            except (TypeError, ValueError) as exc:
                raise PackValidationError(f"depot {code}: weekday {weekday!r} is not an integer") from exc
            if not 1 <= day <= 7:
                raise PackValidationError(f"depot {code}: weekday {day} outside 1-7 (ISO, Monday=1)")
            hours[day] = (window["opens"], window["closes"])
        closures: dict[date, str] = {}
        for closure in raw.get("closures") or []:
            closures[_parse_date(closure.get("date"), f"depot {code} closure")] = (
                _text(closure.get("reason"), "en") or "Closed"
            )
        depots[code] = Depot(code=code, name=raw["name"], county_code=county, hours=hours, closures=closures)

    documents: dict[str, Document] = {}
    for raw in payload.get("documents") or []:
        documents[raw["code"]] = Document(
            code=raw["code"],
            label=raw.get("label") or {},
            how_to_obtain=raw.get("how_to_obtain") or {},
            is_physical=bool(raw.get("is_physical", True)),
        )

    fertilizers = {f["code"]: (f.get("name") or {}) for f in payload.get("fertilizers") or []}

    alloc_raw = payload.get("allocation")
    if not isinstance(alloc_raw, dict):
        raise PackValidationError("allocation is required; question 3 would be unanswerable without it")
    allocation = AllocationRule(
        planting_bags_per_acre=_dec(
            alloc_raw.get("planting_bags_per_acre"), "allocation.planting_bags_per_acre"
        ),
        topdress_bags_per_acre=_dec(
            alloc_raw.get("topdress_bags_per_acre"), "allocation.topdress_bags_per_acre"
        ),
        max_total_bags=int(alloc_raw.get("max_total_bags", 0)),
        bag_weight_kg=_dec(alloc_raw.get("bag_weight_kg", 50), "allocation.bag_weight_kg"),
        rounding_mode=str(alloc_raw.get("rounding_mode", "FLOOR")),
        cap_split=str(alloc_raw.get("cap_split", "PRO_RATA")),
        min_acres=_dec(alloc_raw.get("min_acres", 0), "allocation.min_acres"),
        citation=require_citation(alloc_raw.get("citation"), "allocation"),
    )
    if allocation.max_total_bags <= 0:
        raise PackValidationError("allocation.max_total_bags must be positive")
    if allocation.rounding_mode not in ROUNDING_MODES:
        raise PackValidationError(f"allocation.rounding_mode {allocation.rounding_mode!r} unknown")
    if allocation.cap_split not in CAP_SPLITS:
        raise PackValidationError(f"allocation.cap_split {allocation.cap_split!r} unknown")

    prices: list[PriceRow] = []
    for raw in payload.get("prices") or []:
        fert = raw.get("fertilizer")
        if fert not in fertilizers:
            raise PackValidationError(f"price references unknown fertilizer {fert!r}")
        purpose = raw.get("purpose")
        if purpose not in PURPOSES:
            raise PackValidationError(f"price {fert}: purpose {purpose!r} unknown")
        price = _dec(raw.get("price_kes_per_bag"), f"price {fert}")
        if price <= 0:
            raise PackValidationError(f"price {fert}: must be positive")
        prices.append(
            PriceRow(
                fertilizer_code=fert,
                purpose=purpose,
                price_kes_per_bag=price,
                citation=require_citation(raw.get("citation"), f"price {fert}"),
            )
        )

    rules: list[Rule] = []
    raw_rules = payload.get("rules") or []
    if not raw_rules:
        raise PackValidationError("pack has no rules; every input would return PROCEED")
    seen: set[str] = set()
    for raw in raw_rules:
        code = raw.get("code")
        if not isinstance(code, str) or not code:
            raise PackValidationError("rule with no code")
        if code in seen:
            raise PackValidationError(f"duplicate rule code {code!r}")
        seen.add(code)
        kind = raw.get("kind")
        if kind not in RULE_KINDS:
            raise PackValidationError(f"rule {code}: kind {kind!r} unknown")
        document_code = raw.get("document")
        if (kind == "DOCUMENT") != (document_code is not None):
            raise PackValidationError(
                f"rule {code}: DOCUMENT rules need a document and only DOCUMENT rules may have one"
            )
        if document_code is not None and document_code not in documents:
            raise PackValidationError(f"rule {code}: document {document_code!r} is not in the pack")
        severity = raw.get("severity")
        if severity not in (Severity.BLOCKER, Severity.ADVISORY):
            raise PackValidationError(f"rule {code}: severity {severity!r} unknown")
        message = raw.get("message") or {}
        if not _text(message, "en"):
            raise PackValidationError(f"rule {code}: needs an English message")
        predicates.validate(raw.get("applies_when"), where=f"rule {code}.applies_when")
        rules.append(
            Rule(
                code=code,
                kind=kind,
                document_code=document_code,
                applies_when=raw.get("applies_when"),
                severity=Severity(severity),
                message=message,
                remedy=raw.get("remedy") or {},
                citation=require_citation(raw.get("citation"), f"rule {code}"),
            )
        )

    return RulePack(
        version=version,
        engine_contract=contract,
        scheme_code=str(scheme.get("code", "")),
        scheme_name=str(scheme.get("name", "")),
        season=season,
        counties=counties,
        depots=depots,
        documents=documents,
        fertilizers=fertilizers,
        allocation=allocation,
        prices=tuple(prices),
        rules=tuple(rules),
        citations=citations,
        environment=str(payload.get("_environment", "unknown")),
    )
