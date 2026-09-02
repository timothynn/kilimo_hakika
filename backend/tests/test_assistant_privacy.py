"""The identity boundary between a farmer and the model provider.

These tests are the enforcement. The system prompt also asks the model not to
collect identifiers, but a prompt is a request; this module is the part that
holds when the request is ignored, jailbroken, or simply pre-empted by a farmer
typing their ID unprompted.
"""

from __future__ import annotations

import pytest

from kilimo_hakika.assistant import privacy, scopes
from kilimo_hakika.assistant.scopes import Audience

ALL_TOOLS = [
    {"name": "search_policy"},
    {"name": "get_document_guidance"},
    {"name": "get_triage_verdict"},
    {"name": "get_market_signals"},
]


# --- scrubbing -------------------------------------------------------------


@pytest.mark.parametrize(
    "typed",
    [
        "My number is 0712345678",
        "call me on 0712 345 678",
        "+254712345678",
        "254 712 345 678",
        "reach me 0112345678",  # Safaricom's 01x range
    ],
)
def test_phone_numbers_never_reach_the_model(typed: str) -> None:
    clean, found = privacy.scrub(typed)
    assert "phone" in found
    assert "712345678" not in clean.replace(" ", "")
    assert "0112345678" not in clean.replace(" ", "")


@pytest.mark.parametrize("typed", ["My ID is 12345678", "id 1234567 please", "23145678"])
def test_national_id_numbers_never_reach_the_model(typed: str) -> None:
    clean, found = privacy.scrub(typed)
    assert "national_id" in found
    assert "[ID number removed]" in clean


def test_email_is_removed() -> None:
    clean, found = privacy.scrub("write to wanjiku.kamau@example.co.ke")
    assert found == ["email"]
    assert "@example.co.ke" not in clean


def test_the_question_survives_the_scrub() -> None:
    """Scrubbing must not destroy the message - the farmer still needs an answer."""
    clean, _ = privacy.scrub("My ID is 12345678, what do I need to bring to Nakuru?")
    assert "what do I need to bring to Nakuru?" in clean


@pytest.mark.parametrize(
    "harmless",
    [
        "I farm 2.5 acres",
        "how many bags for 12 acres?",
        "is 2,500 KES the right price?",
        "I need 4 bags of DAP",
        "county 032",
    ],
)
def test_ordinary_numbers_are_left_alone(harmless: str) -> None:
    """A false positive is not free: it corrupts the question being asked."""
    clean, found = privacy.scrub(harmless)
    assert clean == harmless
    assert found == []


def test_multiple_identifiers_in_one_message() -> None:
    clean, found = privacy.scrub("ID 12345678, phone 0712345678, mail me a@b.co")
    assert set(found) == {"national_id", "phone", "email"}
    for leak in ("12345678", "0712345678", "a@b.co"):
        assert leak not in clean


# --- pseudonyms ------------------------------------------------------------


def test_pseudonym_is_stable_per_user() -> None:
    assert privacy.pseudonym("user-1") == privacy.pseudonym("user-1")


def test_pseudonym_differs_between_users() -> None:
    assert privacy.pseudonym("user-1") != privacy.pseudonym("user-2")


def test_pseudonym_does_not_contain_the_user_id() -> None:
    user_id = "3f9c1b7e-0000-4000-8000-000000000001"
    assert user_id not in privacy.pseudonym(user_id)
    assert "3f9c1b7e" not in privacy.pseudonym(user_id)


def test_signed_out_visitor_has_no_pseudonym() -> None:
    assert privacy.pseudonym(None) == "Visitor"


# --- capability tiers ------------------------------------------------------


def test_visitor_gets_only_public_policy_tools() -> None:
    scope = scopes.resolve(user_id=None, roles=None, permissions=None, all_tools=ALL_TOOLS)
    assert scope.audience is Audience.VISITOR
    assert scope.is_signed_in is False
    assert sorted(t["name"] for t in scope.tools) == ["get_document_guidance", "search_policy"]


@pytest.mark.parametrize("withheld", ["get_triage_verdict", "get_market_signals"])
def test_visitor_cannot_reach_anything_personal(withheld: str) -> None:
    scope = scopes.resolve(user_id=None, roles=None, permissions=None, all_tools=ALL_TOOLS)
    assert scope.allows(withheld) is False


def test_visitor_prompt_points_at_the_free_check_and_refuses_verdicts() -> None:
    scope = scopes.resolve(user_id=None, roles=None, permissions=None, all_tools=ALL_TOOLS)
    guidance = scope.guidance()
    assert "NOT signed in" in guidance
    assert "no account" in guidance
    assert "Do not give a depot verdict" in guidance


def test_farmer_gains_the_verdict_and_market_tools() -> None:
    scope = scopes.resolve(
        user_id="u1",
        roles={"farmer"},
        permissions={"triage.run", "market.read", "assistant.chat"},
        all_tools=ALL_TOOLS,
    )
    assert scope.audience is Audience.FARMER
    assert scope.allows("get_triage_verdict")
    assert scope.allows("get_market_signals")


def test_a_permission_a_role_lacks_is_still_withheld() -> None:
    """Roles pick the wording; permissions decide access. Permissions win."""
    scope = scopes.resolve(
        user_id="u1", roles={"farmer"}, permissions={"assistant.chat"}, all_tools=ALL_TOOLS
    )
    assert scope.audience is Audience.FARMER
    assert scope.allows("get_triage_verdict") is False
    assert scope.allows("get_market_signals") is False


@pytest.mark.parametrize(
    ("roles", "expected"),
    [
        ({"farmer"}, Audience.FARMER),
        ({"retailer"}, Audience.BUSINESS),
        ({"wholesaler"}, Audience.BUSINESS),
        ({"supplier_association"}, Audience.ASSOCIATION),
        ({"policy_publisher"}, Audience.STAFF),
        ({"admin"}, Audience.STAFF),
        # Held together, the narrower register wins.
        ({"farmer", "admin"}, Audience.STAFF),
        ({"farmer", "supplier_association"}, Audience.ASSOCIATION),
    ],
)
def test_audience_is_derived_from_roles(roles: set[str], expected: Audience) -> None:
    assert scopes.audience_for(roles) is expected


def test_every_tier_names_the_pseudonym_and_never_asks_for_identifiers() -> None:
    for audience in Audience:
        roles = {} if audience is Audience.VISITOR else {_role_for(audience)}
        scope = scopes.resolve(
            user_id=None if audience is Audience.VISITOR else "u1",
            roles=roles or None,
            permissions={"triage.run", "market.read"},
            all_tools=ALL_TOOLS,
        )
        guidance = scope.guidance()
        assert "{pseudonym}" not in guidance, f"{audience} left the placeholder unfilled"
        assert "must not ask" in guidance or "must never ask" in guidance or "not need to give" in guidance


def test_an_unmapped_tool_is_withheld_rather_than_published() -> None:
    """Adding a tool without deciding who may use it must fail closed."""
    scope = scopes.resolve(
        user_id="u1",
        roles={"farmer"},
        permissions={"triage.run", "market.read"},
        all_tools=[*ALL_TOOLS, {"name": "delete_everything"}],
    )
    assert scope.allows("delete_everything") is False


def _role_for(audience: Audience) -> str:
    return {
        Audience.FARMER: "farmer",
        Audience.BUSINESS: "retailer",
        Audience.ASSOCIATION: "supplier_association",
        Audience.STAFF: "admin",
    }[audience]
