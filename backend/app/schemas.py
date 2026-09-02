"""
Request and response models for the public API.

These double as the OpenAPI contract rendered at /docs, so every field carries
a description and the request model carries a worked example. The four response
blocks required by the triage specification - `verdict`, `gap_analysis`,
`financial_breakdown` and `policy_grounding` - are modelled exactly. The
remaining blocks are additive conveniences for the frontend and never replace
or reshape those four.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TriageStatus(str, Enum):
    """The two possible triage outcomes. There is no third, ambiguous state."""

    PROCEED = "PROCEED"
    DO_NOT_TRAVEL = "DO_NOT_TRAVEL"


# --------------------------------------------------------------------------
# Health
# --------------------------------------------------------------------------


class HealthResponse(BaseModel):
    status: str = Field(description="'ok' when the service is serving requests.")
    service: str = Field(description="Human-readable service name.")
    version: str = Field(description="Backend version.")
    scheme_id: str = Field(description="Identifier of the loaded subsidy scheme.")
    data_loaded: dict[str, int] = Field(
        description="Row counts of the reference data loaded into memory."
    )
    track_constraints: dict[str, str] = Field(
        description="The hard scope boundaries this service operates under."
    )


# --------------------------------------------------------------------------
# Geography
# --------------------------------------------------------------------------


class WardOut(BaseModel):
    ward_id: int = Field(description="Official IEBC ward ID (1-1450).")
    ward_name: str = Field(description="Canonical ward name in title case.")
    lookup_key: str = Field(
        description="Normalized match key (lowercase alphanumerics only)."
    )


class ConstituencyOut(BaseModel):
    constituency_id: int = Field(
        description="Official IEBC constituency ID (1-290)."
    )
    constituency_name: str = Field(description="Canonical constituency name.")
    lookup_key: str = Field(description="Normalized match key.")
    wards: list[WardOut] = Field(description="Wards inside this constituency.")


class CountyOut(BaseModel):
    county_code: int = Field(description="Official county code (1-47).")
    county_name: str = Field(description="Canonical county name.")
    lookup_key: str = Field(description="Normalized match key.")
    constituencies: list[ConstituencyOut] = Field(
        description="Constituencies inside this county."
    )


class GeoHierarchyResponse(BaseModel):
    """County -> Constituency -> Ward tree for cascading dropdowns."""

    source: str = Field(description="Provenance of the reference data.")
    source_files: list[str] = Field(description="Raw files the data was built from.")
    structural_authority: str = Field(
        description="Which raw file the hierarchy's structure and IDs came from."
    )
    totals: dict[str, int] = Field(
        description="Expected counts: 47 counties, 290 constituencies, 1450 wards."
    )
    counties: list[CountyOut] = Field(description="The full hierarchy.")


# --------------------------------------------------------------------------
# Depots
# --------------------------------------------------------------------------


class DepotOut(BaseModel):
    depot_id: str = Field(description="Stable depot identifier used by /api/triage.")
    name: str = Field(description="Official depot name.")
    town: str = Field(description="Town the depot is located in.")
    county: str = Field(description="County the depot is physically located in.")
    county_code: int = Field(description="Official code of the host county.")
    region: str = Field(description="NCPB operational region.")
    status: str = Field(
        description="ACTIVE, STOCK_DEPLETED, UNDER_MAINTENANCE or SUSPENDED."
    )
    status_label: str = Field(description="Plain-language reading of the status.")
    serves_farmers: bool = Field(
        description="Whether this status permits collection today."
    )
    catchment_counties: list[str] = Field(
        description="Counties whose farmers may collect at this depot."
    )
    operating_hours: str = Field(description="Published counter hours.")
    contact_office: str = Field(description="Responsible NCPB office.")
    notes: str = Field(description="Operational notes, empty when there are none.")


class DepotListResponse(BaseModel):
    network_name: str = Field(description="Name of the gazetted depot network.")
    source_citation: str = Field(description="Governing NCPB circular.")
    notice: str = Field(
        description="Statement that only Government depots are listed."
    )
    filtered_by_county: str | None = Field(
        default=None,
        description="Canonical county the list was filtered to, if any.",
    )
    count: int = Field(description="Number of depots returned.")
    status_definitions: dict[str, Any] = Field(
        description="Meaning of each depot status."
    )
    depots: list[DepotOut] = Field(description="The matching depots.")


# --------------------------------------------------------------------------
# Scheme
# --------------------------------------------------------------------------


class SchemeResponse(BaseModel):
    """
    The gazetted circular as served by /api/schemes/current.

    Passed through from `data/scheme_rules.json` unmodified so the frontend can
    render checklists and cost tables straight from the policy source.
    """

    model_config = ConfigDict(extra="allow")

    scheme_id: str = Field(description="Identifier of the scheme.")
    scheme_name: str = Field(description="Official scheme name.")
    source_citation: str = Field(description="Full citation of the governing policy.")
    circular: str = Field(description="MOALD circular reference.")
    operating_procedure: str = Field(description="NCPB operating circular reference.")
    gazette_status: str = Field(description="Gazettement state of the scheme.")
    effective_from: str = Field(description="First day of validity (ISO date).")
    effective_to: str = Field(description="Last day of validity (ISO date).")


# --------------------------------------------------------------------------
# Triage - request
# --------------------------------------------------------------------------


class TriageRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "county": "Uasin Gishu",
                    "constituency": "Soy",
                    "ward": "Moi's Bridge",
                    "target_depot_id": "ncpb_eldoret",
                    "acreage": 4.5,
                    "crop_type": "maize",
                    "documents_held": [
                        "Original National ID",
                        "KIAMIS E-Voucher SMS Code",
                        "Signed Ward Agricultural Officer (WAO) Form",
                    ],
                    "is_land_leased": False,
                    "has_stamped_lease": False,
                }
            ]
        }
    )

    county: str = Field(
        description="County of the holding. Matched case- and punctuation-insensitively.",
        examples=["Uasin Gishu"],
    )
    constituency: str = Field(
        description="Constituency of the holding; must sit inside the county.",
        examples=["Soy"],
    )
    ward: str = Field(
        description="Ward of the holding; must sit inside the constituency.",
        examples=["Moi's Bridge"],
    )
    target_depot_id: str = Field(
        description="Depot the farmer intends to travel to, from GET /api/depots.",
        examples=["ncpb_eldoret"],
    )
    acreage: float = Field(
        gt=0,
        le=100_000,
        description="Declared acreage under the named crop. Must be greater than 0.",
        examples=[4.5],
    )
    crop_type: str = Field(
        min_length=1,
        max_length=120,
        description=(
            "Plain crop name, e.g. 'maize'. Used only to confirm the holding is "
            "within the circular's gazetted crop scope. This service returns no "
            "agronomic advice, and requests phrased as agronomy questions are "
            "refused with HTTP 422."
        ),
        examples=["maize"],
    )
    documents_held: list[str] = Field(
        default_factory=list,
        description=(
            "Documents the farmer physically holds. Accepts canonical codes, "
            "official labels or listed aliases. Disqualifying items such as "
            "'ID photocopy' or 'expired voucher' may also be declared here and "
            "will raise the matching rejection reason."
        ),
        examples=[["Original National ID", "KIAMIS E-Voucher SMS Code"]],
    )
    is_land_leased: bool = Field(
        default=False,
        description="True when the holding is leased rather than owned.",
    )
    has_stamped_lease: bool = Field(
        default=False,
        description=(
            "True when an Official Chief's Stamped Lease Agreement is held. "
            "Only consulted when is_land_leased is true."
        ),
    )


# --------------------------------------------------------------------------
# Triage - response
# --------------------------------------------------------------------------


class Verdict(BaseModel):
    will_be_served: bool = Field(
        description="True only if the farmer will be served at the counter today."
    )
    status: TriageStatus = Field(
        description="PROCEED or DO_NOT_TRAVEL. Mirrors will_be_served exactly."
    )
    summary: str = Field(
        description="One-paragraph plain-language explanation of the verdict."
    )


class GapAnalysis(BaseModel):
    missing_documents: list[str] = Field(
        description="Mandatory documents the farmer does not yet hold."
    )
    rejection_reasons: list[str] = Field(
        description=(
            "Every reason the farmer would be turned away, each citing the "
            "governing circular clause. Empty when the verdict is PROCEED."
        )
    )


class FinancialBreakdown(BaseModel):
    allocated_bags: int = Field(
        description="Whole 50kg bags the farmer is entitled to under the circular."
    )
    price_per_bag: int = Field(
        description="Statutory subsidised price per 50kg bag, in KES."
    )
    total_cost_kes: int = Field(
        description="allocated_bags x price_per_bag, in KES."
    )
    statutory_notice: str = Field(
        description=(
            "Statement of what this figure is, and that no payment is processed "
            "by this service."
        )
    )


class PolicyGrounding(BaseModel):
    circular: str = Field(description="The MOALD circular the verdict rests on.")
    depot_status: str = Field(description="Operational status of the target depot.")
    operating_procedure: str = Field(
        description="The NCPB operating circular governing counter procedure."
    )


class AllocationBasis(BaseModel):
    """Shows the arithmetic behind `allocated_bags` so the figure is auditable."""

    declared_acreage: float = Field(description="Acreage as declared by the farmer.")
    bags_per_acre: int = Field(description="Planting plus top-dressing bags per acre.")
    planting_bags_per_acre: int = Field(description="Planting component per acre.")
    top_dressing_bags_per_acre: int = Field(
        description="Top-dressing component per acre."
    )
    uncapped_entitlement_bags: int = Field(
        description="Entitlement before the per-farmer ceiling is applied."
    )
    max_bags_per_farmer: int = Field(description="Statutory per-farmer ceiling.")
    cap_applied: bool = Field(
        description="True when the ceiling reduced the entitlement."
    )
    rounding_rule: str = Field(description="How fractional bags are handled.")
    explanation: str = Field(description="The calculation in one sentence.")


class ResolvedLocation(BaseModel):
    """Canonical, ID-bearing form of the location the farmer submitted."""

    county: str
    county_code: int
    constituency: str
    constituency_id: int
    ward: str
    ward_id: int


class DocumentCheckItem(BaseModel):
    """One row of the counter checklist, ready to render as a tick list."""

    code: str = Field(description="Canonical document code.")
    label: str = Field(description="Official document name.")
    required: bool = Field(
        description="Whether this document is required for this specific farmer."
    )
    held: bool = Field(description="Whether the farmer declared holding it.")
    requirement_type: str = Field(
        description="'mandatory' for all farmers, 'conditional' when leasing."
    )
    authority: str = Field(description="Circular clause imposing the requirement.")


class TriageResponse(BaseModel):
    # --- the four blocks required by the specification -------------------
    verdict: Verdict
    gap_analysis: GapAnalysis
    financial_breakdown: FinancialBreakdown
    policy_grounding: PolicyGrounding

    # --- additive detail for the frontend --------------------------------
    resolved_location: ResolvedLocation = Field(
        description="The submitted location resolved to canonical names and official IDs."
    )
    depot: DepotOut = Field(description="Full record of the target depot.")
    document_checklist: list[DocumentCheckItem] = Field(
        description="Per-document held/missing state, including conditional items."
    )
    allocation_basis: AllocationBasis = Field(
        description="The entitlement arithmetic, shown for auditability."
    )
    alternative_depots: list[DepotOut] = Field(
        description=(
            "Serving Government depots in the farmer's county, populated only "
            "when the chosen depot cannot serve them. Never a vendor listing."
        )
    )
    declared_crop: str = Field(description="The crop as submitted by the farmer.")
    crop_within_gazetted_scope: bool = Field(
        description=(
            "Whether the declared crop falls inside the circular's crop schedule. "
            "A statutory scope fact, not an agronomic assessment."
        )
    )
    next_steps: list[str] = Field(
        description="Ordered, purely procedural actions for the farmer."
    )
    compliance: dict[str, str] = Field(
        description="The scope boundaries this verdict was produced under."
    )


class ErrorResponse(BaseModel):
    detail: Any = Field(description="Error description.")
