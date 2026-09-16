"""Curated dosing-timing rules — data/timing_rules.csv is hand-sourced from
real FDA/DailyMed drug labels (URLs in the CSV), not fabricated, and
deliberately covers only a small, well-documented set of ingredients. A
missing timing rule for a given ingredient means "not yet curated", never
"no timing considerations apply" — see app.findings.timing and the API
layer for how that distinction is surfaced.

Read-only against the ingredient gazetteer: resolves each CSV row's
ingredient_name via IngredientResolver.resolve() (exact/SY/normalized/
inn_usan/curated tiers only) and never creates a new ingredient — a row
whose name doesn't resolve is a data-entry bug in the CSV, logged as an
error rather than silently skipped or guessed.
"""

import csv
import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingest.base import IngestResult, SourceLoader
from app.ingest.common import get_or_create_source
from app.ingest.ingredient_resolver import IngredientResolver
from app.models.enums import TimingRuleType
from app.models.timing_rule import TimingRule

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TimingRuleRow:
    ingredient_name: str
    rule_type: str
    offset_minutes: int | None
    note: str
    source_name: str
    source_url: str


def read_timing_rule_rows(csv_path: Path) -> list[TimingRuleRow]:
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [
            TimingRuleRow(
                ingredient_name=row["ingredient_name"].strip(),
                rule_type=row["rule_type"].strip(),
                offset_minutes=int(row["offset_minutes"]) if row["offset_minutes"].strip() else None,
                note=row["note"].strip(),
                source_name=row["source_name"].strip(),
                source_url=row["source_url"].strip(),
            )
            for row in reader
        ]


class TimingRuleLoader(SourceLoader):
    source_name = "Curated timing rules"

    def __init__(self, csv_path: Path):
        self.csv_path = csv_path

    def load(self, db: Session) -> IngestResult:
        resolver = IngredientResolver(db)
        resolver.warm()

        # load() must be idempotent (SourceLoader's contract) — no unique
        # DB constraint on (ingredient_id, rule_type), so dedupe here.
        existing: set[tuple[int, str]] = {
            (ingredient_id, rule_type.value)
            for ingredient_id, rule_type in db.execute(
                select(TimingRule.ingredient_id, TimingRule.rule_type)
            ).all()
        }

        rows = read_timing_rule_rows(self.csv_path)
        errors: list[str] = []
        created = 0

        # One Source row per distinct (name, url) pair, not per CSV row —
        # matches get_or_create_source's dedupe-by-name contract.
        sources_by_name: dict[str, object] = {}

        for row in rows:
            ingredient, _tier = resolver.resolve(row.ingredient_name)
            if ingredient is None:
                errors.append(f"Could not resolve ingredient_name={row.ingredient_name!r} — skipped.")
                continue

            try:
                rule_type = TimingRuleType(row.rule_type)
            except ValueError:
                errors.append(
                    f"Unknown rule_type={row.rule_type!r} for {row.ingredient_name!r} — skipped."
                )
                continue

            if (ingredient.id, rule_type.value) in existing:
                continue

            source = sources_by_name.get(row.source_name)
            if source is None:
                source = get_or_create_source(
                    db, name=row.source_name, url=row.source_url, license=None
                )
                sources_by_name[row.source_name] = source

            db.add(
                TimingRule(
                    ingredient_id=ingredient.id,
                    rule_type=rule_type,
                    offset_minutes=row.offset_minutes,
                    note=row.note,
                    source_id=source.id,
                )
            )
            existing.add((ingredient.id, rule_type.value))
            created += 1

        db.commit()

        for err in errors:
            logger.warning(err)

        return IngestResult(
            source_name=self.source_name,
            ingredients_created=0,
            ingredients_updated=0,
            products_created=0,
            products_updated=0,
            interactions_created=0,
            timing_rules_created=created,
            errors=errors,
        )
