"""Official cost: a price table, never a recommendation.

CLAUDE.md's original brief forbade fertilizer-choice advice outright; the
rewritten scope permits advice, but only from the assistant and only labelled as
such. The engine still does not choose. It returns every priced product with the
farmer's bag entitlement and the gazetted price, and flags whichever one the
farmer named. Ranking is absent by design.
"""

from __future__ import annotations

from decimal import Decimal

from .pack import RulePack, _text
from .types import Allocation, Costing, CostLine

CENTS = Decimal("0.01")


def compute(
    pack: RulePack,
    allocation: Allocation,
    *,
    selected_fertilizer: str | None,
    locale: str,
) -> Costing:
    lines: list[CostLine] = []

    for row in pack.prices:
        if row.purpose == "PLANTING":
            bags = allocation.planting_bags
        elif row.purpose == "TOPDRESS":
            bags = allocation.topdress_bags
        else:
            bags = allocation.total_bags

        name = _text(pack.fertilizers.get(row.fertilizer_code, {}), locale) or row.fertilizer_code
        lines.append(
            CostLine(
                fertilizer_code=row.fertilizer_code,
                fertilizer_name=name,
                purpose=row.purpose,
                bags=bags,
                price_kes_per_bag=row.price_kes_per_bag.quantize(CENTS),
                subtotal_kes=(row.price_kes_per_bag * bags).quantize(CENTS),
                selected=row.fertilizer_code == selected_fertilizer,
                citation=row.citation,
                citation_is_unverified=pack.citation_is_unverified(row.citation),
            )
        )

    lines.sort(key=lambda line: (line.purpose, line.fertilizer_code))

    return Costing(
        currency="KES",
        min_total_cost_kes=_cheapest_lawful_total(pack, allocation),
        lines=tuple(lines),
    )


def _cheapest_lawful_total(pack: RulePack, allocation: Allocation) -> Decimal | None:
    """The floor an official could legitimately charge for a full allocation.

    Cheapest planting product for the planting bags, plus cheapest top-dressing
    product for the top-dressing bags. `ANY`-purpose products (potash and the
    like) are excluded: they are not substitutes for either leg, and folding them
    in would produce a lower number than any real basket, which is worse than no
    number at all.
    """
    planting = [p.price_kes_per_bag for p in pack.prices if p.purpose == "PLANTING"]
    topdress = [p.price_kes_per_bag for p in pack.prices if p.purpose == "TOPDRESS"]
    if not planting or not topdress:
        return None
    total = min(planting) * allocation.planting_bags + min(topdress) * allocation.topdress_bags
    return total.quantize(CENTS)
