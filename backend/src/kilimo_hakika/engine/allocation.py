"""Bag allocation: how many bags the farmer's acreage entitles them to.

Every number comes from the pack. Nothing here knows that the rate happens to be
two bags per acre or that the cap happens to be 100 — changing either is a data
edit, per CLAUDE.md.
"""

from __future__ import annotations

from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal

from .pack import AllocationRule
from .types import Allocation

_ROUNDING = {
    "FLOOR": ROUND_FLOOR,
    "CEIL": ROUND_CEILING,
    "NEAREST": ROUND_HALF_UP,
}


def _round(value: Decimal, mode: str) -> int:
    return int(value.quantize(Decimal(1), rounding=_ROUNDING[mode]))


def compute(acreage_acres: Decimal, rule: AllocationRule, *, basis: str) -> Allocation:
    """Bags for planting and top dressing, capped at the season maximum.

    The cap is applied to the *total*, then split, so a farmer over the cap gets
    a usable mix rather than a full planting allocation and no top dressing.
    """
    planting_raw = _round(acreage_acres * rule.planting_bags_per_acre, rule.rounding_mode)
    topdress_raw = _round(acreage_acres * rule.topdress_bags_per_acre, rule.rounding_mode)
    raw_total = planting_raw + topdress_raw

    cap_applied = raw_total > rule.max_total_bags
    if not cap_applied:
        planting, topdress = planting_raw, topdress_raw
    elif rule.cap_split == "PLANTING_FIRST":
        planting = min(planting_raw, rule.max_total_bags)
        topdress = rule.max_total_bags - planting
    elif rule.cap_split == "TOPDRESS_FIRST":
        topdress = min(topdress_raw, rule.max_total_bags)
        planting = rule.max_total_bags - topdress
    else:  # PRO_RATA
        if raw_total == 0:
            planting = topdress = 0
        else:
            planting = int(
                (Decimal(rule.max_total_bags) * Decimal(planting_raw) / Decimal(raw_total)).quantize(
                    Decimal(1), rounding=ROUND_FLOOR
                )
            )
            topdress = rule.max_total_bags - planting

    return Allocation(
        acreage_acres=acreage_acres,
        planting_bags=planting,
        topdress_bags=topdress,
        total_bags=planting + topdress,
        bag_weight_kg=rule.bag_weight_kg,
        max_total_bags=rule.max_total_bags,
        cap_applied=cap_applied,
        basis=basis,
        citation=rule.citation,
    )
