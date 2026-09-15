"""Proposes ingredient-alias mappings for the top unresolved names from the
coverage report — writes ONLY to data/aliases_proposed.csv for human review.
Never writes to data/aliases.csv and never touches the DB's alias table.
Task explicitly separates "propose" from "merge": this script does the
former only.

Two kinds of evidence, always labeled which one a proposal rests on:
  1. "rxnconso": an exact-text match for the alias found ANYWHERE in
     RXNCONSO.RRF (any source vocabulary, not just RXNORM/SY — broader than
     what app.ingest.alias_prepass actually loads, since this is a
     human-reviewed proposal stage, not the committed pipeline) sharing an
     RXCUI with an ingredient already canonical in our DB. This is the
     strong-evidence case — a real data row, not a guess.
  2. "domain_knowledge": no RXNCONSO row exists for the alias under any
     vocabulary (checked, not assumed), so the proposal rests on known
     INN-vs-USAN / British-vs-US spelling pairs (e.g. Paracetamol /
     Acetaminophen). Weaker evidence — a claim, not a data row — and
     labeled as such so you can weight it accordingly on review.

Every candidate that was checked and found NO usable evidence either way
is still included, with an explicit "no_proposal" row — so this file shows
everything that was looked at, not just the hits.
"""

import csv
from collections import Counter
from pathlib import Path

from app.db import SessionLocal
from app.ingest.ingredient_resolver import IngredientResolver
from scripts.coverage_report import (
    DDINTER_DIR,
    INDIAN_MEDICINE_CSV,
    RRF_PATH,
    read_ddinter_name_counts,
    read_indian_medicine_name_counts,
    resolve_name_counts,
)

BACKEND_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = BACKEND_ROOT / "data" / "aliases_proposed.csv"

TOP_N_INDIA = 50
TOP_N_DDINTER = 30

# High-confidence INN-vs-USAN / British-vs-US spelling pairs, used ONLY
# when RXNCONSO has no row for the alias under any source vocabulary
# (checked per-candidate, not assumed). Every value here must itself
# resolve to a real canonical (rxcui-bearing) ingredient already in the DB
# — verified programmatically below, not just asserted; if it doesn't
# resolve, the candidate is downgraded to no_proposal rather than shown
# as a hit.
DOMAIN_KNOWLEDGE = {
    "paracetamol": "acetaminophen",
    "paracetamol/acetaminophen": "acetaminophen",
    "amoxycillin": "amoxicillin",
    "salbutamol": "albuterol",
    "levosalbutamol": "levalbuterol",
    "thyroxine": "levothyroxine",
    "tazobactum": "tazobactam",
    "beclometasone": "beclomethasone",
    "frusemide": "furosemide",
    "adrenaline": "epinephrine",
    "noradrenaline": "norepinephrine",
    "cetirizine hydrochloride": "cetirizine",
    "diclofenac sodium": "diclofenac",
}


def find_rxnconso_match(alias: str) -> tuple[str, str, str] | None:
    """Case-insensitive exact match for `alias` against STR anywhere in
    RXNCONSO.RRF (any SAB/TTY). Returns (rxcui, sab, tty) for the first hit,
    or None. A full-file scan per call — fine for a few dozen candidates,
    not meant for bulk use.
    """
    target = alias.strip().lower()
    with RRF_PATH.open(encoding="utf-8") as f:
        for line in f:
            fields = line.rstrip("\n").split("|")
            if len(fields) < 17:
                continue
            if fields[14].strip().lower() == target:
                return fields[0], fields[11], fields[12]  # rxcui, sab, tty
    return None


def main() -> None:
    db = SessionLocal()
    try:
        resolver = IngredientResolver(db)
        resolver.warm()

        ddinter_counts = read_ddinter_name_counts()
        indian_counts, _ = read_indian_medicine_name_counts()

        _, ddinter_unresolved = resolve_name_counts(resolver, ddinter_counts)
        _, indian_unresolved = resolve_name_counts(resolver, indian_counts)

        candidates: Counter = Counter()
        for name, count in indian_unresolved.most_common(TOP_N_INDIA):
            candidates[name] += count
        for name, count in ddinter_unresolved.most_common(TOP_N_DDINTER):
            candidates[name] += count

        rows: list[dict] = []
        for alias, mention_count in candidates.most_common():
            rxnconso_hit = find_rxnconso_match(alias)
            if rxnconso_hit is not None:
                rxcui, sab, tty = rxnconso_hit
                target_ingredient = resolver.find_by_rxcui(rxcui)
                if target_ingredient is not None:
                    rows.append(
                        {
                            "alias": alias,
                            "proposed_canonical_name": target_ingredient.name,
                            "confidence": "high",
                            "evidence": (
                                f"rxnconso: RXCUI {rxcui} (SAB={sab}, TTY={tty}) matches "
                                f"canonical ingredient {target_ingredient.name!r} (id={target_ingredient.id})"
                            ),
                            "mention_count": mention_count,
                        }
                    )
                    continue
                # RXCUI found in RXNCONSO but that RXCUI isn't one of our
                # loaded canonical ingredients (e.g. it's an ingredient
                # RxNorm has that alias_prepass skipped or that isn't
                # IN/PIN/MIN) — real evidence, but nothing to alias TO yet.
                rows.append(
                    {
                        "alias": alias,
                        "proposed_canonical_name": "",
                        "confidence": "none",
                        "evidence": (
                            f"rxnconso: found RXCUI {rxcui} (SAB={sab}, TTY={tty}) but it is not "
                            f"among the ingredients currently loaded — nothing to alias to yet"
                        ),
                        "mention_count": mention_count,
                    }
                )
                continue

            guess = DOMAIN_KNOWLEDGE.get(alias.strip().lower())
            if guess is not None:
                target, tier = resolver.resolve(guess)
                if target is not None and target.rxcui is not None:
                    rows.append(
                        {
                            "alias": alias,
                            "proposed_canonical_name": target.name,
                            "confidence": "medium",
                            "evidence": (
                                f"domain_knowledge: known INN/USAN or spelling variant of "
                                f"{target.name!r} (not found under any SAB in RXNCONSO — "
                                f"verify before merging)"
                            ),
                            "mention_count": mention_count,
                        }
                    )
                    continue
                # Our own guess didn't even resolve to a real canonical
                # ingredient — don't claim a proposal we can't back up.

            rows.append(
                {
                    "alias": alias,
                    "proposed_canonical_name": "",
                    "confidence": "none",
                    "evidence": (
                        "no_proposal: not found under any SAB in RXNCONSO, no domain-knowledge "
                        "match — likely a genuinely new ingredient not in RxNorm (e.g. not "
                        "US-marketed) or needs manual research"
                    ),
                    "mention_count": mention_count,
                }
            )

        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as f:
            f.write(
                "# Machine-proposed ingredient aliases — FOR REVIEW ONLY.\n"
                "# Generated by scripts/propose_aliases.py from the top unresolved names in\n"
                "# coverage_report.md. Nothing here has been merged into data/aliases.csv or\n"
                "# the DB — copy the rows you accept into data/aliases.csv yourself (its header\n"
                "# comment explains that file's format).\n"
                "#\n"
                "# confidence: high = alias found verbatim in RXNCONSO.RRF (any vocabulary),\n"
                "#   sharing an RXCUI with an already-canonical ingredient in the DB — a real\n"
                "#   data row, not a guess. medium = no RXNCONSO evidence; rests on a known\n"
                "#   INN/USAN or spelling pair (see DOMAIN_KNOWLEDGE in this script) — verify\n"
                "#   before trusting. none = checked, nothing usable found either way.\n"
                "#\n"
                "# mention_count: how many products/pairs this alias appeared in per\n"
                "# coverage_report.md — proxy for how much this one row is worth fixing.\n"
            )
            writer = csv.DictWriter(
                f, fieldnames=["alias", "proposed_canonical_name", "confidence", "evidence", "mention_count"]
            )
            writer.writeheader()
            writer.writerows(rows)

        high = sum(1 for r in rows if r["confidence"] == "high")
        medium = sum(1 for r in rows if r["confidence"] == "medium")
        none = sum(1 for r in rows if r["confidence"] == "none")
        print(f"Wrote {len(rows)} proposals to {OUTPUT_PATH}")
        print(f"  high={high}, medium={medium}, none={none}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
