"""The `applies_when` predicate DSL.

Closed vocabulary, closed operator set, no expressions, no `eval`. A predicate
naming an unknown field or operator is a pack validation error at load time, not
a runtime shrug: a pack that cannot be understood must never serve a verdict.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from .types import PackValidationError

# The only field names a predicate may reference. Adding one here is a
# deliberate widening of the contract between policy data and the engine.
FIELDS: frozenset[str] = frozenset(
    {
        "acreage_acres",
        "depot_code",
        "land_tenure",
        "travel_date",
        "collecting_in_person",
        "registration_county_code",
        "depot_county_code",
        "travel_weekday",
        "depot_open_on_travel_date",
    }
)

COMBINATORS: frozenset[str] = frozenset({"all", "any", "not"})
FIELD_OPS: frozenset[str] = frozenset(
    {"eq", "ne", "in", "not_in", "gt", "gte", "lt", "lte", "is_known", "eq_field", "ne_field"}
)
DOCUMENT_OPS: frozenset[str] = frozenset({"has_document", "missing_document"})


def _as_decimal(value: Any) -> Any:
    """Compare numbers as Decimals so 2 and 2.0 and "2.00" agree."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return Decimal(str(value))
    return value


def validate(predicate: Any, *, where: str) -> None:
    """Raise PackValidationError unless the whole tree is understood."""
    if predicate is None:
        return
    if not isinstance(predicate, dict):
        raise PackValidationError(f"{where}: predicate must be an object, got {type(predicate).__name__}")

    keys = set(predicate)

    combinator = keys & COMBINATORS
    if combinator:
        if len(keys) != 1:
            raise PackValidationError(
                f"{where}: {sorted(combinator)[0]} must be the only key, saw {sorted(keys)}"
            )
        op = next(iter(combinator))
        branch = predicate[op]
        if op == "not":
            validate(branch, where=f"{where}.not")
            return
        if not isinstance(branch, list) or not branch:
            raise PackValidationError(f"{where}.{op}: expected a non-empty list")
        for i, sub in enumerate(branch):
            validate(sub, where=f"{where}.{op}[{i}]")
        return

    doc_op = keys & DOCUMENT_OPS
    if doc_op:
        if len(keys) != 1:
            raise PackValidationError(f"{where}: document operator must be the only key, saw {sorted(keys)}")
        op = next(iter(doc_op))
        if not isinstance(predicate[op], str):
            raise PackValidationError(f"{where}.{op}: expected a document code string")
        return

    if "field" not in keys:
        raise PackValidationError(
            f"{where}: predicate needs 'field', a combinator {sorted(COMBINATORS)}, "
            f"or a document operator {sorted(DOCUMENT_OPS)}; saw {sorted(keys)}"
        )

    name = predicate["field"]
    if name not in FIELDS:
        raise PackValidationError(f"{where}.field: unknown input field {name!r}; known: {sorted(FIELDS)}")

    ops = keys - {"field"}
    if not ops:
        raise PackValidationError(f"{where}: field {name!r} has no operator")
    unknown = ops - FIELD_OPS
    if unknown:
        raise PackValidationError(
            f"{where}: unknown operator(s) {sorted(unknown)}; known: {sorted(FIELD_OPS)}"
        )

    for op in ops:
        value = predicate[op]
        if op in ("in", "not_in") and not isinstance(value, list):
            raise PackValidationError(f"{where}.{op}: expected a list")
        if op == "is_known" and not isinstance(value, bool):
            raise PackValidationError(f"{where}.is_known: expected a boolean")
        if op in ("eq_field", "ne_field") and value not in FIELDS:
            raise PackValidationError(f"{where}.{op}: unknown input field {value!r}")


def matches(predicate: Any, context: dict[str, Any], held_documents: frozenset[str]) -> bool:
    """Evaluate a validated predicate. `None` means "always applies"."""
    if predicate is None:
        return True

    keys = set(predicate)

    if "all" in keys:
        return all(matches(sub, context, held_documents) for sub in predicate["all"])
    if "any" in keys:
        return any(matches(sub, context, held_documents) for sub in predicate["any"])
    if "not" in keys:
        return not matches(predicate["not"], context, held_documents)
    if "has_document" in keys:
        return predicate["has_document"] in held_documents
    if "missing_document" in keys:
        return predicate["missing_document"] not in held_documents

    actual = context.get(predicate["field"])

    for op, expected in predicate.items():
        if op == "field":
            continue
        if not _compare(op, actual, expected, context):
            return False
    return True


def _compare(op: str, actual: Any, expected: Any, context: dict[str, Any]) -> bool:
    if op == "is_known":
        return (actual is not None) is expected

    if op == "eq_field":
        return actual == context.get(expected)
    if op == "ne_field":
        return actual != context.get(expected)

    # An unknown value satisfies no value comparison. This is the fail-closed
    # half of the DSL: a rule that needs a fact we do not have does not fire,
    # and the pack pairs it with an is_known advisory (see ELIG_DEPOT_COUNTY_*).
    if actual is None:
        return False

    if op == "eq":
        return _as_decimal(actual) == _as_decimal(expected)
    if op == "ne":
        return _as_decimal(actual) != _as_decimal(expected)
    if op == "in":
        return actual in expected
    if op == "not_in":
        return actual not in expected

    left, right = _as_decimal(actual), _as_decimal(expected)
    if op == "gt":
        return bool(left > right)
    if op == "gte":
        return bool(left >= right)
    if op == "lt":
        return bool(left < right)
    if op == "lte":
        return bool(left <= right)

    raise PackValidationError(f"operator {op!r} passed validation but has no implementation")
