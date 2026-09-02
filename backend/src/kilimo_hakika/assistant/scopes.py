"""What the assistant may do, per caller.

The helper is on every page, including the landing page where nobody is signed
in. It must be useful there without being a side door into anything personal.

Two decisions make that safe:

  - **Tools are gated by permission, not by prompt.** Each tool names the
    permission it needs; a caller without it never sees the tool in the request,
    so the model cannot call it, cannot be talked into calling it, and cannot
    reveal that it exists. A signed-out visitor has no permissions, so only the
    two public-policy tools are offered.
  - **The audience only shapes the wording.** It decides what the assistant says
    about its own limits, never what it can reach. If the two ever disagree, the
    permission wins, because the permission is what the code enforces.

Tiers, in the order a person meets them:

  VISITOR      signed out, landing page. Explains what the app does and what the
               rules say, from public policy. No verdict, nothing personal.
               Points at the free depot check and at signing in for the rest.
  FARMER       + a verdict from their own saved profile.
  BUSINESS     a retailer or wholesaler. Same policy access.
  ASSOCIATION  a supplier association. Same policy access.
  STAFF        internal. Same tools; the wording drops the consumer framing.

This app carries no market, price-comparison or vendor data of any kind, so no
tier grants any. That is a hard product boundary, not a permission level.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .privacy import pseudonym

# The permission each tool requires. `None` means the tool returns published
# government policy and needs no account - that is the whole public promise of
# the product, and it is the same data the unauthenticated /reference endpoint
# already serves.
TOOL_PERMISSIONS: dict[str, str | None] = {
    "search_policy": None,
    "get_document_guidance": None,
    "get_triage_verdict": "triage.run",
}


class Audience(StrEnum):
    VISITOR = "VISITOR"
    FARMER = "FARMER"
    BUSINESS = "BUSINESS"
    ASSOCIATION = "ASSOCIATION"
    STAFF = "STAFF"


_GUIDANCE: dict[Audience, str] = {
    Audience.VISITOR: """You are talking to someone who is NOT signed in, on a public page.

What you can do here: explain what this app does, explain what the government rules require, explain what a document is and where to get it, all from the sources below.

What you must NOT do here, because you have no tool for it and no data about this person:
- Do not give a depot verdict, and do not say whether they will be served. You cannot check. Point them at the free depot check on this site: it asks three questions and needs no account.
- Do not quote seller, retail or wholesale prices, and do not compare sellers. This app holds no such data. You may quote official gazetted prices from the sources, because those are public.
- Do not ask for, and do not accept, any personal detail - no name, no phone number, no ID number, no location beyond a county. If they offer one, tell them they do not need to give it and carry on without it.
- Do not claim to remember them or to have any record of them.

If they want a verdict or their own history, say plainly that the depot check is free and needs no account, and that signing in adds history.""",
    Audience.FARMER: """You are talking to a signed-in farmer, known to you only as {pseudonym}.

You may run the official depot check for them with get_triage_verdict - it reads the acreage, county and land tenure they saved to their profile.

You do not know their name, their phone number or their ID number, and you must never ask for any of them. Refer to them as "you"; the pseudonym is for your reference only and should not be shown to them.""",
    Audience.BUSINESS: """You are talking to a signed-in retail or wholesale business, known to you only as {pseudonym}.

You may explain the government rules and quote official gazetted prices and caps.

Two things to hold firm on:
- The gazetted price is a statutory figure for the subsidised programme. It is not a wholesale price, a margin, or a recommended resale price. Do not present it as any of those, and do not help set a resale price against it.
- This app does not sell, list, broker or compare sellers, and holds no supplier prices at all. If asked for any of that, say it is not what this app does.

You do not know who this person is and must not ask.""",
    Audience.ASSOCIATION: """You are talking to a signed-in supplier association, known to you only as {pseudonym}.

You may explain the government rules and quote official gazetted prices and caps.

Gazetted prices and allocation caps come from government sources and are binding. This app publishes no association notices, supplier prices or demand and supply signals, and you have no tool for them - if asked, say plainly that it is not what this app does.

You do not know who this person is and must not ask.""",
    Audience.STAFF: """You are talking to an internal staff user, known to you only as {pseudonym}.

Normal rules still apply: verdicts come from the tool, every rule claim carries its source, and unverified sources are labelled. You may explain how a rule resolved and which source it rests on.

You have no access to any farmer's personal details and must not speculate about individuals. You must not ask this user for anyone's name, phone number or ID number, including their own - you cannot receive them and you do not need them.""",
}


@dataclass(frozen=True)
class Scope:
    audience: Audience
    pseudonym: str
    tools: tuple[dict[str, Any], ...]

    @property
    def is_signed_in(self) -> bool:
        return self.audience is not Audience.VISITOR

    def guidance(self) -> str:
        return _GUIDANCE[self.audience].format(pseudonym=self.pseudonym)

    def allows(self, tool_name: str) -> bool:
        return any(tool["name"] == tool_name for tool in self.tools)


def audience_for(roles: frozenset[str] | set[str] | None) -> Audience:
    """Pick the wording tier from the caller's roles.

    Checked most specific first: someone who is both staff and a farmer gets the
    staff wording, because that is the narrower, less consumer-facing register.
    """
    held = set(roles or ())
    if not held:
        return Audience.VISITOR
    if held & {"policy_author", "policy_reviewer", "policy_publisher", "admin"}:
        return Audience.STAFF
    if "supplier_association" in held:
        return Audience.ASSOCIATION
    if held & {"retailer", "wholesaler"}:
        return Audience.BUSINESS
    return Audience.FARMER


def resolve(
    *,
    user_id: str | None,
    roles: frozenset[str] | set[str] | None,
    permissions: frozenset[str] | set[str] | None,
    all_tools: list[dict[str, Any]],
) -> Scope:
    """Build the scope for one caller. Pass `user_id=None` for a signed-out visitor."""
    granted = set(permissions or ())

    def offered(tool: dict[str, Any]) -> bool:
        # Fail closed: a tool nobody has mapped a permission for is withheld
        # rather than published, so adding a tool without deciding who may use
        # it makes it unavailable instead of public.
        if tool["name"] not in TOOL_PERMISSIONS:
            return False
        needed = TOOL_PERMISSIONS[tool["name"]]
        return needed is None or needed in granted

    return Scope(
        audience=audience_for(roles),
        pseudonym=pseudonym(user_id),
        tools=tuple(tool for tool in all_tools if offered(tool)),
    )
