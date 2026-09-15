"""Pure logic for DDInter's per-drug/per-class coverage tracking — separate
from ddinter_parsing.py (interaction-pair severity semantics) since this
feeds a different table (ingredient_source_mention / source_coverage), not
Interaction rows. See app.models.ingredient_source_mention's docstring for
why only Drug_A-position mentions carry a class code.
"""

from collections.abc import Iterable
from dataclasses import dataclass

# The full WHO ATC anatomical main group taxonomy — fixed, standard, not
# derived from any dataset. Kept here (not just in scripts/coverage_report.py)
# since app.ingest.ddinter needs it to populate source_coverage's
# "not present" rows too, not just the report.
ATC_TOP_LEVEL: dict[str, str] = {
    "A": "Alimentary tract and metabolism",
    "B": "Blood and blood forming organs",
    "C": "Cardiovascular system",
    "D": "Dermatologicals",
    "G": "Genito-urinary system and sex hormones",
    "H": "Systemic hormonal preparations, excl. sex hormones",
    "J": "Antiinfectives for systemic use",
    "L": "Antineoplastic and immunomodulating agents",
    "M": "Musculoskeletal system",
    "N": "Nervous system",
    "P": "Antiparasitic products, insecticides and repellents",
    "R": "Respiratory system",
    "S": "Sensory organs",
    "V": "Various",
}


@dataclass(frozen=True)
class RawMentionRow:
    drug_a: str
    drug_b: str
    class_code: str  # from the source filename, e.g. "A"


@dataclass(frozen=True)
class MentionRecord:
    name: str
    class_code: str | None  # None for a Drug_B-position mention


def extract_mentions(rows: Iterable[RawMentionRow]) -> list[MentionRecord]:
    mentions: list[MentionRecord] = []
    for row in rows:
        a = " ".join(row.drug_a.strip().split())
        b = " ".join(row.drug_b.strip().split())
        if a:
            mentions.append(MentionRecord(name=a, class_code=row.class_code))
        if b:
            mentions.append(MentionRecord(name=b, class_code=None))
    return mentions


def build_class_code_by_name(mentions: Iterable[MentionRecord]) -> dict[str, str | None]:
    """Case-insensitive-keyed: first mention WITH a class code wins for a
    given name; a name only ever seen Drug_B-side stays mapped to None
    (still a real mention, just no class evidence)."""
    result: dict[str, str | None] = {}
    for mention in mentions:
        key = mention.name.lower()
        if key not in result:
            result[key] = mention.class_code
        elif result[key] is None and mention.class_code is not None:
            result[key] = mention.class_code
    return result


def class_codes_present(rows: Iterable[RawMentionRow]) -> set[str]:
    return {row.class_code for row in rows}
