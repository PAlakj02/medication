from app.parsing.prescription import parse_prescription_line


def test_full_line_with_all_fields():
    result = parse_prescription_line("Tab. Paracetamol 500mg BD x 5 days")
    assert result.drug_candidate == "Paracetamol"
    assert result.route_form == "tablet"
    assert result.dose.value == 500.0
    assert result.dose.unit == "mg"
    assert result.frequency.code == "BD"
    assert result.duration.value == 5.0
    assert result.duration.unit == "day"
    assert result.raw_text == "Tab. Paracetamol 500mg BD x 5 days"


def test_free_text_frequency_and_no_route_form():
    result = parse_prescription_line("Metformin 500mg twice daily")
    assert result.drug_candidate == "Metformin"
    assert result.route_form is None
    assert result.dose.value == 500.0
    assert result.frequency.code == "BD"
    assert result.duration is None


def test_bare_drug_name_with_no_dosage_info_at_all():
    result = parse_prescription_line("Aspirin")
    assert result.drug_candidate == "Aspirin"
    assert result.dose is None
    assert result.frequency is None
    assert result.duration is None
    assert result.route_form is None


def test_multi_word_drug_name_preserved():
    result = parse_prescription_line("Cap. Amoxicillin Clavulanate 625mg TDS")
    assert result.drug_candidate == "Amoxicillin Clavulanate"
    assert result.route_form == "capsule"


def test_syrup_with_ml_dose_and_duration_for_weeks():
    result = parse_prescription_line("Syp. Cough Mixture 10ml TDS for 1 week")
    assert result.drug_candidate == "Cough Mixture"
    assert result.route_form == "syrup"
    assert result.dose.unit == "ml"
    assert result.duration.unit == "week"


def test_stat_dose_no_recurring_frequency():
    result = parse_prescription_line("Inj. Adrenaline 1mg STAT")
    assert result.drug_candidate == "Adrenaline"
    assert result.frequency.code == "STAT"
    assert result.frequency.times_per_day is None


def test_as_needed_prn_style():
    result = parse_prescription_line("Paracetamol 500mg SOS")
    assert result.drug_candidate == "Paracetamol"
    assert result.frequency.code == "SOS"


def test_every_n_hours_frequency():
    result = parse_prescription_line("Paracetamol 500mg every 6 hours x 3 days")
    assert result.drug_candidate == "Paracetamol"
    assert result.frequency.code == "CUSTOM"
    assert result.frequency.times_per_day == 4.0
    assert result.duration.value == 3.0


def test_whitespace_only_line_yields_empty_drug_candidate():
    result = parse_prescription_line("   ")
    assert result.drug_candidate == ""


def test_raw_text_preserves_original_including_whitespace():
    result = parse_prescription_line("  Aspirin  ")
    assert result.raw_text == "  Aspirin  "
    assert result.drug_candidate == "Aspirin"
