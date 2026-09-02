"""The deterministic triage engine.

Stdlib only, by contract. No FastAPI, no database driver, no HTTP client, no
model call, and no wall clock — the travel date and the pack are arguments. This
is what makes a verdict a pure function of (pack version, inputs) and therefore
replayable years later, which is the product's core promise.

`tests/engine/test_purity.py` enforces all of that by walking this package's AST.
"""

from .evaluate import evaluate
from .pack import RulePack, load
from .types import (
    Allocation,
    Costing,
    Finding,
    LandTenure,
    PackValidationError,
    ReasonKind,
    Severity,
    TriageInput,
    TriageResult,
    Verdict,
)

__all__ = [
    "Allocation",
    "Costing",
    "Finding",
    "LandTenure",
    "PackValidationError",
    "ReasonKind",
    "RulePack",
    "Severity",
    "TriageInput",
    "TriageResult",
    "Verdict",
    "evaluate",
    "load",
]
