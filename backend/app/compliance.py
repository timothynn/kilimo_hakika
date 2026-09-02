"""
Enforcement of the three hard track constraints.

Constraints 2 (no payments) and 3 (no marketplace) are structural: this service
has no payment client, no mobile-money credentials, no order/basket model and no
vendor table, so there is nothing to guard at request time. The depot list is
drawn exclusively from the gazetted NCPB network.

Constraint 1 (no agronomic advice) is the one that needs an active guard,
because `crop_type` on the triage request is free text. A farmer - or a client
developer wiring up a chat box - can try to smuggle an agronomy question
through it ("what fertilizer is best for maize?"). This module detects that and
the router refuses the request rather than answering it.

The declared crop is used for exactly one purpose: confirming the holding falls
inside the gazetted scope of the circular. That is a statutory scope fact. No
recommendation is produced, and no alternative crop is ever suggested.
"""

from __future__ import annotations

import re

from .config import TRACK_CONSTRAINTS

# Phrases that indicate the caller wants agronomic guidance rather than
# declaring a crop. Matched case-insensitively on word boundaries.
_ADVICE_PATTERNS: tuple[str, ...] = (
    r"\brecommend\w*\b",
    r"\badvi[cs]e\w*\b",
    r"\bsuggest\w*\b",
    r"\bbest\b",
    r"\bwhich\b",
    r"\bwhat\b",
    r"\bhow\s+(?:much|many|do|to|should)\b",
    r"\bwhen\s+(?:to|should)\b",
    r"\bshould\s+i\b",
    r"\bsuitab\w*\b",
    r"\bidea?l\b",
    r"\bnpk\b",
    r"\bsoil\s+(?:ph|test|type|health|fertility)\b",
    r"\bph\s+level\b",
    r"\bspacing\b",
    r"\bpest\w*\b",
    r"\bdiseas\w*\b",
    r"\byield\w*\b",
    r"\bharvest\w*\b",
    r"\bplant(?:ing)?\s+(?:date|time|season|depth)\b",
    r"\btop[\s-]?dress(?:ing)?\s+(?:rate|schedule|when)\b",
    r"\bvariety\s+(?:choice|selection|to)\b",
    r"\bintercrop\w*\b",
    r"\brotat\w*\b",
    r"\bmanure\b",
    r"\bcompost\b",
    r"\bdap\s+or\b",
    r"\bor\s+can\b",
)

_ADVICE_REGEX = re.compile("|".join(_ADVICE_PATTERNS), re.IGNORECASE)

# A crop declaration is a short noun phrase. Real gazetted entries run to at
# most three words ("irish potatoes", "finger millet"), so anything longer is
# prose rather than a declaration.
_MAX_CROP_WORDS = 4

REFUSAL_MESSAGE = (
    "Kilimo Hakika cannot answer agronomic questions. This service is a "
    "government subsidy and depot triage engine: it reports your statutory "
    "entitlement, the mandatory paperwork and whether your chosen NCPB depot "
    "can serve you. It does not recommend crops, soils, seeds or fertilizers. "
    "Please submit 'crop_type' as a plain crop name (for example \"maize\"), "
    "and speak to your Ward Agricultural Officer for agronomic guidance."
)


def detect_advice_request(text: str) -> str | None:
    """
    Return a human-readable reason if `text` reads as a request for agronomic
    advice rather than a plain crop declaration, else None.
    """
    if text is None:
        return None

    candidate = text.strip()
    if not candidate:
        return None

    if "?" in candidate:
        return "The declared crop contains a question."

    match = _ADVICE_REGEX.search(candidate)
    if match:
        return (
            f"The declared crop contains advisory language ({match.group(0)!r}), "
            "which reads as a request for agronomic guidance."
        )

    if len(candidate.split()) > _MAX_CROP_WORDS:
        return (
            "The declared crop reads as a sentence rather than a crop name. "
            "Submit a plain crop name."
        )

    return None


def compliance_notice() -> dict[str, str]:
    """The standing compliance boundary, attached to every triage response."""
    return dict(TRACK_CONSTRAINTS)
