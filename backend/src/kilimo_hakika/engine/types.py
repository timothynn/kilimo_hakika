"""Value types for the triage engine.

Everything here is frozen. A verdict is a pure function of (pack, input, clock),
and immutable inputs and outputs are how that stays true under refactoring.

Stdlib only. See `tests/engine/test_purity.py`, which fails the build if this
package ever imports anything else or reads a wall clock.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum


class Verdict(StrEnum):
    PROCEED = "PROCEED"
    DO_NOT_TRAVEL = "DO_NOT_TRAVEL"


class ReasonKind(StrEnum):
    """Why the verdict is what it is.

    The last three are fail-closed states: the engine could not establish
    something it needed, so it refuses to send a farmer to a depot on its word.
    """

    READY = "READY"
    MISSING_REQUIREMENTS = "MISSING_REQUIREMENTS"
    DEPOT_UNKNOWN = "DEPOT_UNKNOWN"
    NO_EFFECTIVE_SEASON = "NO_EFFECTIVE_SEASON"
    PACK_INVALID = "PACK_INVALID"


class Severity(StrEnum):
    BLOCKER = "BLOCKER"
    ADVISORY = "ADVISORY"


class LandTenure(StrEnum):
    OWNED = "OWNED"
    LEASED = "LEASED"
    FAMILY_UNREGISTERED = "FAMILY_UNREGISTERED"
    UNKNOWN = "UNKNOWN"


class PackValidationError(Exception):
    """The pack cannot be trusted to produce a verdict."""


@dataclass(frozen=True, slots=True)
class TriageInput:
    acreage_acres: Decimal
    depot_code: str
    held_documents: frozenset[str]
    travel_date: date
    land_tenure: LandTenure = LandTenure.UNKNOWN
    registration_county_code: str | None = None
    collecting_in_person: bool = True
    fertilizer_code: str | None = None


@dataclass(frozen=True, slots=True)
class Finding:
    """A rule that matched. Blockers decide the verdict; advisories inform."""

    code: str
    kind: str
    severity: Severity
    message: str
    document_code: str | None
    label: str | None
    remedy: str | None
    # None only for engine-generated findings (depot unknown, no effective
    # season). Those are statements about this app's knowledge, not about the
    # law, so they must not carry a citation id no source backs.
    citation: str | None
    citation_is_unverified: bool


@dataclass(frozen=True, slots=True)
class Allocation:
    acreage_acres: Decimal
    planting_bags: int
    topdress_bags: int
    total_bags: int
    bag_weight_kg: Decimal
    max_total_bags: int
    cap_applied: bool
    basis: str
    citation: str


@dataclass(frozen=True, slots=True)
class CostLine:
    fertilizer_code: str
    fertilizer_name: str
    purpose: str
    bags: int
    price_kes_per_bag: Decimal
    subtotal_kes: Decimal
    selected: bool
    citation: str
    citation_is_unverified: bool


@dataclass(frozen=True, slots=True)
class Costing:
    currency: str
    min_total_cost_kes: Decimal | None
    lines: tuple[CostLine, ...]


@dataclass(frozen=True, slots=True)
class DepotView:
    code: str
    name: str
    county_code: str
    county_name: str
    open_on_travel_date: bool
    opens_at: str | None
    closes_at: str | None


@dataclass(frozen=True, slots=True)
class TraceEntry:
    """Every rule the engine considered, and what it decided.

    This is what makes a disputed verdict auditable: not "the app said no", but
    "rule DOC_EVOUCHER_CODE matched, citing MOALD-NFSP-2025-LAUNCH".
    """

    rule_code: str
    applied: bool
    matched: bool
    severity: Severity
    citation: str


@dataclass(frozen=True, slots=True)
class TriageResult:
    verdict: Verdict
    reason_kind: ReasonKind
    headline: str
    summary: str
    blockers: tuple[Finding, ...]
    advisories: tuple[Finding, ...]
    allocation: Allocation | None
    costing: Costing | None
    depot: DepotView | None
    pack_version: str
    season_code: str | None
    travel_date: date
    trace: tuple[TraceEntry, ...] = field(default=())

    @property
    def blocker_codes(self) -> tuple[str, ...]:
        return tuple(b.code for b in self.blockers)
