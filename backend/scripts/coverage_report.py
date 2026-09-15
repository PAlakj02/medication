"""Ingredient-resolution coverage report — read-only.

Re-resolves every raw ingredient name from each source's ORIGINAL file
against the ingredient/alias state currently in the DB (via
IngredientResolver.resolve(), never get_or_create()) and reports where the
gaps are. Does not write to the DB or to data/aliases.csv — the output is
input for a human to act on (data/aliases.csv), not something this script
edits itself.

Run scripts/run_ingest.py first. Usage:
    PYTHONPATH=. uv run python scripts/coverage_report.py > coverage_report.md

Caveat spelled out inline in the ATC section: DDInter's bulk CSVs carry no
ATC code column, and the RxNorm RXNCONSO.RRF in this data drop has zero
ATC-sourced rows (checked: `awk -F'|' '$12=="ATC"'` matches nothing) — there
is no real per-ingredient ATC mapping available to compute "which ATC
classes DDInter covers" precisely. The only signal that exists is which of
DDInter's per-category download files are present, and their single-letter
names happen to match WHO ATC top-level codes — that's used here as an
explicitly-labeled proxy, not a verified mapping.
"""

import csv
from collections import Counter
from pathlib import Path

from app.db import SessionLocal
from app.ingest.ddinter_parsing import RawPairRow, dedupe_pairs, normalize_pair
from app.ingest.indian_medicine_parsing import parse_composition_field
from app.ingest.ingredient_resolver import IngredientResolver
from app.ingest.rxnorm_parsing import is_branded_drug_concept, parse_clinical_drug_string, parse_rrf_line
from app.ingest.rxnorm_bulk import MAX_STRENGTH

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = BACKEND_ROOT.parent
DDINTER_DIR = DATA_ROOT / "ddinter"
INDIAN_MEDICINE_CSV = DATA_ROOT / "indian_medicine_data.csv"
RRF_PATH = DATA_ROOT / "RxNorm_full_prescribe_09082026" / "rrf" / "RXNCONSO.RRF"

TOP_N_INDIA = 50

# The full WHO ATC anatomical main group taxonomy — fixed, standard, not
# derived from any dataset in this repo.
ATC_TOP_LEVEL = {
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


def ddinter_category_coverage() -> tuple[list[str], list[str]]:
    present = sorted(
        p.stem.replace("ddinter_downloads_code_", "").upper()
        for p in DDINTER_DIR.glob("ddinter_downloads_code_*.csv")
    )
    missing = sorted(set(ATC_TOP_LEVEL) - set(present))
    return present, missing


def read_ddinter_name_counts() -> Counter:
    """name -> number of distinct (deduped) pairs it appears in."""
    raw_rows: list[RawPairRow] = []
    for path in sorted(DDINTER_DIR.glob("ddinter_downloads_code_*.csv")):
        with path.open(newline="", encoding="utf-8") as f:
            for record in csv.DictReader(f):
                raw_rows.append(
                    RawPairRow(
                        drug_a=record.get("Drug_A", ""),
                        drug_b=record.get("Drug_B", ""),
                        level=record.get("Level", ""),
                    )
                )
    normalized = [p for p in (normalize_pair(r) for r in raw_rows) if p is not None]
    pairs = dedupe_pairs(normalized)

    counts: Counter = Counter()
    for pair in pairs:
        counts[pair.name_a] += 1
        counts[pair.name_b] += 1
    return counts


def read_indian_medicine_name_counts() -> tuple[Counter, dict[str, set[int]]]:
    """Returns (name -> mention count across non-discontinued products,
    name -> set of product row indices it appears in) — the second is used
    for the product-level resolved/unresolved stat.
    """
    counts: Counter = Counter()
    name_to_products: dict[str, set[int]] = {}
    with INDIAN_MEDICINE_CSV.open(newline="", encoding="utf-8") as f:
        for idx, record in enumerate(csv.DictReader(f)):
            if record.get("Is_discontinued", "").strip().upper() == "TRUE":
                continue
            for col in ("short_composition1", "short_composition2"):
                comp = parse_composition_field(record.get(col, ""))
                if comp is None:
                    continue
                counts[comp.name] += 1
                name_to_products.setdefault(comp.name, set()).add(idx)
    return counts, name_to_products


def read_rxnorm_sbd_name_counts() -> Counter:
    """name -> number of SBD rows it appears in, applying the same
    MAX_STRENGTH skip the real loader applies, so this is an apples-to-
    apples comparison against what was actually loaded.
    """
    counts: Counter = Counter()
    with RRF_PATH.open(encoding="utf-8") as f:
        for line in f:
            row = parse_rrf_line(line)
            if row is None or not is_branded_drug_concept(row):
                continue
            parsed = parse_clinical_drug_string(row.str_)
            if parsed is None:
                continue
            for ing in parsed.ingredients:
                if ing.strength >= MAX_STRENGTH:
                    continue
                counts[ing.name] += 1
    return counts


def resolve_name_counts(resolver: IngredientResolver, name_counts: Counter) -> tuple[Counter, Counter]:
    """Read-only: resolver.resolve() only, never get_or_create(). Returns
    (tier -> total mention count, unresolved name -> mention count).

    "Resolved" means matches a genuine RxNorm-canonical ingredient
    (Ingredient.rxcui IS NOT NULL) — not just any existing row. By the time
    this report runs, the DB also contains "orphan" ingredients the loaders
    themselves created for names that matched nothing (rxcui stays NULL for
    those, since only alias_prepass's get_or_create_canonical sets it).
    Without this check, an orphan created from DDInter would show as
    "exact"-resolved against itself, and 0% would ever be unresolved — an
    exact/normalized match to a non-canonical row is really "matches
    something another source's loader made up," not "verified against
    RxNorm," so it's counted as unresolved too. SY/curated alias matches
    always point at a canonical ingredient by construction (see
    alias_prepass), so those are exempt from this check.
    """
    tier_totals: Counter = Counter()
    unresolved: Counter = Counter()
    for name, count in name_counts.items():
        ingredient, tier = resolver.resolve(name)
        effectively_unresolved = tier == "created" or (
            tier in ("exact", "normalized") and (ingredient is None or ingredient.rxcui is None)
        )
        if effectively_unresolved:
            tier_totals["unresolved"] += count
            unresolved[name] = count
        else:
            tier_totals[tier] += count
    return tier_totals, unresolved


def format_source_section(source_label: str, tier_totals: Counter, unresolved: Counter, top_n: int | None) -> list[str]:
    total = sum(tier_totals.values())
    resolved = total - tier_totals.get("unresolved", 0)
    pct = (resolved / total * 100) if total else 0.0

    lines = [f"### {source_label}", ""]
    lines.append(f"- Total mentions: {total:,}")
    lines.append(f"- Resolved: {resolved:,} ({pct:.1f}%)")
    lines.append(f"- Unresolved: {tier_totals.get('unresolved', 0):,} ({len(unresolved):,} distinct names)")
    lines.append(
        f"- Resolution breakdown: exact={tier_totals.get('exact', 0):,}, "
        f"sy={tier_totals.get('sy', 0):,}, normalized={tier_totals.get('normalized', 0):,}, "
        f"curated={tier_totals.get('curated', 0):,}"
    )
    lines.append("")

    if unresolved and top_n:
        ranked = unresolved.most_common(top_n)
        lines.append(f"Top {len(ranked)} unresolved names (by mention count):")
        lines.append("")
        lines.append("| Name | Mentions |")
        lines.append("|---|---|")
        for name, count in ranked:
            lines.append(f"| {name} | {count:,} |")
        lines.append("")

    return lines


def main() -> None:
    db = SessionLocal()
    try:
        resolver = IngredientResolver(db)
        resolver.warm()

        ddinter_counts = read_ddinter_name_counts()
        indian_counts, indian_name_to_products = read_indian_medicine_name_counts()
        rxnorm_counts = read_rxnorm_sbd_name_counts()

        ddinter_tiers, ddinter_unresolved = resolve_name_counts(resolver, ddinter_counts)
        indian_tiers, indian_unresolved = resolve_name_counts(resolver, indian_counts)
        rxnorm_tiers, rxnorm_unresolved = resolve_name_counts(resolver, rxnorm_counts)

        # Product-level stat for India: a product "resolves" only if EVERY
        # ingredient it lists resolves — a partially-unresolved combination
        # product still needs attention.
        unresolved_names = set(indian_unresolved)
        all_product_indices: set[int] = set()
        unresolved_product_indices: set[int] = set()
        for name, product_indices in indian_name_to_products.items():
            all_product_indices |= product_indices
            if name in unresolved_names:
                unresolved_product_indices |= product_indices
        resolved_product_count = len(all_product_indices) - len(unresolved_product_indices)

        present_atc, missing_atc = ddinter_category_coverage()

        lines: list[str] = []
        lines.append("# Ingredient Resolution Coverage Report")
        lines.append("")
        lines.append(
            f"Generated against **{resolver.known_ingredient_count:,} canonical ingredients** "
            f"and **{resolver.known_alias_count:,} aliases** currently loaded in the DB."
        )
        lines.append("")
        lines.append(
            "Read-only report — re-resolves each source's raw names against the current "
            "ingredient/alias state, does not modify the DB or `data/aliases.csv`."
        )
        lines.append("")

        lines.append("## 1. Unresolved ingredient names per source")
        lines.append("")
        lines += format_source_section("DDInter", ddinter_tiers, ddinter_unresolved, top_n=30)
        lines += format_source_section("RxNorm (SBD branded products)", rxnorm_tiers, rxnorm_unresolved, top_n=30)
        lines += format_source_section("Indian medicine dataset", indian_tiers, indian_unresolved, top_n=None)

        lines.append("## 2. DDInter ATC category coverage")
        lines.append("")
        lines.append(
            "**Caveat**: DDInter's bulk CSV export carries no ATC code column, and the RxNorm "
            "RXNCONSO.RRF in this data drop has zero ATC-sourced rows — there is no real "
            "per-ingredient ATC mapping available in this pipeline to compute this precisely. "
            "The signal below is which of DDInter's per-category download files are present "
            "(their single-letter names match WHO ATC top-level codes) — an approximate proxy "
            "for category coverage, not a verified per-drug ATC mapping."
        )
        lines.append("")
        lines.append(f"**Present** ({len(present_atc)}/{len(ATC_TOP_LEVEL)}): " + ", ".join(
            f"{code} ({ATC_TOP_LEVEL[code]})" for code in present_atc
        ))
        lines.append("")
        lines.append(f"**Missing** ({len(missing_atc)}/{len(ATC_TOP_LEVEL)}): " + ", ".join(
            f"{code} ({ATC_TOP_LEVEL[code]})" for code in missing_atc
        ))
        lines.append("")
        if missing_atc:
            lines.append(
                "Check DDInter's download page for these category files — if they exist "
                "upstream and simply weren't downloaded, that's the single highest-leverage "
                "gap to close (whole anatomical categories with zero interaction coverage)."
            )
            lines.append("")

        lines.append("## 3. Indian medicine dataset: product-level resolution")
        lines.append("")
        total_products = len(all_product_indices)
        pct_resolved = (resolved_product_count / total_products * 100) if total_products else 0.0
        lines.append(f"- Total non-discontinued products with at least one parseable composition: {total_products:,}")
        lines.append(
            f"- Fully resolved (every listed ingredient matches a known ingredient): "
            f"{resolved_product_count:,} ({pct_resolved:.1f}%)"
        )
        lines.append(
            f"- Partially or fully unresolved (at least one ingredient did not match): "
            f"{len(unresolved_product_indices):,} ({100 - pct_resolved:.1f}%)"
        )
        lines.append("")

        lines.append(f"## 4. Top {TOP_N_INDIA} unresolved India ingredient names — work queue for `data/aliases.csv`")
        lines.append("")
        lines.append(
            "Ranked by number of distinct products each name appears in — highest-impact "
            "first. For each, check: is this a genuine alias for an existing ingredient "
            "(add to `data/aliases.csv`), a salt-form spelling `normalize_salt_form` should "
            "already catch but doesn't (extend the salt-form list), or a real ingredient RxNorm "
            "doesn't have at all (nothing to alias — it's a legitimately new ingredient)?"
        )
        lines.append("")
        lines.append("| Rank | Name | Product count |")
        lines.append("|---|---|---|")
        for rank, (name, count) in enumerate(indian_unresolved.most_common(TOP_N_INDIA), start=1):
            lines.append(f"| {rank} | {name} | {count:,} |")
        lines.append("")

        print("\n".join(lines))
    finally:
        db.close()


if __name__ == "__main__":
    main()
