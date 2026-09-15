"""Pure parsing/normalization for DDInter CSV rows — no DB, no file I/O.
Kept separate from ddinter.py (the loader) for the same reason
app.findings.engine is kept separate from app.findings.repository: this is
the part worth unit testing in isolation.

DDInter's bulk export has severity (Minor/Moderate/Major, or "Unknown" for
~47K of the ~222K raw rows) but no mechanism or source-excerpt text. Per the
product decision made for this dataset (broad coverage now, real mechanism
text as a later enrichment pass): every pair gets an honest, non-fabricated
mechanism sentence that states only what DDInter's classification actually
says, nothing more.

"Unknown"-severity rows are NOT dropped — they load with severity=None and
severity_ungraded=True. A real, sourced interaction that DDInter didn't
grade is still more useful to a safety tool than silently discarding it;
what matters is that it stays clearly distinguishable from a graded one at
every layer (DB constraint, API field, rendered text).
"""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum


class Severity(str, Enum):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"


# Ungraded ranks below even LOW for dedup-conflict purposes: a known grade
# (even "low") is more informative than "unknown" — see dedupe_pairs and
# severity_rank.
_SEVERITY_RANK = {Severity.LOW: 0, Severity.MODERATE: 1, Severity.HIGH: 2}
_UNGRADED_RANK = -1


def severity_rank(severity: Severity | None, ungraded: bool) -> int:
    """Public so callers outside this module (ddinter.py's post-resolution
    dedup — see its module docstring) can apply the identical "keep the
    highest-ranked, graded beats ungraded" policy this module uses for
    string-level dedup, instead of re-implementing or drifting from it."""
    return _UNGRADED_RANK if ungraded else _SEVERITY_RANK[severity]

_LEVEL_MAP = {
    "major": Severity.HIGH,
    "moderate": Severity.MODERATE,
    "minor": Severity.LOW,
}
_UNGRADED_LEVEL = "unknown"


@dataclass(frozen=True)
class ParsedSeverity:
    severity: Severity | None
    ungraded: bool


@dataclass(frozen=True)
class RawPairRow:
    drug_a: str
    drug_b: str
    level: str


@dataclass(frozen=True)
class NormalizedPair:
    """name_a/name_b are ordered case-insensitive-lexicographically, not
    tied to the source's Drug_A/Drug_B columns — DDInter's per-category CSV
    split means the same real-world pair can appear as (A, B) in one file
    and (B, A) in another; this ordering is what makes dedup possible."""

    name_a: str
    name_b: str
    severity: Severity | None
    severity_ungraded: bool


def parse_severity(level: str) -> ParsedSeverity | None:
    """Returns None only for genuinely unrecognized text — not for
    "Unknown", which is DDInter's own explicit ungraded marker and gets a
    real (severity=None, ungraded=True) result, not a rejection."""
    normalized = level.strip().lower()
    if normalized == _UNGRADED_LEVEL:
        return ParsedSeverity(severity=None, ungraded=True)
    severity = _LEVEL_MAP.get(normalized)
    if severity is None:
        return None
    return ParsedSeverity(severity=severity, ungraded=False)


def normalize_pair(row: RawPairRow) -> NormalizedPair | None:
    """Returns None for rows that can't be used at all: blank names, a drug
    paired with itself, or truly unrecognized severity text (not "Unknown",
    which is a valid ungraded result — see parse_severity)."""
    a = " ".join(row.drug_a.strip().split())
    b = " ".join(row.drug_b.strip().split())
    if not a or not b or a.lower() == b.lower():
        return None

    parsed = parse_severity(row.level)
    if parsed is None:
        return None

    if a.lower() > b.lower():
        a, b = b, a
    return NormalizedPair(name_a=a, name_b=b, severity=parsed.severity, severity_ungraded=parsed.ungraded)


def _pair_rank(pair: NormalizedPair) -> int:
    return severity_rank(pair.severity, pair.severity_ungraded)


def dedupe_pairs(pairs: Iterable[NormalizedPair]) -> list[NormalizedPair]:
    """De-dupes by (name_a, name_b) case-insensitively. If the same pair
    shows up with conflicting severities across the per-category files
    (possible, since the split can put one real-world pair in two files),
    keeps the HIGHEST-ranked one — a safety tool should round up, not down,
    when sources disagree, and a graded severity always beats "unknown".
    Stable order: first-seen position is preserved.
    """
    best: dict[tuple[str, str], NormalizedPair] = {}
    order: list[tuple[str, str]] = []
    for pair in pairs:
        key = (pair.name_a.lower(), pair.name_b.lower())
        if key not in best:
            order.append(key)
            best[key] = pair
        elif _pair_rank(pair) > _pair_rank(best[key]):
            best[key] = pair
    return [best[key] for key in order]


def build_mechanism_text(name_a: str, name_b: str, severity: Severity | None, ungraded: bool) -> str:
    """Deliberately terse and literal — states only the one fact actually
    known (DDInter's classification, graded or not), nothing invented. See
    module docstring."""
    if ungraded:
        return (
            f"DDInter records a potential interaction between {name_a} and {name_b} "
            f"but does not assign it a severity grade."
        )
    return f"DDInter classifies concurrent use of {name_a} and {name_b} as a {severity.value}-severity interaction."
