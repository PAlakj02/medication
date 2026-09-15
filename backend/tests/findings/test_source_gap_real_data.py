"""Integration tests against the real loaded DB (requires scripts/run_ingest.py
to have run first — deliberately NOT a synthetic-fixture test).

History: this file used to document that canonical "aspirin" had zero
DDInter mentions (DDInter's raw data called it "Acetylsalicylic acid"
instead), making warfarin+aspirin — one of medicine's best-known
interactions — wrongly read as NOT_CHECKED_SOURCE_GAP. That was fixed on
2026-09-09 by adding acetylsalicylic-acid/aspirin to
data/inn_usan_map.csv and rebuilding from empty tables. The first two
tests below now guard against that fix regressing. The gap-state test
uses a fresh real example — domperidone, a real internationally common
drug that's genuinely absent from RxNorm (not FDA-approved in the US, so
there's no RxCUI to alias to) — since aspirin no longer demonstrates the
gap state.
"""

import pytest
from sqlalchemy import func, select

from app.findings.engine import check_pair
from app.findings.models import IngredientRef, PairState
from app.findings.repository import load_covered_ingredient_ids, load_interaction_rules
from app.models.ingredient import Ingredient


def _find_ingredient(dev_db_session, name: str) -> IngredientRef | None:
    row = dev_db_session.execute(
        select(Ingredient).where(func.lower(Ingredient.name) == name.lower())
    ).scalar_one_or_none()
    if row is None:
        return None
    return IngredientRef(id=row.id, name=row.name)


def test_canonical_aspirin_now_has_ddinter_coverage_regression_guard(dev_db_session):
    """Guards against the 2026-09-09 fix (acetylsalicylic-acid/aspirin in
    data/inn_usan_map.csv) regressing — canonical "aspirin" must stay
    covered by DDInter, not silently revert to the pre-fix gap."""
    aspirin = _find_ingredient(dev_db_session, "aspirin")
    if aspirin is None:
        pytest.skip("Bulk data not loaded — run scripts/run_ingest.py first")

    covered = load_covered_ingredient_ids(dev_db_session, "DDInter")
    assert aspirin.id in covered, (
        "Canonical 'aspirin' has no DDInter mentions again — the "
        "acetylsalicylic-acid/aspirin inn_usan alias fix may have regressed "
        "(check data/inn_usan_map.csv and that the pipeline was rebuilt from "
        "empty tables, not just incrementally re-run)."
    )


def test_warfarin_aspirin_is_found_not_a_source_gap_regression_guard(dev_db_session):
    aspirin = _find_ingredient(dev_db_session, "aspirin")
    warfarin = _find_ingredient(dev_db_session, "warfarin")
    if aspirin is None or warfarin is None:
        pytest.skip("Bulk data not loaded — run scripts/run_ingest.py first")

    covered = load_covered_ingredient_ids(dev_db_session, "DDInter")
    rules = load_interaction_rules(dev_db_session, [aspirin.id, warfarin.id])
    result = check_pair(aspirin, warfarin, rules, covered)

    assert result.state == PairState.FOUND, (
        f"warfarin+aspirin regressed to {result.state.value!r} — expected FOUND "
        "(a real, correctly-attributed high-severity interaction) since the "
        "2026-09-09 alias fix."
    )
    assert result.finding.severity is not None and result.finding.severity.value == "high"


def test_domperidone_ibuprofen_returns_not_checked_source_gap_not_checked_none_found(dev_db_session):
    """The current real example of NOT_CHECKED_SOURCE_GAP: domperidone is
    a real, internationally common anti-nausea drug with no US RxCUI at
    all (not FDA-approved) — DDInter has zero data on it, so there's
    nothing to alias to; unlike aspirin, this gap isn't a naming problem."""
    domperidone = _find_ingredient(dev_db_session, "domperidone")
    ibuprofen = _find_ingredient(dev_db_session, "ibuprofen")
    if domperidone is None or ibuprofen is None:
        pytest.skip("Bulk data not loaded — run scripts/run_ingest.py first")

    covered = load_covered_ingredient_ids(dev_db_session, "DDInter")
    rules = load_interaction_rules(dev_db_session, [domperidone.id, ibuprofen.id])
    result = check_pair(domperidone, ibuprofen, rules, covered)

    assert result.state == PairState.NOT_CHECKED_SOURCE_GAP
    assert result.state != PairState.CHECKED_NONE_FOUND
    assert result.finding is None
