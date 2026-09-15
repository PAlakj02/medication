"""Ingredient alias pre-pass — run this BEFORE ddinter.py, rxnorm_bulk.py,
and indian_medicine.py. Loads RxNorm's canonical ingredients (IN/PIN/MIN
concepts) together with their SY synonyms, then the hand-verified
INN/USAN map, then the open-ended hand-curated data/aliases.csv — so every
other loader's ingredient resolution (via IngredientResolver) benefits
from all three before it runs.

Four passes over the same RXNCONSO.RRF read (kept in memory between the
first two rather than re-reading the file):
  1. Canonical ingredients: every usable IN/PIN/MIN row becomes (or
     backfills) an Ingredient row, keyed by RXCUI.
  2. SY synonyms: every usable SY row whose RXCUI matches a canonical
     ingredient from pass 1 becomes an IngredientAlias(tier=SY) row.
  3. INN/USAN aliases: data/inn_usan_map.csv (documented INN-vs-USAN
     naming divergences, e.g. paracetamol/acetaminophen), resolved against
     passes 1-2 — see the file's header for its format.
  4. Curated aliases: data/aliases.csv, resolved against everything above
     (plus any curated rows already loaded) — see that file's header.
"""

import csv
import logging
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.ingest.base import IngestResult, SourceLoader
from app.ingest.common import get_or_create_source
from app.ingest.ingredient_resolver import IngredientResolver
from app.ingest.rxnorm_parsing import ConsoRow, is_ingredient_concept, parse_rrf_line
from app.models.enums import AliasTier
from app.models.ingredient_alias import IngredientAlias

logger = logging.getLogger(__name__)

RXNORM_SOURCE_URL = "https://www.nlm.nih.gov/research/umls/rxnorm/"
RXNORM_LICENSE = "UMLS Metathesaurus License Agreement (NLM) — required to use RxNorm data; verify compliance."
CURATED_SOURCE_NAME = "Manual curation"
INN_USAN_SOURCE_NAME = "INN/USAN mapping"

_BATCH_SIZE = 2000

# See app.models.ingredient.Ingredient.name docstring: RxNorm's MIN concepts
# include multi-antigen combination vaccine names up to ~2600 chars (p99.9
# of all RXNCONSO STR values is 469). Names/aliases longer than this are
# skipped, not truncated — truncating would silently create a different,
# wrong ingredient name.
MAX_NAME_LENGTH = 500


def _is_sy_row(row: ConsoRow) -> bool:
    return row.sab == "RXNORM" and row.lat == "ENG" and row.suppress == "N" and row.tty == "SY"


def _maybe_deprecate_orphan(resolver: IngredientResolver, alias_name: str, target) -> bool:  # noqa: ANN001
    """For inn_usan/curated tiers only (never sy/normalized — see module
    docstring): if `alias_name` already resolves to a DIFFERENT ingredient
    via plain EXACT match, and that existing ingredient is a true orphan
    (rxcui is None — not an independently-real RxNorm concept like
    "doxycycline hyclate" next to "doxycycline"), deprecate it so the new
    alias isn't permanently shadowed by it. Returns True if a deprecation
    happened.
    """
    existing, existing_tier = resolver.resolve(alias_name)
    if existing is None or existing.id == target.id:
        return False
    if existing_tier != "exact":
        # Don't deprecate for a spelling (normalized) or sy match — only a
        # raw pre-existing orphan ingredient row justifies this.
        return False
    if existing.rxcui is not None:
        # A real, independently-loaded RxNorm concept, not an orphan —
        # leave both as separate ingredients rather than fold one away.
        return False
    resolver.deprecate(existing)
    return True


class AliasPrepassLoader(SourceLoader):
    source_name = "Ingredient alias pre-pass"

    def __init__(self, rrf_path: Path, curated_csv_path: Path, inn_usan_csv_path: Path | None = None):
        self.rrf_path = Path(rrf_path)
        self.curated_csv_path = Path(curated_csv_path)
        self.inn_usan_csv_path = (
            Path(inn_usan_csv_path)
            if inn_usan_csv_path is not None
            else self.curated_csv_path.parent / "inn_usan_map.csv"
        )

    def load(self, db: Session) -> IngestResult:
        errors: list[str] = []
        resolver = IngredientResolver(db)
        resolver.warm()

        rxnorm_source = get_or_create_source(
            db, name="RxNorm", url=RXNORM_SOURCE_URL, license=RXNORM_LICENSE
        )
        db.flush()

        rxcui_to_ingredient_id, sy_rows, skipped_too_long = self._load_canonical_ingredients(resolver)
        logger.info(
            "Alias pre-pass: %d canonical ingredients from RxNorm IN/PIN/MIN, %d SY rows to attach",
            len(rxcui_to_ingredient_id),
            len(sy_rows),
        )
        if skipped_too_long:
            errors.append(
                f"{skipped_too_long} IN/PIN/MIN concepts skipped — name longer than "
                f"{MAX_NAME_LENGTH} chars (multi-antigen combination vaccine names)"
            )

        sy_attached, sy_unmatched = self._attach_sy_aliases(
            db, resolver, sy_rows, rxcui_to_ingredient_id, rxnorm_source.id
        )
        if sy_unmatched:
            logger.info(
                "Alias pre-pass: %d SY rows skipped (RXCUI not an IN/PIN/MIN loaded above)",
                sy_unmatched,
            )
        db.commit()

        inn_usan_attached, inn_usan_unresolved = self._attach_inn_usan_aliases(db, resolver, errors)
        db.commit()
        logger.info(
            "Alias pre-pass: %d INN/USAN aliases attached, %d rows skipped (us_name unresolved)",
            inn_usan_attached,
            inn_usan_unresolved,
        )

        curated_attached = self._attach_curated_aliases(db, resolver, errors)
        db.commit()

        resolver.log_summary(label="alias-prepass")
        logger.info(
            "Alias pre-pass: %d SY aliases attached, %d INN/USAN aliases attached, %d curated aliases attached",
            sy_attached,
            inn_usan_attached,
            curated_attached,
        )

        return IngestResult(
            source_name=self.source_name,
            ingredients_created=resolver.created_count,
            ingredients_updated=0,
            products_created=0,
            products_updated=0,
            interactions_created=0,
            timing_rules_created=0,
            errors=errors,
        )

    def _load_canonical_ingredients(
        self, resolver: IngredientResolver
    ) -> tuple[dict[str, int], list[ConsoRow], int]:
        rxcui_to_ingredient_id: dict[str, int] = {}
        sy_rows: list[ConsoRow] = []
        skipped_too_long = 0

        with self.rrf_path.open(encoding="utf-8") as f:
            for line in f:
                row = parse_rrf_line(line)
                if row is None:
                    continue
                if is_ingredient_concept(row):
                    if len(row.str_) > MAX_NAME_LENGTH:
                        skipped_too_long += 1
                        continue
                    ingredient = resolver.get_or_create_canonical(row.str_, rxcui=row.rxcui)
                    rxcui_to_ingredient_id[row.rxcui] = ingredient.id
                elif _is_sy_row(row):
                    sy_rows.append(row)

        return rxcui_to_ingredient_id, sy_rows, skipped_too_long

    def _attach_sy_aliases(
        self,
        db: Session,
        resolver: IngredientResolver,
        sy_rows: list[ConsoRow],
        rxcui_to_ingredient_id: dict[str, int],
        source_id: int,
    ) -> tuple[int, int]:
        pending: list[dict] = []
        attached = 0
        unmatched = 0

        def flush_batch() -> None:
            nonlocal pending
            if not pending:
                return
            stmt = pg_insert(IngredientAlias).values(pending)
            stmt = stmt.on_conflict_do_nothing(constraint="uq_ingredient_alias_name_tier")
            db.execute(stmt)
            pending = []

        for row in sy_rows:
            ingredient_id = rxcui_to_ingredient_id.get(row.rxcui)
            if ingredient_id is None:
                unmatched += 1
                continue
            ingredient = resolver.get_by_id(ingredient_id)
            alias_name = " ".join(row.str_.strip().split())
            if not alias_name or len(alias_name) > MAX_NAME_LENGTH:
                continue
            resolver.register_alias(alias_name, ingredient, AliasTier.SY)
            pending.append(
                {
                    "ingredient_id": ingredient_id,
                    "alias_name": alias_name,
                    "tier": AliasTier.SY,
                    "source_id": source_id,
                }
            )
            attached += 1
            if len(pending) >= _BATCH_SIZE:
                flush_batch()
        flush_batch()

        return attached, unmatched

    def _attach_inn_usan_aliases(
        self, db: Session, resolver: IngredientResolver, errors: list[str]
    ) -> tuple[int, int]:
        source = get_or_create_source(
            db,
            name=INN_USAN_SOURCE_NAME,
            url=None,
            license=None,
        )
        db.flush()

        pending: list[dict] = []
        attached = 0
        unresolved = 0
        deprecated = 0

        def flush_batch() -> None:
            nonlocal pending
            if not pending:
                return
            stmt = pg_insert(IngredientAlias).values(pending)
            stmt = stmt.on_conflict_do_nothing(constraint="uq_ingredient_alias_name_tier")
            db.execute(stmt)
            pending = []

        for inn_name, us_name in self._read_inn_usan_rows():
            target, _tier = resolver.resolve(us_name)
            if target is None:
                unresolved += 1
                errors.append(
                    f"data/inn_usan_map.csv: us_name {us_name!r} does not resolve to any "
                    f"existing ingredient (inn_name {inn_name!r} skipped)"
                )
                continue
            if _maybe_deprecate_orphan(resolver, inn_name, target):
                deprecated += 1
            resolver.register_alias(inn_name, target, AliasTier.INN_USAN)
            pending.append(
                {
                    "ingredient_id": target.id,
                    "alias_name": " ".join(inn_name.strip().split()),
                    "tier": AliasTier.INN_USAN,
                    "source_id": source.id,
                }
            )
            attached += 1
        flush_batch()

        if deprecated:
            logger.info("Alias pre-pass: %d ingredients deprecated while attaching INN/USAN aliases", deprecated)

        return attached, unresolved

    def _read_inn_usan_rows(self) -> list[tuple[str, str]]:
        """data/inn_usan_map.csv columns: inn_name,us_name,rxcui,source,notes
        — only inn_name/us_name are used for aliasing; rxcui/source/notes
        are documentation for a human reviewing the file, not consumed here.
        """
        if not self.inn_usan_csv_path.exists():
            return []
        with self.inn_usan_csv_path.open(newline="", encoding="utf-8") as f:
            rows: list[tuple[str, str]] = []
            for record in csv.DictReader(f):
                inn_name = (record.get("inn_name") or "").strip()
                us_name = (record.get("us_name") or "").strip()
                if inn_name and us_name:
                    rows.append((inn_name, us_name))
        return rows

    def _attach_curated_aliases(
        self, db: Session, resolver: IngredientResolver, errors: list[str]
    ) -> int:
        curated_source = get_or_create_source(
            db, name=CURATED_SOURCE_NAME, url=None, license=None
        )
        db.flush()

        pending: list[dict] = []
        attached = 0
        deprecated = 0

        def flush_batch() -> None:
            nonlocal pending
            if not pending:
                return
            stmt = pg_insert(IngredientAlias).values(pending)
            stmt = stmt.on_conflict_do_nothing(constraint="uq_ingredient_alias_name_tier")
            db.execute(stmt)
            pending = []

        for alias, canonical_name in self._read_curated_rows():
            target, _tier = resolver.resolve(canonical_name)
            if target is None:
                errors.append(
                    f"data/aliases.csv: canonical_name {canonical_name!r} does not resolve "
                    f"to any existing ingredient (alias {alias!r} skipped)"
                )
                continue
            if _maybe_deprecate_orphan(resolver, alias, target):
                deprecated += 1
            resolver.register_alias(alias, target, AliasTier.CURATED)
            pending.append(
                {
                    "ingredient_id": target.id,
                    "alias_name": " ".join(alias.strip().split()),
                    "tier": AliasTier.CURATED,
                    "source_id": curated_source.id,
                }
            )
            attached += 1
        flush_batch()

        if deprecated:
            logger.info("Alias pre-pass: %d ingredients deprecated while attaching curated aliases", deprecated)

        return attached

    def _read_curated_rows(self) -> list[tuple[str, str]]:
        if not self.curated_csv_path.exists():
            return []
        with self.curated_csv_path.open(newline="", encoding="utf-8") as f:
            lines = [line for line in f if not line.lstrip().startswith("#")]
        if not lines:
            return []
        rows: list[tuple[str, str]] = []
        for record in csv.DictReader(lines):
            alias = (record.get("alias") or "").strip()
            canonical_name = (record.get("canonical_name") or "").strip()
            if alias and canonical_name:
                rows.append((alias, canonical_name))
        return rows
