from app.ingest.normalization import normalize_salt_form


def test_lowercases():
    assert normalize_salt_form("Aspirin") == "aspirin"


def test_collapses_punctuation_and_whitespace():
    assert normalize_salt_form("St. John's   Wort") == "st johns wort"


def test_strips_trailing_hydrochloride():
    assert normalize_salt_form("Diphenhydramine hydrochloride") == "diphenhydramine"


def test_strips_trailing_hcl_abbreviation():
    assert normalize_salt_form("Sertraline HCl") == "sertraline"


def test_strips_trailing_sodium():
    assert normalize_salt_form("Naproxen Sodium") == "naproxen"


def test_strips_trailing_sulfate():
    assert normalize_salt_form("Morphine Sulfate") == "morphine"


def test_strips_trailing_maleate():
    assert normalize_salt_form("Chlorpheniramine Maleate") == "chlorpheniramine"


def test_strips_trailing_besylate():
    assert normalize_salt_form("Amlodipine Besylate") == "amlodipine"


def test_strips_trailing_tartrate():
    assert normalize_salt_form("Metoprolol Tartrate") == "metoprolol"


def test_does_not_strip_salt_form_word_that_is_the_whole_name():
    # A standalone "Sodium" (e.g. as a mineral supplement) should not be
    # reduced to an empty string.
    assert normalize_salt_form("Sodium") == "sodium"


def test_does_not_strip_salt_form_word_when_not_trailing():
    # "Sodium" appearing mid-name (not as a trailing salt-form suffix)
    # should be left alone.
    assert normalize_salt_form("Sodium Chloride Injection") == "sodium chloride injection"


def test_only_strips_one_trailing_salt_form():
    # Not a realistic drug name, but the transform should be a single pass,
    # not a loop that keeps stripping.
    assert normalize_salt_form("Foo Sodium Sulfate") == "foo sodium"


def test_two_different_source_spellings_converge():
    assert normalize_salt_form("Acetylsalicylic Acid") == normalize_salt_form(
        "acetylsalicylic acid"
    )
    # (Aspirin vs Acetylsalicylic acid is a *different-name* problem, not a
    # salt-form-suffix problem — this normalizer alone doesn't solve that
    # one; that's what the curated CSV tier is for.)


def test_empty_string_returns_empty_string():
    assert normalize_salt_form("") == ""
    assert normalize_salt_form("   ") == ""


# --- "Name (qualifier)" stripping ---------------------------------------


def test_strips_trailing_route_qualifier():
    assert normalize_salt_form("Brimonidine (ophthalmic)") == "brimonidine"


def test_strips_trailing_topical_qualifier():
    assert normalize_salt_form("Doxepin (topical)") == "doxepin"


def test_strips_trailing_formulation_qualifier():
    assert normalize_salt_form("Insulin human (isophane)") == "insulin human"


def test_strips_trailing_self_referential_qualifier():
    # "Insulin aspart (aspart)" -- the qualifier repeats a word already in
    # the name; still just a trailing paren block to drop wholesale.
    assert normalize_salt_form("Insulin aspart (aspart)") == "insulin aspart"


def test_strips_multiple_trailing_qualifiers():
    assert normalize_salt_form("Name (a) (b)") == "name"


def test_qualifier_stripping_combines_with_salt_form_stripping():
    assert (
        normalize_salt_form("Diphenhydramine Hydrochloride (topical)") == "diphenhydramine"
    )


def test_does_not_strip_a_leading_or_mid_string_parenthetical():
    # Only a TRAILING paren block is a qualifier to drop -- a parenthetical
    # elsewhere in the name is left alone (punctuation-stripped like any
    # other, not specially removed).
    assert normalize_salt_form("(Test) Ingredient") == "test ingredient"


def test_qualifier_stripping_on_name_with_no_parens_is_a_no_op():
    assert normalize_salt_form("Aspirin") == "aspirin"


def test_empty_parens_alone_strip_to_empty_string():
    assert normalize_salt_form("()") == ""


def test_qualifier_only_no_base_name_still_normalizes_the_remainder():
    # Edge case: nothing before the parens at all.
    assert normalize_salt_form("(topical)") == ""
