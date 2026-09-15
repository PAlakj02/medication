"""DDInter loader — real interaction-pair data, not a stub.

Point `data_dir` at the folder containing DDInter's per-category CSV
exports (ddinter_downloads_code_*.csv, downloaded from
http://ddinter.scbdd.com/download/). Parsing/dedup logic lives in
ddinter_parsing.py (interaction-pair severity semantics) and
ddinter_coverage.py (per-drug/per-class mention tracking) — both pure,
unit tested; this module is only the DB I/O.

License note: DDInter is a public academic database. Verify its license
terms (see http://ddinter.scbdd.com/) before any commercial/production use
— DEFAULT_LICENSE below is a placeholder reminder, not a verified statement.
"""

import csv
import logging
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.ingest.base import IngestResult, SourceLoader
from app.ingest.common import get_or_create_source
from app.ingest.ddinter_coverage import (
    ATC_TOP_LEVEL,
    RawMentionRow,
    build_class_code_by_name,
    extract_mentions,
)
from app.ingest.ddinter_parsing import (
    RawPairRow,
    Severity,
    build_mechanism_text,
    dedupe_pairs,
    normalize_pair,
    severity_rank,
)
from app.ingest.ingredient_resolver import IngredientResolver
from app.models.enums import Severity as OrmSeverity
from app.models.ingredient_source_mention import IngredientSourceMention
from app.models.interaction import Interaction
from app.models.source_coverage import SourceCoverage

logger = logging.getLogger(__name__)

SOURCE_URL = "http://ddinter.scbdd.com/"
DEFAULT_LICENSE = "Academic/research use — verify DDInter's license terms before production/commercial use."

_BATCH_SIZE = 2000
_FILE_PREFIX = "ddinter_downloads_code_"


class DDInterLoader(SourceLoader):
    source_name = "DDInter"

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)

    def _read_rows(self) -> list[tuple[RawPairRow, str]]:
        """Returns (row, class_code) — class_code is the source file's
        letter (e.g. "ddinter_downloads_code_A.csv" -> "A"), used only for
        coverage tracking (see ddinter_coverage.py), not the interaction
        pipeline itself.
        """
        rows: list[tuple[RawPairRow, str]] = []
        paths = sorted(self.data_dir.glob(f"{_FILE_PREFIX}*.csv"))
        if not paths:
            raise FileNotFoundError(
                f"No {_FILE_PREFIX}*.csv files found under {self.data_dir}"
            )
        for path in paths:
            class_code = path.stem.replace(_FILE_PREFIX, "").upper()
            with path.open(newline="", encoding="utf-8") as f:
                for record in csv.DictReader(f):
                    row = RawPairRow(
                        drug_a=record.get("Drug_A", ""),
                        drug_b=record.get("Drug_B", ""),
                        level=record.get("Level", ""),
                    )
                    rows.append((row, class_code))
        return rows

    def load(self, db: Session) -> IngestResult:
        errors: list[str] = []
        raw_rows_with_class = self._read_rows()
        raw_rows = [row for row, _class_code in raw_rows_with_class]

        normalized = []
        for row in raw_rows:
            pair = normalize_pair(row)
            if pair is None:
                errors.append(f"skipped unparseable row: {row!r}")
                continue
            normalized.append(pair)

        pairs = dedupe_pairs(normalized)
        logger.info(
            "DDInter: %d raw rows -> %d parseable -> %d unique pairs",
            len(raw_rows),
            len(normalized),
            len(pairs),
        )

        source = get_or_create_source(
            db, name=self.source_name, url=SOURCE_URL, license=DEFAULT_LICENSE
        )
        db.flush()

        resolver = IngredientResolver(db)
        resolver.warm()

        # Resolve every pair to an ingredient-id pair FIRST, keeping only
        # the highest-ranked severity per (a_id, b_id), before any DB
        # insert — NOT the same as dedupe_pairs()'s dedup above, which only
        # catches collisions between IDENTICAL raw strings. Two DIFFERENT
        # strings (e.g. "Paclitaxel" and "Paclitaxel (protein-bound)") can
        # now resolve to the SAME ingredient thanks to normalize_salt_form's
        # qualifier-stripping — without this second dedup pass, whichever
        # row happened to be inserted first would silently win via
        # ON CONFLICT DO NOTHING, which could arbitrarily keep a LOWER
        # severity than a conflicting duplicate actually recorded. Checked
        # against real data: this affects ~887 pairs.
        best_by_ingredient_pair: dict[tuple[int, int], dict] = {}
        collisions_resolved = 0

        for pair in pairs:
            ing_a = resolver.get_or_create(pair.name_a)
            ing_b = resolver.get_or_create(pair.name_b)
            if ing_a.id == ing_b.id:
                # Two different source strings resolved to the same
                # ingredient (e.g. a name already merged from another
                # source) — no self-interaction row possible.
                continue

            a_id, b_id = (ing_a.id, ing_b.id) if ing_a.id < ing_b.id else (ing_b.id, ing_a.id)
            key = (a_id, b_id)
            severity: Severity | None = pair.severity
            mechanism = build_mechanism_text(pair.name_a, pair.name_b, severity, pair.severity_ungraded)
            candidate = {
                "ingredient_a_id": a_id,
                "ingredient_b_id": b_id,
                "severity": OrmSeverity(severity.value) if severity is not None else None,
                "severity_ungraded": pair.severity_ungraded,
                "mechanism": mechanism,
                "source_id": source.id,
                "source_text": mechanism,
                "_rank": severity_rank(severity, pair.severity_ungraded),
            }

            existing = best_by_ingredient_pair.get(key)
            if existing is None:
                best_by_ingredient_pair[key] = candidate
            elif candidate["_rank"] > existing["_rank"]:
                best_by_ingredient_pair[key] = candidate
                collisions_resolved += 1
            else:
                collisions_resolved += 1

        if collisions_resolved:
            logger.info(
                "DDInter: %d post-resolution ingredient-pair collisions resolved "
                "(different raw names now sharing one canonical ingredient) — kept the "
                "highest-ranked severity per pair, not whichever inserted first",
                collisions_resolved,
            )

        pending: list[dict] = []
        interactions_attempted = 0

        def flush_batch() -> None:
            nonlocal pending
            if not pending:
                return
            stmt = pg_insert(Interaction).values(pending)
            stmt = stmt.on_conflict_do_nothing(constraint="uq_interaction_pair")
            db.execute(stmt)
            pending = []

        for candidate in best_by_ingredient_pair.values():
            candidate = {k: v for k, v in candidate.items() if k != "_rank"}
            pending.append(candidate)
            interactions_attempted += 1
            if len(pending) >= _BATCH_SIZE:
                flush_batch()

        flush_batch()
        db.commit()

        mentions_recorded, classes_covered = self._record_coverage(
            db, resolver, raw_rows_with_class, source.id
        )
        db.commit()

        resolver.log_summary(label="ddinter")
        logger.info(
            "DDInter coverage: %d ingredient mentions recorded, %d/%d ATC classes covered",
            mentions_recorded,
            len(classes_covered),
            len(ATC_TOP_LEVEL),
        )

        return IngestResult(
            source_name=self.source_name,
            ingredients_created=resolver.created_count,
            ingredients_updated=0,
            products_created=0,
            products_updated=0,
            # Rows attempted, not rows actually inserted — ON CONFLICT DO
            # NOTHING means a re-run reports the same number here even
            # though 0 new rows land. Query `interaction` count yourself
            # for the true delta on a re-run.
            interactions_created=interactions_attempted,
            timing_rules_created=0,
            errors=errors,
        )

    def _record_coverage(
        self,
        db: Session,
        resolver: IngredientResolver,
        raw_rows_with_class: list[tuple[RawPairRow, str]],
        source_id: int,
    ) -> tuple[int, set[str]]:
        """Populates source_coverage (which ATC classes this source's data
        covers, based on which per-category files exist) and
        ingredient_source_mention (which ingredients it mentioned at all —
        the ground truth for check_pair's NOT_CHECKED_SOURCE_GAP state).
        Uses ALL raw rows, including "Unknown"-severity ones dropped from
        the interaction pipeline — DDInter still has *some* data on a drug
        even when it couldn't grade a given pair, and that's what coverage
        tracks.
        """
        mention_rows = [
            RawMentionRow(drug_a=row.drug_a, drug_b=row.drug_b, class_code=class_code)
            for row, class_code in raw_rows_with_class
        ]
        mentions = extract_mentions(mention_rows)
        class_code_by_name = build_class_code_by_name(mentions)

        classes_present = {class_code for _row, class_code in raw_rows_with_class}
        coverage_pending = [
            {
                "source_id": source_id,
                "atc_class_code": code,
                "atc_class_label": label,
                "covered": code in classes_present,
            }
            for code, label in ATC_TOP_LEVEL.items()
        ]
        stmt = pg_insert(SourceCoverage).values(coverage_pending)
        stmt = stmt.on_conflict_do_nothing(constraint="uq_source_coverage_class")
        db.execute(stmt)

        mention_pending: list[dict] = []
        recorded = 0

        def flush_mentions() -> None:
            nonlocal mention_pending
            if not mention_pending:
                return
            stmt = pg_insert(IngredientSourceMention).values(mention_pending)
            stmt = stmt.on_conflict_do_nothing(constraint="uq_ingredient_source_mention")
            db.execute(stmt)
            mention_pending = []

        for name, class_code in class_code_by_name.items():
            ingredient, tier = resolver.resolve(name)
            if ingredient is None:
                # Shouldn't happen — every name here was already
                # get_or_create'd while building interactions above — but
                # stay defensive rather than crash a load over it.
                continue
            mention_pending.append(
                {"ingredient_id": ingredient.id, "source_id": source_id, "atc_class_code": class_code}
            )
            recorded += 1
            if len(mention_pending) >= _BATCH_SIZE:
                flush_mentions()
        flush_mentions()

        return recorded, classes_present
