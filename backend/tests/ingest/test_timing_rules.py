from pathlib import Path

from app.ingest.timing_rules import TimingRuleLoader, read_timing_rule_rows
from app.models.ingredient import Ingredient
from app.models.timing_rule import TimingRule


def test_read_timing_rule_rows_parses_the_shipped_data_file():
    # Smoke test on the real, curated data/timing_rules.csv.
    rows = read_timing_rule_rows(Path(__file__).resolve().parents[2] / "data" / "timing_rules.csv")
    assert len(rows) > 0
    assert all(r.ingredient_name and r.rule_type and r.note and r.source_url for r in rows)


def test_read_timing_rule_rows_parses_blank_offset_as_none(tmp_path):
    csv_path = tmp_path / "timing_rules.csv"
    csv_path.write_text(
        "ingredient_name,rule_type,offset_minutes,note,source_name,source_url\n"
        "Metronidazole,avoid_alcohol,,Avoid alcohol.,FDA,https://example.com\n"
    )
    rows = read_timing_rule_rows(csv_path)
    assert rows[0].offset_minutes is None


def test_load_resolves_ingredient_and_creates_timing_rule(db_session):
    db_session.add(Ingredient(name="Levothyroxine"))
    db_session.flush()

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        csv_path = Path(tmp) / "timing_rules.csv"
        csv_path.write_text(
            "ingredient_name,rule_type,offset_minutes,note,source_name,source_url\n"
            "Levothyroxine,take_on_empty_stomach,60,Take before breakfast.,FDA label,https://example.com/label\n"
        )
        result = TimingRuleLoader(csv_path=csv_path).load(db_session)

    assert result.timing_rules_created == 1
    assert result.errors == []

    rule = db_session.query(TimingRule).one()
    assert rule.rule_type.value == "take_on_empty_stomach"
    assert rule.offset_minutes == 60
    assert rule.source.name == "FDA label"


def test_load_logs_error_and_skips_unresolvable_ingredient(db_session):
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        csv_path = Path(tmp) / "timing_rules.csv"
        csv_path.write_text(
            "ingredient_name,rule_type,offset_minutes,note,source_name,source_url\n"
            "SomeCompletelyUnknownDrugXYZ,avoid_alcohol,,note,FDA,https://example.com\n"
        )
        result = TimingRuleLoader(csv_path=csv_path).load(db_session)

    assert result.timing_rules_created == 0
    assert len(result.errors) == 1
    assert "SomeCompletelyUnknownDrugXYZ" in result.errors[0]


def test_load_is_idempotent_on_rerun(db_session):
    db_session.add(Ingredient(name="Levothyroxine"))
    db_session.flush()

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        csv_path = Path(tmp) / "timing_rules.csv"
        csv_path.write_text(
            "ingredient_name,rule_type,offset_minutes,note,source_name,source_url\n"
            "Levothyroxine,take_on_empty_stomach,60,Take before breakfast.,FDA label,https://example.com/label\n"
        )
        loader = TimingRuleLoader(csv_path=csv_path)
        first = loader.load(db_session)
        second = loader.load(db_session)

    assert first.timing_rules_created == 1
    assert second.timing_rules_created == 0
    assert db_session.query(TimingRule).count() == 1
