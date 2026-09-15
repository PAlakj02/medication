"""Pure regex extraction of dose, frequency, duration, and dosage-form
prefix from prescription text — no DB, no I/O. Module 1's regex half; the
gazetteer (drug-name matching) half is app.linking.resolver, which calls
into this module to strip these spans out before attempting a match.

Every extractor returns (parsed_or_None, remaining_text) — composable, and
each one independently returns None (abstains) rather than guessing when
the text doesn't clearly match a known pattern. Same philosophy as
app.ingest.normalization and app.linking.resolver's abstain threshold:
silently guessing wrong is worse than not extracting a field at all.

Deliberately not exhaustive — common prescription-shorthand formats only,
per the "initial version, refine edge cases as we go" scope. Notably
missing: complex combined frequencies ("BD for 3 days then OD"), range
doses ("1-2 tablets"), and multi-drug lines — all flagged as follow-up
work, not silently mishandled.
"""

import re
from dataclasses import dataclass

# --- dose -----------------------------------------------------------------

_DOSE_UNIT_CANONICAL = {
    "mg": "mg",
    "mcg": "mcg",
    "μg": "mcg",
    "ug": "mcg",
    "g": "g",
    "ml": "ml",
    "iu": "iu",
    "unit": "unit",
    "units": "unit",
    "tab": "tablet",
    "tabs": "tablet",
    "tablet": "tablet",
    "tablets": "tablet",
    "cap": "capsule",
    "caps": "capsule",
    "capsule": "capsule",
    "capsules": "capsule",
    "drop": "drop",
    "drops": "drop",
    "puff": "puff",
    "puffs": "puff",
    "tsp": "tsp",
    "teaspoon": "tsp",
    "teaspoons": "tsp",
}
_DOSE_RE = re.compile(
    r"\b(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>mg|mcg|μg|ug|g|ml|iu|units?|tabs?|tablets?|caps?|capsules?|drops?|puffs?|tsp|teaspoons?)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class DoseAmount:
    value: float
    unit: str  # canonical, e.g. "mg", "tablet"
    raw_text: str


def extract_dose(text: str) -> tuple[DoseAmount | None, str]:
    match = _DOSE_RE.search(text)
    if match is None:
        return None, text
    unit = _DOSE_UNIT_CANONICAL[match.group("unit").lower()]
    dose = DoseAmount(value=float(match.group("value")), unit=unit, raw_text=match.group(0))
    remaining = (text[: match.start()] + " " + text[match.end() :]).strip()
    remaining = re.sub(r"\s+", " ", remaining)
    return dose, remaining


# --- frequency --------------------------------------------------------------


@dataclass(frozen=True)
class Frequency:
    code: str  # OD, BD, TDS, QDS, QOD, HS, SOS, STAT, CUSTOM
    times_per_day: float | None  # None for SOS/STAT (not a fixed daily count)
    raw_text: str


# Ordered longest/most-specific pattern first where overlap is possible
# (e.g. QDS before QOD before OD) — first match found wins.
_FREQUENCY_ABBREVIATIONS: list[tuple[str, float | None, str]] = [
    ("QDS", 4.0, r"\bq\.?d\.?s\.?\b|\bq\.?i\.?d\.?\b"),
    ("TDS", 3.0, r"\bt\.?d\.?s\.?\b|\bt\.?i\.?d\.?\b"),
    ("QOD", 0.5, r"\bq\.?o\.?d\.?\b"),
    ("BD", 2.0, r"\bb\.?i\.?d\.?\b|\bbd\b"),
    ("HS", 1.0, r"\bh\.?s\.?\b"),
    ("STAT", None, r"\bstat\b"),
    ("SOS", None, r"\bs\.?o\.?s\.?\b|\bprn\b"),
    ("OD", 1.0, r"\bo\.?d\.?\b"),
]

_FREQUENCY_FREE_TEXT: list[tuple[str, float | None, str]] = [
    ("QDS", 4.0, r"\bfour times (?:a day|daily)\b"),
    ("TDS", 3.0, r"\bthree times (?:a day|daily)\b|\bthrice (?:a day|daily)\b"),
    ("BD", 2.0, r"\btwice (?:a day|daily)\b|\btwo times (?:a day|daily)\b"),
    ("OD", 1.0, r"\bonce (?:a day|daily)\b"),
    ("HS", 1.0, r"\bat bedtime\b|\bbefore bed\b|\bat night\b"),
    ("SOS", None, r"\bas needed\b|\bas required\b"),
]

_EVERY_N_HOURS_RE = re.compile(r"\bevery\s+(?P<hours>\d+(?:\.\d+)?)\s*(?:hours?|hrs?)\b", re.IGNORECASE)


def extract_frequency(text: str) -> tuple[Frequency | None, str]:
    earliest: tuple[re.Match, str, float | None] | None = None

    for code, times_per_day, pattern in [*_FREQUENCY_FREE_TEXT, *_FREQUENCY_ABBREVIATIONS]:
        match = re.search(pattern, text, re.IGNORECASE)
        if match is not None and (earliest is None or match.start() < earliest[0].start()):
            earliest = (match, code, times_per_day)

    hours_match = _EVERY_N_HOURS_RE.search(text)
    if hours_match is not None and (earliest is None or hours_match.start() < earliest[0].start()):
        hours = float(hours_match.group("hours"))
        earliest = (hours_match, "CUSTOM", round(24.0 / hours, 2) if hours > 0 else None)

    if earliest is None:
        return None, text

    match, code, times_per_day = earliest
    frequency = Frequency(code=code, times_per_day=times_per_day, raw_text=match.group(0))
    remaining = (text[: match.start()] + " " + text[match.end() :]).strip()
    remaining = re.sub(r"\s+", " ", remaining)
    return frequency, remaining


# --- duration ---------------------------------------------------------------

_DURATION_UNIT_CANONICAL = {"day": "day", "days": "day", "week": "week", "weeks": "week", "month": "month", "months": "month"}
_DURATION_RE = re.compile(
    r"(?:\bx\b|\bfor\b)\s*(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>days?|weeks?|months?)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Duration:
    value: float
    unit: str  # day, week, month
    raw_text: str


def extract_duration(text: str) -> tuple[Duration | None, str]:
    match = _DURATION_RE.search(text)
    if match is None:
        return None, text
    unit = _DURATION_UNIT_CANONICAL[match.group("unit").lower()]
    duration = Duration(value=float(match.group("value")), unit=unit, raw_text=match.group(0))
    remaining = (text[: match.start()] + " " + text[match.end() :]).strip()
    remaining = re.sub(r"\s+", " ", remaining)
    return duration, remaining


# --- route / dosage form prefix ---------------------------------------------

_ROUTE_FORM_CANONICAL = {
    "tab": "tablet",
    "tabs": "tablet",
    "tablet": "tablet",
    "tablets": "tablet",
    "cap": "capsule",
    "caps": "capsule",
    "capsule": "capsule",
    "capsules": "capsule",
    "syp": "syrup",
    "syrup": "syrup",
    "inj": "injection",
    "injection": "injection",
    "susp": "suspension",
    "suspension": "suspension",
    "oint": "ointment",
    "ointment": "ointment",
    "cream": "cream",
    "drop": "drops",
    "drops": "drops",
    "gel": "gel",
}
# Anchored at the START of the string only — a form prefix is a leading
# token ("Tab. Paracetamol..."), not something to hunt for mid-string.
_ROUTE_FORM_RE = re.compile(
    r"^\s*(?P<form>tabs?|tablets?|caps?|capsules?|syp|syrup|inj|injection|susp|suspension|"
    r"oint|ointment|cream|drops?|gel)\.?\s+",
    re.IGNORECASE,
)


def extract_route_form(text: str) -> tuple[str | None, str]:
    match = _ROUTE_FORM_RE.match(text)
    if match is None:
        return None, text
    form = _ROUTE_FORM_CANONICAL[match.group("form").lower()]
    remaining = text[match.end() :].strip()
    return form, remaining
