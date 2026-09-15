from app.parsing.dosage import (
    DoseAmount,
    Duration,
    Frequency,
    extract_dose,
    extract_duration,
    extract_frequency,
    extract_route_form,
)

# --- extract_dose ---------------------------------------------------------


def test_extract_dose_mg():
    dose, remaining = extract_dose("Paracetamol 500mg BD")
    assert dose == DoseAmount(value=500.0, unit="mg", raw_text="500mg")
    assert remaining == "Paracetamol BD"


def test_extract_dose_decimal_value():
    dose, remaining = extract_dose("Digoxin 0.25mg OD")
    assert dose.value == 0.25
    assert dose.unit == "mg"


def test_extract_dose_with_space_before_unit():
    dose, _ = extract_dose("Ibuprofen 400 mg TDS")
    assert dose == DoseAmount(value=400.0, unit="mg", raw_text="400 mg")


def test_extract_dose_normalizes_tablet_synonyms():
    for text, expected_raw in [("2 tabs", "2 tabs"), ("2 tablet", "2 tablet"), ("2 tablets", "2 tablets")]:
        dose, _ = extract_dose(text)
        assert dose.unit == "tablet"
        assert dose.raw_text == expected_raw


def test_extract_dose_normalizes_capsule_synonyms():
    dose, _ = extract_dose("1 cap")
    assert dose.unit == "capsule"


def test_extract_dose_mcg_and_micro_symbol():
    dose, _ = extract_dose("Levothyroxine 50mcg OD")
    assert dose.unit == "mcg"
    dose2, _ = extract_dose("Levothyroxine 50μg OD")
    assert dose2.unit == "mcg"


def test_extract_dose_iu():
    dose, _ = extract_dose("Vitamin D 1000IU OD")
    assert dose.unit == "iu"


def test_extract_dose_ml():
    dose, _ = extract_dose("Cough syrup 10ml TDS")
    assert dose.unit == "ml"


def test_extract_dose_returns_none_when_no_dose_present():
    dose, remaining = extract_dose("Paracetamol BD")
    assert dose is None
    assert remaining == "Paracetamol BD"


def test_extract_dose_case_insensitive_unit():
    dose, _ = extract_dose("500MG")
    assert dose.unit == "mg"


# --- extract_frequency -----------------------------------------------------


def test_extract_frequency_od_abbreviation():
    freq, remaining = extract_frequency("Paracetamol 500mg OD")
    assert freq == Frequency(code="OD", times_per_day=1.0, raw_text="OD")
    assert remaining == "Paracetamol 500mg"


def test_extract_frequency_bd_abbreviation():
    freq, _ = extract_frequency("Metformin 500mg BD")
    assert freq.code == "BD"
    assert freq.times_per_day == 2.0


def test_extract_frequency_bid_variant():
    freq, _ = extract_frequency("Metformin 500mg BID")
    assert freq.code == "BD"
    assert freq.times_per_day == 2.0


def test_extract_frequency_tds_and_tid_variants():
    for text in ["Amoxicillin 250mg TDS", "Amoxicillin 250mg TID"]:
        freq, _ = extract_frequency(text)
        assert freq.code == "TDS"
        assert freq.times_per_day == 3.0


def test_extract_frequency_qds_and_qid_variants():
    for text in ["Drug 10mg QDS", "Drug 10mg QID"]:
        freq, _ = extract_frequency(text)
        assert freq.code == "QDS"
        assert freq.times_per_day == 4.0


def test_extract_frequency_hs_bedtime():
    freq, _ = extract_frequency("Zolpidem 10mg HS")
    assert freq.code == "HS"
    assert freq.times_per_day == 1.0


def test_extract_frequency_sos_and_prn():
    for text in ["Paracetamol 500mg SOS", "Paracetamol 500mg PRN"]:
        freq, _ = extract_frequency(text)
        assert freq.code == "SOS"
        assert freq.times_per_day is None


def test_extract_frequency_stat():
    freq, _ = extract_frequency("Adrenaline 1mg STAT")
    assert freq.code == "STAT"
    assert freq.times_per_day is None


def test_extract_frequency_qod_every_other_day():
    freq, _ = extract_frequency("Warfarin 2mg QOD")
    assert freq.code == "QOD"
    assert freq.times_per_day == 0.5


def test_extract_frequency_free_text_twice_daily():
    freq, remaining = extract_frequency("Metformin 500mg twice daily")
    assert freq.code == "BD"
    assert freq.times_per_day == 2.0
    assert remaining == "Metformin 500mg"


def test_extract_frequency_free_text_three_times_a_day():
    freq, _ = extract_frequency("Amoxicillin 250mg three times a day")
    assert freq.code == "TDS"


def test_extract_frequency_free_text_thrice_daily():
    freq, _ = extract_frequency("Amoxicillin 250mg thrice daily")
    assert freq.code == "TDS"


def test_extract_frequency_free_text_once_daily():
    freq, _ = extract_frequency("Atorvastatin 10mg once daily")
    assert freq.code == "OD"
    assert freq.times_per_day == 1.0


def test_extract_frequency_every_n_hours():
    freq, remaining = extract_frequency("Paracetamol 500mg every 6 hours")
    assert freq.code == "CUSTOM"
    assert freq.times_per_day == 4.0
    assert remaining == "Paracetamol 500mg"


def test_extract_frequency_every_n_hrs_abbreviation():
    freq, _ = extract_frequency("Paracetamol 500mg every 8 hrs")
    assert freq.code == "CUSTOM"
    assert freq.times_per_day == 3.0


def test_extract_frequency_does_not_false_match_hs_inside_hours():
    # "every 8 hours" must resolve via the every-N-hours pattern, not
    # accidentally trip the standalone "HS" (bedtime) abbreviation.
    freq, _ = extract_frequency("every 8 hours")
    assert freq.code == "CUSTOM"


def test_extract_frequency_returns_none_when_absent():
    freq, remaining = extract_frequency("Paracetamol 500mg")
    assert freq is None
    assert remaining == "Paracetamol 500mg"


def test_extract_frequency_at_bedtime_free_text():
    freq, _ = extract_frequency("Melatonin 3mg at bedtime")
    assert freq.code == "HS"


def test_extract_frequency_as_needed_free_text():
    freq, _ = extract_frequency("Paracetamol 500mg as needed")
    assert freq.code == "SOS"


# --- extract_duration -------------------------------------------------------


def test_extract_duration_x_n_days():
    duration, remaining = extract_duration("Paracetamol BD x 5 days")
    assert duration == Duration(value=5.0, unit="day", raw_text="x 5 days")
    assert remaining == "Paracetamol BD"


def test_extract_duration_for_n_weeks():
    duration, _ = extract_duration("Amoxicillin TDS for 2 weeks")
    assert duration.value == 2.0
    assert duration.unit == "week"


def test_extract_duration_months():
    duration, _ = extract_duration("Atorvastatin OD for 3 months")
    assert duration.unit == "month"


def test_extract_duration_returns_none_when_absent():
    duration, remaining = extract_duration("Paracetamol BD")
    assert duration is None
    assert remaining == "Paracetamol BD"


# --- extract_route_form -----------------------------------------------------


def test_extract_route_form_tab_prefix():
    form, remaining = extract_route_form("Tab. Paracetamol 500mg BD")
    assert form == "tablet"
    assert remaining == "Paracetamol 500mg BD"


def test_extract_route_form_cap_prefix():
    form, remaining = extract_route_form("Cap Amoxicillin 250mg TDS")
    assert form == "capsule"
    assert remaining == "Amoxicillin 250mg TDS"


def test_extract_route_form_syp_prefix():
    form, remaining = extract_route_form("Syp. Cough Mixture 10ml TDS")
    assert form == "syrup"
    assert remaining == "Cough Mixture 10ml TDS"


def test_extract_route_form_inj_prefix():
    form, _ = extract_route_form("Inj. Adrenaline 1mg STAT")
    assert form == "injection"


def test_extract_route_form_only_matches_leading_prefix_not_mid_string():
    # "Tab" appearing mid-string (not as the leading token) is not a
    # dosage-form prefix to strip.
    form, remaining = extract_route_form("Paracetamol Tab 500mg BD")
    assert form is None
    assert remaining == "Paracetamol Tab 500mg BD"


def test_extract_route_form_returns_none_when_absent():
    form, remaining = extract_route_form("Paracetamol 500mg BD")
    assert form is None
    assert remaining == "Paracetamol 500mg BD"


def test_extract_route_form_case_insensitive():
    form, _ = extract_route_form("tab paracetamol 500mg")
    assert form == "tablet"
