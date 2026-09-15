"""Shared get-or-create helpers for ingest/ loaders — kept out of app.ingest.base
because base.py defines the loader *interface*, not shared implementation.

Ingredient identity resolution is app.ingest.ingredient_resolver.IngredientResolver
(exact → SY → normalized → curated, never fuzzy) — not here. This module
only has the Product and Source helpers, which don't need multi-tier
resolution.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import Market, OtcStatus
from app.models.product import Product
from app.models.source import Source


def normalize_name(name: str) -> str:
    return " ".join(name.strip().split())


class ProductCache:
    """Same idea as IngredientCache, keyed on (market, lower(name),
    lower(manufacturer)) to match Product's uq_product_name_manufacturer
    constraint. `manufacturer=None` is a valid, distinct key (products with
    unknown manufacturer all share one bucket per name) — that's a
    deliberate simplification for sources that don't carry manufacturer
    data (e.g. RxNorm-derived branded products); see
    app.ingest.rxnorm_bulk for the known limitation this creates when the
    same brand name covers multiple real strength variants.
    """

    def __init__(self, db: Session, market: Market):
        self.db = db
        self.market = market
        self._by_key: dict[tuple[str, str], Product] = {}
        self.created_count = 0

    def _key(self, name: str, manufacturer: str | None) -> tuple[str, str]:
        return (name.strip().lower(), (manufacturer or "").strip().lower())

    def warm(self) -> None:
        stmt = select(Product).where(Product.market == self.market)
        for product in self.db.execute(stmt).scalars():
            self._by_key[self._key(product.name, product.manufacturer)] = product

    def get_or_create(
        self,
        raw_name: str,
        manufacturer: str | None = None,
        otc_status: OtcStatus | None = None,
    ) -> Product:
        """Trusts the in-memory index built by warm() — no per-miss DB
        fallback query. An earlier version had one (matching lower(name)),
        but on a bulk load where most rows are cache misses (e.g. ~246K
        largely-distinct product names), that meant one unindexed
        func.lower(Product.name) query PER ROW — the dominant cost in a
        run that took 10+ minutes and was still nowhere near done. Same
        lesson as IngredientResolver, which never had this problem: after
        warm(), the in-memory index IS the source of truth for this run.
        """
        name = normalize_name(raw_name)
        manufacturer = normalize_name(manufacturer) if manufacturer else None
        key = self._key(name, manufacturer)

        existing = self._by_key.get(key)
        if existing is not None:
            return existing

        product = Product(name=name, market=self.market, manufacturer=manufacturer, otc_status=otc_status)
        self.db.add(product)
        self.db.flush()
        self._by_key[key] = product
        self.created_count += 1
        return product


def get_or_create_source(
    db: Session,
    name: str,
    url: str | None,
    license: str | None,
    retrieved_at: datetime | None = None,
) -> Source:
    existing = db.execute(select(Source).where(Source.name == name)).scalar_one_or_none()
    if existing is not None:
        return existing

    source = Source(
        name=name,
        url=url,
        license=license,
        retrieved_at=retrieved_at or datetime.now(timezone.utc),
    )
    db.add(source)
    db.flush()
    return source
