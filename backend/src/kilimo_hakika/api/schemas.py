"""Request models and response serialisers - the frontend contract in code.

See docs/design/api-contract.md. Response shapes are built by hand rather than
inferred, because the contract guarantees (allocation always present, verdict
binary, every statutory number carrying a citation) are promises to another team.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from ..engine import RulePack, TriageResult
from ..engine.pack import _text


class TriageRequest(BaseModel):
    acreage_acres: Decimal | None = Field(default=None, gt=0, le=10_000)
    depot_code: str = Field(min_length=1, max_length=64)
    held_documents: list[str] = Field(default_factory=list, max_length=64)
    land_tenure: Literal["OWNED", "LEASED", "FAMILY_UNREGISTERED", "UNKNOWN"] | None = None
    travel_date: date | None = None
    registration_county_code: str | None = Field(default=None, max_length=16)
    collecting_in_person: bool = True
    fertilizer_code: str | None = Field(default=None, max_length=32)

    @field_validator("held_documents")
    @classmethod
    def dedupe(cls, value: list[str]) -> list[str]:
        return sorted(set(value))


class OtpStartRequest(BaseModel):
    phone: str = Field(min_length=9, max_length=20)


class OtpVerifyRequest(BaseModel):
    phone: str = Field(min_length=9, max_length=20)
    code: str = Field(min_length=4, max_length=8)
    shared_device: bool = False


class StaffLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=1, max_length=200)
    totp_code: str | None = Field(default=None, max_length=8)


class ProfileRequest(BaseModel):
    registration_county_code: str | None = Field(default=None, max_length=16)
    default_acreage_acres: Decimal | None = Field(default=None, gt=0, le=10_000)
    land_tenure: Literal["OWNED", "LEASED", "FAMILY_UNREGISTERED", "UNKNOWN"] | None = None
    kiamis_registered: bool | None = None
    national_id: str | None = Field(default=None, max_length=32)


class ConsentRequest(BaseModel):
    purpose: Literal["ACCOUNT", "ASSISTANT_AI", "ANALYTICS"]
    granted: bool
    policy_version: str = Field(default="2026-09-01", max_length=32)


class GapStateRequest(BaseModel):
    gap_state: dict[str, Literal["PENDING", "RESOLVED", "BLOCKED"]]


class AssistantMessageRequest(BaseModel):
    conversation_id: str | None = None
    text: str = Field(min_length=1, max_length=2_000)
    locale: Literal["en", "sw"] = "en"
    depot_code: str | None = None


def money(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def serialise_finding(finding: Any) -> dict[str, Any]:
    return {
        "code": finding.code,
        "document_code": finding.document_code,
        "label": finding.label,
        "message": finding.message,
        "remedy": finding.remedy,
        "citation": finding.citation,
        "citation_is_unverified": finding.citation_is_unverified,
    }


def serialise_triage(
    result: TriageResult,
    *,
    pack_source: str,
    environment: str,
    history_id: str | None,
    include_trace: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "verdict": str(result.verdict),
        "reason_kind": str(result.reason_kind),
        "headline": result.headline,
        "summary": result.summary,
        "blockers": [serialise_finding(b) for b in result.blockers],
        "advisories": [serialise_finding(a) for a in result.advisories],
        "allocation": None,
        "costing": None,
        "depot": None,
        "history_id": history_id,
        "meta": {
            "rule_pack_version": result.pack_version,
            "engine_version": "1.0.0",
            "season_code": result.season_code,
            "travel_date": result.travel_date.isoformat(),
            "pack_source": pack_source,
            "environment": environment,
        },
    }

    if result.allocation is not None:
        a = result.allocation
        payload["allocation"] = {
            "acreage_acres": float(a.acreage_acres),
            "planting_bags": a.planting_bags,
            "topdress_bags": a.topdress_bags,
            "total_bags": a.total_bags,
            "bag_weight_kg": float(a.bag_weight_kg),
            "cap_applied": a.cap_applied,
            "max_total_bags": a.max_total_bags,
            "basis": a.basis,
            "citation": a.citation,
        }

    if result.costing is not None:
        c = result.costing
        payload["costing"] = {
            "currency": c.currency,
            "min_total_cost_kes": money(c.min_total_cost_kes),
            "lines": [
                {
                    "fertilizer_code": line.fertilizer_code,
                    "fertilizer_name": line.fertilizer_name,
                    "purpose": line.purpose,
                    "bags": line.bags,
                    "price_kes_per_bag": money(line.price_kes_per_bag),
                    "subtotal_kes": money(line.subtotal_kes),
                    "selected": line.selected,
                    "citation": line.citation,
                    "citation_is_unverified": line.citation_is_unverified,
                }
                for line in c.lines
            ],
        }

    if result.depot is not None:
        d = result.depot
        payload["depot"] = {
            "code": d.code,
            "name": d.name,
            "county_code": d.county_code,
            "county_name": d.county_name,
            "open_on_travel_date": d.open_on_travel_date,
            "opens_at": d.opens_at,
            "closes_at": d.closes_at,
        }

    if include_trace:
        payload["trace"] = [
            {
                "rule_code": t.rule_code,
                "applied": t.applied,
                "matched": t.matched,
                "severity": str(t.severity),
                "citation": t.citation,
            }
            for t in result.trace
        ]

    return payload


def serialise_reference(pack: RulePack, locale: str) -> dict[str, Any]:
    """Everything the wizard needs to render itself, in one cacheable payload."""
    required_always: set[str] = set()
    conditional: set[str] = set()
    for rule in pack.rules:
        if rule.document_code is None:
            continue
        if rule.applies_when is None and rule.severity == "BLOCKER":
            required_always.add(rule.document_code)
        else:
            conditional.add(rule.document_code)
    conditional -= required_always

    return {
        "rule_pack_version": pack.version,
        "environment": pack.environment,
        "scheme": {"code": pack.scheme_code, "name": pack.scheme_name},
        "season": {
            "code": pack.season.code,
            "label": _text(pack.season.label, locale),
            "effective_from": pack.season.effective_from.isoformat(),
            "effective_to": pack.season.effective_to.isoformat(),
        },
        "counties": [
            {"code": code, "name": name} for code, name in sorted(pack.counties.items(), key=lambda kv: kv[1])
        ],
        "depots": [
            {
                "code": d.code,
                "name": d.name,
                "county_code": d.county_code,
                "county_name": pack.counties.get(d.county_code, d.county_code),
                "open_days": sorted(d.hours),
                "opens_at": next(iter(d.hours.values()))[0] if d.hours else None,
                "closes_at": next(iter(d.hours.values()))[1] if d.hours else None,
            }
            for d in sorted(pack.depots.values(), key=lambda d: d.name)
        ],
        "documents": [
            {
                "code": doc.code,
                "label": _text(doc.label, locale),
                "how_to_obtain": _text(doc.how_to_obtain, locale),
                "is_physical": doc.is_physical,
                "relevance": "ALWAYS" if doc.code in required_always else "CONDITIONAL",
            }
            for doc in pack.documents.values()
            if doc.code in required_always | conditional
        ],
        "fertilizers": [
            {"code": code, "name": _text(name, locale) or code} for code, name in pack.fertilizers.items()
        ],
        "land_tenures": [
            {"code": "OWNED", "label": "I own this land"},
            {"code": "LEASED", "label": "I lease this land"},
            {"code": "FAMILY_UNREGISTERED", "label": "Family land, not in my name"},
            {"code": "UNKNOWN", "label": "I would rather not say"},
        ],
        "allocation": {
            "min_acres": float(pack.allocation.min_acres),
            "max_total_bags": pack.allocation.max_total_bags,
            "bag_weight_kg": float(pack.allocation.bag_weight_kg),
        },
    }
