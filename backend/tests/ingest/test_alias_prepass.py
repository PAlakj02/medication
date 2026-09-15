from pathlib import Path

from app.ingest.alias_prepass import AliasPrepassLoader


def _loader(curated_csv_path: Path) -> AliasPrepassLoader:
    # rrf_path is unused by _read_curated_rows; any path is fine here.
    return AliasPrepassLoader(rrf_path=Path("/dev/null"), curated_csv_path=curated_csv_path)


def test_read_curated_rows_skips_comment_lines(tmp_path):
    csv_path = tmp_path / "aliases.csv"
    csv_path.write_text(
        "# a comment line\n"
        "# another comment\n"
        "alias,canonical_name\n"
        "Acetylsalicylic acid,Aspirin\n"
    )
    rows = _loader(csv_path)._read_curated_rows()
    assert rows == [("Acetylsalicylic acid", "Aspirin")]


def test_read_curated_rows_returns_empty_list_for_header_only_file(tmp_path):
    csv_path = tmp_path / "aliases.csv"
    csv_path.write_text("# a comment\nalias,canonical_name\n")
    rows = _loader(csv_path)._read_curated_rows()
    assert rows == []


def test_read_curated_rows_parses_the_shipped_data_aliases_file():
    # The real, populated data/aliases.csv — a smoke test that it's still
    # well-formed and non-empty, without pinning exact row count/content
    # (that file is expected to grow over time).
    loader = AliasPrepassLoader(
        rrf_path=Path("/dev/null"),
        curated_csv_path=Path(__file__).resolve().parents[2] / "data" / "aliases.csv",
    )
    rows = loader._read_curated_rows()
    assert len(rows) > 0
    assert all(alias and canonical for alias, canonical in rows)


def test_read_curated_rows_returns_empty_list_when_file_missing(tmp_path):
    loader = _loader(tmp_path / "does_not_exist.csv")
    assert loader._read_curated_rows() == []


def test_read_curated_rows_skips_rows_with_blank_fields(tmp_path):
    csv_path = tmp_path / "aliases.csv"
    csv_path.write_text(
        "alias,canonical_name\n"
        "Good Alias,Good Canonical\n"
        ",Missing Alias\n"
        "Missing Canonical,\n"
    )
    rows = _loader(csv_path)._read_curated_rows()
    assert rows == [("Good Alias", "Good Canonical")]


def test_read_curated_rows_strips_whitespace(tmp_path):
    csv_path = tmp_path / "aliases.csv"
    csv_path.write_text("alias,canonical_name\n  Padded Alias  ,  Padded Canonical  \n")
    rows = _loader(csv_path)._read_curated_rows()
    assert rows == [("Padded Alias", "Padded Canonical")]


def test_read_inn_usan_rows_parses_inn_name_and_us_name(tmp_path):
    csv_path = tmp_path / "inn_usan_map.csv"
    csv_path.write_text(
        "inn_name,us_name,rxcui,source,notes\n"
        "paracetamol,acetaminophen,161,domain_knowledge,best known example\n"
    )
    loader = AliasPrepassLoader(
        rrf_path=Path("/dev/null"), curated_csv_path=Path("/dev/null"), inn_usan_csv_path=csv_path
    )
    assert loader._read_inn_usan_rows() == [("paracetamol", "acetaminophen")]


def test_read_inn_usan_rows_ignores_blank_rxcui():
    # The shipped file leaves rxcui blank for at least one row
    # (thiopentone/thiopental) — that must not break parsing.
    real_path = Path(__file__).resolve().parents[2] / "data" / "inn_usan_map.csv"
    loader = AliasPrepassLoader(
        rrf_path=Path("/dev/null"), curated_csv_path=Path("/dev/null"), inn_usan_csv_path=real_path
    )
    rows = loader._read_inn_usan_rows()
    assert ("thiopentone", "thiopental") in rows
    assert len(rows) >= 20


def test_read_inn_usan_rows_returns_empty_list_when_file_missing(tmp_path):
    loader = AliasPrepassLoader(
        rrf_path=Path("/dev/null"),
        curated_csv_path=Path("/dev/null"),
        inn_usan_csv_path=tmp_path / "does_not_exist.csv",
    )
    assert loader._read_inn_usan_rows() == []


def test_alias_prepass_defaults_inn_usan_path_next_to_curated_path(tmp_path):
    curated_path = tmp_path / "aliases.csv"
    loader = AliasPrepassLoader(rrf_path=Path("/dev/null"), curated_csv_path=curated_path)
    assert loader.inn_usan_csv_path == tmp_path / "inn_usan_map.csv"
