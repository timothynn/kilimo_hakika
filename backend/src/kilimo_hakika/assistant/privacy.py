"""Keeping identity out of the model.

The model provider is a third party. It needs to help a farmer with depot rules,
and helping with depot rules never requires knowing who the farmer is. So the
identity never leaves this process:

  - The model is given a **pseudonym** (`Farmer-4F2A`), derived by keyed hash
    from the internal user id. Stable within an account so the assistant can
    refer back across turns, and useless outside this deployment.
  - Tool results are built from policy inputs only - acreage, county code, land
    tenure, documents held. No name, no phone, no ID, no user id.
  - Anything the *farmer types* is scrubbed before it is sent. This is the leak
    that guardrails in a prompt cannot cover: a farmer who pastes their ID
    number into the chat has already handed it over unless the code removes it.

The prompt also tells the model not to ask for these. That instruction is a
courtesy to the farmer, not the control. The control is this module.
"""

from __future__ import annotations

import hashlib
import hmac
import re

from ..settings import get_settings

# Order matters: the phone patterns are tried before the bare-digit rule so a
# +254 number is reported as a phone rather than as an unlabelled number.
_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b"), "[email removed]"),
    # Kenyan mobile numbers: +254 7xx / 254 7xx / 07xx / 01xx, spaces or dashes
    # allowed inside. Written out rather than one clever pattern so each form is
    # readable and testable.
    ("phone", re.compile(r"\+?254[\s-]?[17]\d{2}[\s-]?\d{3}[\s-]?\d{3}\b"), "[phone number removed]"),
    ("phone", re.compile(r"\b0[17]\d{2}[\s-]?\d{3}[\s-]?\d{3}\b"), "[phone number removed]"),
    # Kenyan national ID numbers are 7-8 digits. Nothing else a farmer types in
    # this app is a bare 7-8 digit run: acreage is small, bag counts are small,
    # and prices are written with a currency word or a comma. Anchored on word
    # boundaries so it cannot bite into a longer reference number.
    ("national_id", re.compile(r"\b\d{7,8}\b"), "[ID number removed]"),
)


def pseudonym(user_id: str | None) -> str:
    """A stable, non-reversible handle for one account.

    Keyed so that a leaked pseudonym cannot be walked back to the user id by
    hashing candidates. `None` means nobody is signed in.
    """
    if not user_id:
        return "Visitor"
    digest = hmac.new(
        get_settings().jwt_secret.encode("utf-8"),
        f"assistant-pseudonym:{user_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    # Deliberately neutral: the same helper serves farmers, retailers, supplier
    # associations and staff, and a handle that asserted a role would mislabel
    # three of the four.
    return f"Account-{digest[:4].upper()}"


def scrub(text: str) -> tuple[str, list[str]]:
    """Remove identifiers from text bound for the model.

    Returns the cleaned text and the kinds that were found, so the caller can
    audit that a scrub happened without logging the values themselves.
    """
    found: list[str] = []
    cleaned = text
    for kind, pattern, replacement in _PATTERNS:
        cleaned, count = pattern.subn(replacement, cleaned)
        if count and kind not in found:
            found.append(kind)
    return cleaned, found
