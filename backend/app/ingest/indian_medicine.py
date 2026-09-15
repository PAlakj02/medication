"""Indian medicine dataset loader — real data, not a stub.

Point `csv_path` at indian_medicine_data.csv (columns: id, name,
price(₹), Is_discontinued, manufacturer_name, type, pack_size_label,
short_composition1, short_composition2).

Scope cuts, documented rather than silent:
  - Skips discontinued rows (Is_discontinued == "TRUE") — ~3% of the file.
    A discontinued product shouldn't be surfaced as a substitute suggestion.
  - `price` and `pack_size_label` are not loaded — the schema you specified
    has no column for either on `product`. Worth adding if
    app.alternatives.ranking should eventually rank by cost (its docstring
    already flags Jan Aushadhi pricing as a natural next step; this dataset
    would feed the same column).
  - `otc_status` is left null — this dataset doesn't carry it. See
    app.models.product.Product.otc_status and the migration that made it
    nullable.
  - Each product's `name` here is already SKU-specific (e.g. "Augmentin 625
    Duo Tablet"), unlike RxNorm's bare brand names — so unlike
    rxnorm_bulk.py, this loader does NOT collapse multiple rows into one
    Product; distinct row = distinct product (matched for idempotent re-run
    by (name, manufacturer), per Product's unique constraint).
"""

import csv
import logging
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.ingest.base import IngestResult, SourceLoader
from app.ingest.common import ProductCache, get_or_create_source
from app.ingest.indian_medicine_parsing import parse_composition_field
from app.ingest.ingredient_resolver import IngredientResolver
from app.models.enums import Market
from app.models.product_ingredient import ProductIngredient

logger = logging.getLogger(__name__)

LICENSE = "Unknown/unverified — confirm redistribution rights before production use."
_BATCH_SIZE = 2000


class IndianMedicineLoader(SourceLoader):
    source_name = "Indian Medicine Dataset"

    def __init__(self, csv_path: Path, source_url: str | None = None):
        self.csv_path = Path(csv_path)
        # No canonical URL is known for this specific CSV (its provenance
        # wasn't confirmed) — pass one in if you know where it came from.
        self.source_url = source_url

    def load(self, db: Session) -> IngestResult:
        errors: list[str] = []

        source = get_or_create_source(
            db, name=self.source_name, url=self.source_url, license=LICENSE
        )
        db.flush()

        resolver = IngredientResolver(db)
        resolver.warm()
        products = ProductCache(db, market=Market.IN)
        products.warm()

        pending_links: list[dict] = []
        skipped_discontinued = 0
        skipped_no_composition = 0
        rows_processed = 0

        def flush_links() -> None:
            nonlocal pending_links
            if not pending_links:
                return
            stmt = pg_insert(ProductIngredient).values(pending_links)
            stmt = stmt.on_conflict_do_nothing(constraint="uq_product_ingredient")
            db.execute(stmt)
            pending_links = []

        with self.csv_path.open(newline="", encoding="utf-8") as f:
            for record in csv.DictReader(f):
                rows_processed += 1

                if record.get("Is_discontinued", "").strip().upper() == "TRUE":
                    skipped_discontinued += 1
                    continue

                compositions = [
                    parse_composition_field(record.get("short_composition1", "")),
                    parse_composition_field(record.get("short_composition2", "")),
                ]
                compositions = [c for c in compositions if c is not None]
                if not compositions:
                    skipped_no_composition += 1
                    continue

                name = record.get("name", "").strip()
                if not name:
                    continue
                manufacturer = record.get("manufacturer_name", "").strip() or None

                product = products.get_or_create(name, manufacturer=manufacturer, otc_status=None)

                for comp in compositions:
                    ingredient = resolver.get_or_create(comp.name)
                    pending_links.append(
                        {
                            "product_id": product.id,
                            "ingredient_id": ingredient.id,
                            "strength_mg": comp.strength,
                            "unit": comp.unit,
                        }
                    )
                    if len(pending_links) >= _BATCH_SIZE:
                        flush_links()

        flush_links()

        if skipped_discontinued:
            logger.info("Indian medicine dataset: skipped %d discontinued rows", skipped_discontinued)
        if skipped_no_composition:
            errors.append(f"{skipped_no_composition} rows had no parseable composition and were skipped")

        db.commit()

        resolver.log_summary(label="indian_medicine")
        logger.info(
            "Indian medicine dataset: %d rows processed, %d ingredients, %d products",
            rows_processed,
            resolver.created_count,
            products.created_count,
        )

        return IngestResult(
            source_name=self.source_name,
            ingredients_created=resolver.created_count,
            ingredients_updated=0,
            products_created=products.created_count,
            products_updated=0,
            interactions_created=0,
            timing_rules_created=0,
            errors=errors,
        )
