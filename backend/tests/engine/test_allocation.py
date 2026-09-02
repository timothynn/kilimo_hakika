"""Allocation maths.

The three worked examples in NCPB's own FAQ (Q8) are the golden cases. If these
ever fail, the number we show a farmer disagrees with the number the depot will
release, which is the single most expensive bug this project can ship.
"""

from __future__ import annotations

from decimal import ROUND_FLOOR, Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from kilimo_hakika.engine import allocation as allocation_mod


@pytest.mark.parametrize(
    ("acres", "expected_total"),
    [
        (3, 12),  # NCPB FAQ Q8: "A farmer with 3 acres ... up to a maximum of 12 bags"
        (15, 60),  # NCPB FAQ Q8: "A farmer with 15 acres can buy up to 60 bags"
        (25, 100),  # the cap and the rate meet exactly here
        (26, 100),  # NCPB FAQ Q8: "over 25 acres can buy up to 100 bags"
        (100, 100),
    ],
)
def test_ncpb_published_examples(pack, acres, expected_total):
    result = allocation_mod.compute(Decimal(acres), pack.allocation, basis="")
    assert result.total_bags == expected_total


def test_split_is_even_when_rates_are_equal(pack):
    result = allocation_mod.compute(Decimal(3), pack.allocation, basis="")
    assert (result.planting_bags, result.topdress_bags) == (6, 6)


def test_cap_splits_pro_rata_not_planting_first(pack):
    """A farmer over the cap must still get top dressing, not 100 planting bags."""
    result = allocation_mod.compute(Decimal(40), pack.allocation, basis="")
    assert result.cap_applied is True
    assert result.planting_bags == 50
    assert result.topdress_bags == 50


def test_fractional_acreage_floors(pack):
    """FLOOR is an interpretation, and a conservative one: never promise a bag
    the depot will not release."""
    result = allocation_mod.compute(Decimal("2.4"), pack.allocation, basis="")
    assert (result.planting_bags, result.topdress_bags, result.total_bags) == (4, 4, 8)


def test_small_holding_still_gets_an_allocation(pack):
    result = allocation_mod.compute(Decimal("0.5"), pack.allocation, basis="")
    assert result.total_bags == 2


@settings(max_examples=200, deadline=None)
@given(acres=st.decimals(min_value=Decimal("0.25"), max_value=Decimal("5000"), places=2))
def test_invariants_hold_for_any_acreage(pack, acres):
    result = allocation_mod.compute(acres, pack.allocation, basis="")
    cap = pack.allocation.max_total_bags

    assert result.total_bags <= cap, "the statutory cap is never exceeded"
    assert result.planting_bags + result.topdress_bags == result.total_bags
    assert result.planting_bags >= 0 and result.topdress_bags >= 0

    # cap_applied reflects the *floored* bag count, not raw acreage arithmetic:
    # 25.01 acres floors to exactly 100 bags, so the cap has not bitten.
    def floored(rate: Decimal) -> int:
        return int((acres * rate).quantize(Decimal(1), rounding=ROUND_FLOOR))

    raw = floored(pack.allocation.planting_bags_per_acre) + floored(pack.allocation.topdress_bags_per_acre)
    assert result.cap_applied == (raw > cap)


@settings(max_examples=100, deadline=None)
@given(
    a=st.decimals(min_value=Decimal("0.25"), max_value=Decimal("30"), places=2),
    b=st.decimals(min_value=Decimal("0.25"), max_value=Decimal("30"), places=2),
)
def test_monotonic_in_acreage(pack, a, b):
    small, large = min(a, b), max(a, b)
    lo = allocation_mod.compute(small, pack.allocation, basis="").total_bags
    hi = allocation_mod.compute(large, pack.allocation, basis="").total_bags
    assert lo <= hi, "more land can never mean fewer bags"
