from app.ingest.rxnorm_parsing import (
    ConsoRow,
    IngredientStrength,
    ParsedClinicalDrug,
    is_branded_drug_concept,
    is_ingredient_concept,
    parse_clinical_drug_string,
    parse_rrf_line,
)

# Real sample lines pulled from RxNorm_full_prescribe_09082026/rrf/RXNCONSO.RRF.
IN_LINE = "44|ENG||||||12251526|12251526|44||RXNORM|IN|44|mesna||N|4096|"
PIN_LINE = "1943|ENG||||||123|123|1943||RXNORM|PIN|1943|some ingredient||N|4096|"
SU_LINE = "44|ENG||||||2798745|2798745|44||MTHSPL|SU|NR7O1405Q9|mesna||N|4096|"
SBD_LINE = (
    "92758|ENG||||||12363086|12363086|92758||RXNORM|SBD|92758|"
    "griseofulvin 165 MG Oral Tablet [Fulvicin P/G]||N|4096|"
)
SUPPRESSED_IN_LINE = "50|ENG||||||1|1|50||RXNORM|IN|50|suppressed ingredient||Y|4096|"


def test_parse_rrf_line_extracts_expected_fields():
    row = parse_rrf_line(IN_LINE)
    assert row == ConsoRow(rxcui="44", lat="ENG", sab="RXNORM", tty="IN", suppress="N", str_="mesna")


def test_parse_rrf_line_returns_none_for_short_line():
    assert parse_rrf_line("too|few|fields") is None


def test_is_ingredient_concept_accepts_in_pin_min():
    assert is_ingredient_concept(parse_rrf_line(IN_LINE))
    assert is_ingredient_concept(parse_rrf_line(PIN_LINE))


def test_is_ingredient_concept_rejects_non_rxnorm_source():
    # SU from MTHSPL, not RXNORM -- should not be treated as canonical.
    assert not is_ingredient_concept(parse_rrf_line(SU_LINE))


def test_is_ingredient_concept_rejects_suppressed_rows():
    assert not is_ingredient_concept(parse_rrf_line(SUPPRESSED_IN_LINE))


def test_is_branded_drug_concept_accepts_sbd():
    assert is_branded_drug_concept(parse_rrf_line(SBD_LINE))


def test_is_branded_drug_concept_rejects_ingredient_row():
    assert not is_branded_drug_concept(parse_rrf_line(IN_LINE))


def test_parse_clinical_drug_string_single_ingredient_with_slash_unit():
    result = parse_clinical_drug_string("fluorouracil 10 MG/ML Topical Cream [Fluoroplex]")
    assert result == ParsedClinicalDrug(
        brand="Fluoroplex",
        ingredients=[IngredientStrength(name="fluorouracil", strength=10.0, unit="MG/ML")],
    )


def test_parse_clinical_drug_string_combination_product():
    result = parse_clinical_drug_string(
        "hydrochlorothiazide 50 MG / triamterene 75 MG Oral Tablet [Maxzide]"
    )
    assert result.brand == "Maxzide"
    assert result.ingredients == [
        IngredientStrength(name="hydrochlorothiazide", strength=50.0, unit="MG"),
        IngredientStrength(name="triamterene", strength=75.0, unit="MG"),
    ]


def test_parse_clinical_drug_string_decimal_strength():
    result = parse_clinical_drug_string("desoximetasone 2.5 MG/ML Topical Cream [Topicort]")
    assert result.ingredients == [
        IngredientStrength(name="desoximetasone", strength=2.5, unit="MG/ML")
    ]


def test_parse_clinical_drug_string_returns_none_without_brand_bracket():
    # SCD strings (generic, no brand) are out of scope for product creation.
    assert parse_clinical_drug_string("hydrogen peroxide 300 MG/ML Topical Solution") is None


def test_parse_clinical_drug_string_percent_unit():
    result = parse_clinical_drug_string("benzocaine 20 % Topical Gel [Orajel]")
    assert result.ingredients == [IngredientStrength(name="benzocaine", strength=20.0, unit="%")]


def test_parse_clinical_drug_string_ingredient_name_starting_with_digit():
    result = parse_clinical_drug_string("5-hydroxytryptophan 50 MG Oral Capsule [SomeBrand]")
    assert result.ingredients == [
        IngredientStrength(name="5-hydroxytryptophan", strength=50.0, unit="MG")
    ]


def test_parse_clinical_drug_string_returns_none_when_no_segment_parses():
    assert parse_clinical_drug_string("Topical Cream [SomeBrand]") is None
