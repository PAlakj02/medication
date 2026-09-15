"""Pure parsing for RxNorm's RRF bulk files — no DB, no file I/O beyond
splitting a line already read by the caller.

RXNCONSO.RRF column layout (standard RxNorm/UMLS RRF format), pipe-delimited
with a trailing pipe:
  0 RXCUI | 1 LAT | 2 TS | 3 LUI | 4 STT | 5 SUI | 6 ISPREF | 7 RXAUI |
  8 SAUI | 9 SCUI | 10 SDUI | 11 SAB | 12 TTY | 13 CODE | 14 STR |
  15 SRL | 16 SUPPRESS | 17 CVF

Two things this module does:
  1. Pick out ingredient-level concepts (TTY IN/PIN/MIN) — straightforward
     field extraction, these are just canonical names.
  2. Parse SBD ("Semantic Branded Drug") STR strings into brand + ingredient/
     strength/unit segments, e.g.
     "hydrochlorothiazide 50 MG / triamterene 75 MG Oral Tablet [Maxzide]"
     -> brand "Maxzide", ingredients [(hydrochlorothiazide, 50, MG),
     (triamterene, 75, MG)].

     This is a HEURISTIC regex parser, not authoritative — RxNorm's
     canonical way to get this relationship is RXNREL.RRF (ingredient-of /
     has-ingredient relationships), which this scaffold does not parse (that
     file is 189MB and a materially bigger parsing job — left as a TODO).
     The regex approach was verified against real sample rows from this
     dataset (see tests/ingest/test_rxnorm_parsing.py) but will not be
     perfect across all ~8-9K SBD strings; rows it can't confidently parse
     are skipped by the loader, not guessed at.
"""

import re
from dataclasses import dataclass

# Ingredient-level RxNorm term types.
INGREDIENT_TTYS = frozenset({"IN", "PIN", "MIN"})
BRANDED_DRUG_TTY = "SBD"


@dataclass(frozen=True)
class ConsoRow:
    rxcui: str
    lat: str
    sab: str
    tty: str
    suppress: str
    str_: str


def parse_rrf_line(line: str) -> ConsoRow | None:
    fields = line.rstrip("\n").split("|")
    if len(fields) < 17:
        return None
    return ConsoRow(
        rxcui=fields[0],
        lat=fields[1],
        sab=fields[11],
        tty=fields[12],
        str_=fields[14],
        suppress=fields[16],
    )


def _is_usable(row: ConsoRow) -> bool:
    """Common filter for both ingredient and branded-drug rows: canonical
    English RxNorm content, not suppressed."""
    return row.sab == "RXNORM" and row.lat == "ENG" and row.suppress == "N"


def is_ingredient_concept(row: ConsoRow) -> bool:
    return _is_usable(row) and row.tty in INGREDIENT_TTYS


def is_branded_drug_concept(row: ConsoRow) -> bool:
    return _is_usable(row) and row.tty == BRANDED_DRUG_TTY


@dataclass(frozen=True)
class IngredientStrength:
    name: str
    strength: float
    unit: str


@dataclass(frozen=True)
class ParsedClinicalDrug:
    brand: str | None
    ingredients: list[IngredientStrength]


_BRAND_RE = re.compile(r"^(?P<clinical>.+?)\s*\[(?P<brand>[^\[\]]+)\]\s*$")
_SEGMENT_RE = re.compile(
    r"^\s*(?P<name>.+?)\s+(?P<strength>\d+(?:\.\d+)?)\s*(?P<unit>[A-Za-z%]+(?:/[A-Za-z0-9.]+)?)"
)


def parse_clinical_drug_string(raw: str) -> ParsedClinicalDrug | None:
    """Returns None if no brand bracket is found (not a branded product) or
    no ingredient/strength segment could be parsed at all."""
    s = raw.strip()

    match = _BRAND_RE.match(s)
    if not match:
        return None
    brand = match.group("brand").strip()
    clinical = match.group("clinical").strip()

    ingredients: list[IngredientStrength] = []
    for segment in (seg.strip() for seg in clinical.split(" / ")):
        if not segment:
            continue
        seg_match = _SEGMENT_RE.match(segment)
        if not seg_match:
            continue
        try:
            strength = float(seg_match.group("strength"))
        except ValueError:
            continue
        ingredients.append(
            IngredientStrength(
                name=" ".join(seg_match.group("name").split()),
                strength=strength,
                unit=seg_match.group("unit"),
            )
        )

    if not ingredients:
        return None
    return ParsedClinicalDrug(brand=brand, ingredients=ingredients)
