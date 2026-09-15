"""Pure parsing for indian_medicine_data.csv's composition columns — no DB,
no file I/O.

short_composition1/short_composition2 hold strings like "Ofloxacin (200mg)"
or, for combination products, one ingredient per column e.g.
short_composition1="Cefixime (50mg)", short_composition2="Ofloxacin (50mg)".
Real variety seen in this dataset that the parser has to handle (see
tests/ingest/test_indian_medicine_parsing.py for the exact cases):
  - A qualifier in its own parens before the real strength, e.g.
    "Dehydroepiandrosterone (Micronized) (75mg)" — the LAST parenthetical
    group is taken as the strength; any earlier ones are stripped from the
    name as qualifiers, not treated as the strength.
  - Compound units with a space, e.g. "Clobetasol (0.05% w/w)".
  - Non-mass "strength" values that don't cleanly split into number+unit,
    e.g. "Lactobacillus (60Million spores)" — degrades gracefully to
    strength=60, unit="Million spores" rather than failing the row; the
    `unit` column is free text (see app.models.product_ingredient), the
    `strength_mg` name is inherited from the requested schema and is a
    misnomer for non-mass units like this one.
  - No parenthetical at all — returns None; the loader still records the
    ingredient's existence via the raw name in that case, just without a
    strength (see indian_medicine.py).
"""

import re
from dataclasses import dataclass

_LAST_PAREN_RE = re.compile(r"\(([^()]*)\)")
_AMOUNT_RE = re.compile(r"^(?P<strength>\d+(?:\.\d+)?)\s*(?P<unit>.*)$")

# product_ingredient.unit is String(16) — truncate rather than let a long
# unit string fail the insert.
MAX_UNIT_LENGTH = 16


@dataclass(frozen=True)
class CompositionIngredient:
    name: str
    strength: float | None
    unit: str | None


def parse_composition_field(raw: str) -> CompositionIngredient | None:
    s = raw.strip()
    if not s:
        return None

    parens = list(_LAST_PAREN_RE.finditer(s))
    if not parens:
        # No strength info at all in this field — still a real ingredient
        # name, just without dosage. Loader decides whether that's usable.
        return CompositionIngredient(name=s, strength=None, unit=None)

    last = parens[-1]
    name = s[: last.start()]
    # Strip any earlier parenthetical qualifiers too, e.g. "(Micronized)".
    name = _LAST_PAREN_RE.sub("", name).strip()
    if not name:
        return None

    amount_raw = last.group(1).strip()
    if not amount_raw:
        return CompositionIngredient(name=name, strength=None, unit=None)

    amount_match = _AMOUNT_RE.match(amount_raw)
    if not amount_match:
        return CompositionIngredient(name=name, strength=None, unit=amount_raw[:MAX_UNIT_LENGTH])

    strength = float(amount_match.group("strength"))
    unit = amount_match.group("unit").strip() or None
    if unit:
        unit = unit[:MAX_UNIT_LENGTH]
    return CompositionIngredient(name=name, strength=strength, unit=unit)
