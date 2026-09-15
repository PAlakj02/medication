"""RxNorm bulk-file loader — real data, not a stub.

Distinct from app.ingest.rxnav.RxNavLoader (still a stub): that one is for
incrementally pulling new/changed concepts from the live RxNav REST API.
This one loads a static "Full Prescribable Content" RRF download in one
pass — what you actually have on disk right now.

Point `rrf_path` at RXNCONSO.RRF from the extracted release.

Ingredient loading (TTY IN/PIN/MIN) moved to app.ingest.alias_prepass —
run that FIRST. This loader now only handles branded drugs (TTY SBD) ->
app.models.product.Product (market=US) + ProductIngredient, via the
heuristic string parser in rxnorm_parsing.py. Ingredient names found in SBD
strings are resolved through IngredientResolver (exact/SY/normalized/
curated) same as every other loader — most should already exist from the
alias pre-pass; any that don't get created here as a fallback.

NOT loaded here (documented scope cuts, not oversights):
  - SCD (generic/unbranded clinical drugs) — no brand, so nothing to create
    a Product row for; the ingredients they'd reference are already covered
    by the alias pre-pass's IN/PIN/MIN pass.
  - RXNREL.RRF / RXNSAT.RRF — relationship and attribute files. RXNREL
    would give authoritative (not regex-inferred) brand<->ingredient links;
    RXNSAT carries additional attributes (e.g. some marketing-status
    signals) that could help populate Product.otc_status instead of leaving
    it null. Both are materially bigger parsing jobs, left as a TODO.
  - Known limitation: a brand name that covers multiple real strength
    formulations (e.g. "Maxzide" 50mg/75mg AND 25mg/37.5mg are both real
    RxNorm SBD concepts) collapses to ONE Product row here (Product has no
    per-formulation key), keeping only the first-encountered strength per
    ingredient. A more faithful model would key Product on (brand, RXCUI)
    instead of brand name alone — deferred given scope.
"""

import logging
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.ingest.base import IngestResult, SourceLoader
from app.ingest.common import ProductCache, get_or_create_source
from app.ingest.ingredient_resolver import IngredientResolver
from app.ingest.rxnorm_parsing import (
    ConsoRow,
    is_branded_drug_concept,
    parse_clinical_drug_string,
    parse_rrf_line,
)
from app.models.enums import Market
from app.models.product_ingredient import ProductIngredient

logger = logging.getLogger(__name__)

SOURCE_URL = "https://www.nlm.nih.gov/research/umls/rxnorm/"
LICENSE = "UMLS Metathesaurus License Agreement (NLM) — required to use RxNorm data; verify compliance."

_BATCH_SIZE = 2000

# A handful of RxNorm SBD gene-therapy products (e.g. onasemnogene
# abeparvovec) carry strengths in the trillions — vector-genome counts per
# mL, not a realistic "mg" dose. Segments at or above this are skipped
# entirely (not resolved as an ingredient, not linked) rather than stored;
# see app.models.product_ingredient.ProductIngredient.strength_mg.
MAX_STRENGTH = 1_000_000_000


def _iter_conso_rows(rrf_path: Path) -> Iterator[ConsoRow]:
    with rrf_path.open(encoding="utf-8") as f:
        for line in f:
            row = parse_rrf_line(line)
            if row is not None:
                yield row


class RxNormBulkLoader(SourceLoader):
    source_name = "RxNorm"

    def __init__(self, rrf_path: Path):
        self.rrf_path = Path(rrf_path)

    def load(self, db: Session) -> IngestResult:
        errors: list[str] = []

        source = get_or_create_source(db, name=self.source_name, url=SOURCE_URL, license=LICENSE)
        db.flush()

        resolver = IngredientResolver(db)
        resolver.warm()
        products = ProductCache(db, market=Market.US)
        products.warm()

        sbd_rows: list[ConsoRow] = [
            row for row in _iter_conso_rows(self.rrf_path) if is_branded_drug_concept(row)
        ]

        logger.info("RxNorm: %d SBD rows to parse", len(sbd_rows))

        pending_links: list[dict] = []
        parse_failures = 0
        strength_out_of_range = 0

        def flush_links() -> None:
            nonlocal pending_links
            if not pending_links:
                return
            stmt = pg_insert(ProductIngredient).values(pending_links)
            stmt = stmt.on_conflict_do_nothing(constraint="uq_product_ingredient")
            db.execute(stmt)
            pending_links = []

        for row in sbd_rows:
            parsed = parse_clinical_drug_string(row.str_)
            if parsed is None or parsed.brand is None:
                parse_failures += 1
                continue

            product = products.get_or_create(parsed.brand, manufacturer=None, otc_status=None)

            for ing_strength in parsed.ingredients:
                if ing_strength.strength >= MAX_STRENGTH:
                    strength_out_of_range += 1
                    continue
                ingredient = resolver.get_or_create(ing_strength.name)
                pending_links.append(
                    {
                        "product_id": product.id,
                        "ingredient_id": ingredient.id,
                        "strength_mg": ing_strength.strength,
                        "unit": ing_strength.unit,
                    }
                )
                if len(pending_links) >= _BATCH_SIZE:
                    flush_links()

        flush_links()

        if parse_failures:
            errors.append(f"{parse_failures} SBD rows could not be parsed by the heuristic string parser")
        if strength_out_of_range:
            errors.append(
                f"{strength_out_of_range} ingredient-strength segments skipped — "
                f"strength >= {MAX_STRENGTH:,} (not a realistic mg dose, e.g. gene-therapy vector-genome counts)"
            )

        db.commit()

        resolver.log_summary(label="rxnorm_bulk")

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
