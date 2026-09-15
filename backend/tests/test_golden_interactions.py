"""Golden interaction test set — a REAL integration test against the
loaded DB (requires scripts/run_ingest.py to have been run first). This is
deliberately not a hermetic unit test: it exists to catch regressions in
the actual data pipeline (ingest, alias resolution, findings engine)
working together, which no amount of synthetic-fixture testing can verify.

Every row in data/golden_pairs.csv becomes its own pytest case via
parametrize, so a failure names the exact pair, not "somewhere in a loop".
See that file's header for the exact format.

Fails loudly, never skips, when a golden pair references a drug name that
doesn't resolve to any ingredient in the DB — see test_golden_pair's
assertions. A missing/unresolvable name is either a typo in the golden set
or a genuine regression in ingest/alias resolution; both need to be seen,
not silently passed over.
"""

import csv
from pathlib import Path

import pytest

from app.findings.engine import check_pair
from app.findings.models import PairState
from app.findings.repository import load_covered_ingredient_ids, load_interaction_rules
from app.ingest.ingredient_resolver import IngredientResolver

GOLDEN_CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "golden_pairs.csv"

_STATE_BY_LABEL = {
    "found": PairState.FOUND,
    "checked_none_found": PairState.CHECKED_NONE_FOUND,
    "not_checked_source_gap": PairState.NOT_CHECKED_SOURCE_GAP,
}
_SEVERITY_LABELS = {"high", "moderate", "low", "ungraded"}

INTERACTION_SOURCE_NAME = "DDInter"


def _read_golden_rows() -> list[dict]:
    if not GOLDEN_CSV_PATH.exists():
        return []
    with GOLDEN_CSV_PATH.open(newline="", encoding="utf-8") as f:
        lines = [line for line in f if not line.lstrip().startswith("#")]
    if not lines:
        return []
    return [row for row in csv.DictReader(lines) if row.get("drug_a")]


_GOLDEN_ROWS = _read_golden_rows()


def _case_id(row: dict) -> str:
    return f"{row['drug_a']}+{row['drug_b']}"


def test_golden_pairs_file_is_populated():
    """A meta-check that fails loudly instead of this whole file silently
    collecting zero test cases if data/golden_pairs.csv is ever emptied."""
    assert _GOLDEN_ROWS, (
        f"{GOLDEN_CSV_PATH} has no data rows — populate it (see its header comment "
        "for the format) before this golden set can verify anything."
    )


@pytest.mark.parametrize(
    "row", _GOLDEN_ROWS, ids=[_case_id(r) for r in _GOLDEN_ROWS] if _GOLDEN_ROWS else []
)
def test_golden_pair(row: dict, dev_db_session):
    case_id = _case_id(row)
    expected_state_label = row["expected_state"].strip()
    expected_severity_label = (row.get("expected_severity") or "").strip() or None
    note = row.get("note", "")

    assert expected_state_label in _STATE_BY_LABEL, (
        f"{case_id}: unrecognized expected_state {expected_state_label!r} in "
        f"{GOLDEN_CSV_PATH} — must be one of {sorted(_STATE_BY_LABEL)}"
    )
    if expected_severity_label is not None:
        assert expected_severity_label in _SEVERITY_LABELS, (
            f"{case_id}: unrecognized expected_severity {expected_severity_label!r} — "
            f"must be one of {sorted(_SEVERITY_LABELS)} or blank"
        )
    expected_state = _STATE_BY_LABEL[expected_state_label]

    resolver = IngredientResolver(dev_db_session)
    resolver.warm()

    ingredient_a, _tier_a = resolver.resolve(row["drug_a"])
    ingredient_b, _tier_b = resolver.resolve(row["drug_b"])
    assert ingredient_a is not None, (
        f"{case_id}: {row['drug_a']!r} does not resolve to any ingredient in the DB. "
        f"Either fix the name in data/golden_pairs.csv, or this is a real regression in "
        f"ingest/alias resolution — don't skip this, investigate it. Note: {note}"
    )
    assert ingredient_b is not None, (
        f"{case_id}: {row['drug_b']!r} does not resolve to any ingredient in the DB. "
        f"Either fix the name in data/golden_pairs.csv, or this is a real regression in "
        f"ingest/alias resolution — don't skip this, investigate it. Note: {note}"
    )

    covered = load_covered_ingredient_ids(dev_db_session, INTERACTION_SOURCE_NAME)
    rules = load_interaction_rules(dev_db_session, [ingredient_a.id, ingredient_b.id])
    result = check_pair(ingredient_a, ingredient_b, rules, covered)

    assert result.state == expected_state, (
        f"{case_id}: expected state {expected_state.value!r}, got {result.state.value!r}. "
        f"Note: {note}"
    )

    if expected_severity_label is None:
        return

    assert result.finding is not None, (
        f"{case_id}: expected_severity={expected_severity_label!r} but state={result.state.value!r} "
        f"has no finding to have a severity. Note: {note}"
    )
    actual_severity_label = (
        "ungraded" if result.finding.severity_ungraded else result.finding.severity.value
    )
    assert actual_severity_label == expected_severity_label, (
        f"{case_id}: expected severity {expected_severity_label!r}, got "
        f"{actual_severity_label!r}. Note: {note}"
    )
