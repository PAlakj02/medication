from app.ingest.indian_medicine_parsing import CompositionIngredient, parse_composition_field


def test_parses_simple_name_and_strength():
    result = parse_composition_field("Ofloxacin (200mg)")
    assert result == CompositionIngredient(name="Ofloxacin", strength=200.0, unit="mg")


def test_returns_none_for_blank_field():
    assert parse_composition_field("") is None
    assert parse_composition_field("   ") is None


def test_strips_leading_and_trailing_whitespace():
    result = parse_composition_field(" Cefixime (50mg) ")
    assert result == CompositionIngredient(name="Cefixime", strength=50.0, unit="mg")


def test_takes_last_parenthetical_as_strength_and_strips_qualifier():
    result = parse_composition_field("Dehydroepiandrosterone (Micronized) (75mg)")
    assert result == CompositionIngredient(
        name="Dehydroepiandrosterone", strength=75.0, unit="mg"
    )


def test_compound_unit_with_space():
    result = parse_composition_field("Clobetasol (0.05% w/w)")
    assert result == CompositionIngredient(name="Clobetasol", strength=0.05, unit="% w/w")


def test_non_mass_strength_degrades_gracefully():
    result = parse_composition_field("Lactobacillus (60Million spores)")
    assert result.name == "Lactobacillus"
    assert result.strength == 60.0
    assert result.unit == "Million spores"


def test_per_volume_unit():
    result = parse_composition_field("Ambroxol (30mg/5ml)")
    assert result == CompositionIngredient(name="Ambroxol", strength=30.0, unit="mg/5ml")


def test_no_parenthetical_returns_name_only():
    result = parse_composition_field("Benadryl")
    assert result == CompositionIngredient(name="Benadryl", strength=None, unit=None)


def test_empty_parens_returns_name_without_strength():
    result = parse_composition_field("SomeIngredient ()")
    assert result == CompositionIngredient(name="SomeIngredient", strength=None, unit=None)


def test_unparseable_amount_falls_back_to_raw_unit_string():
    result = parse_composition_field("SomeIngredient (as required)")
    assert result == CompositionIngredient(name="SomeIngredient", strength=None, unit="as required")
