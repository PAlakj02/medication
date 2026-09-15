"""Ingredient name resolution — the shared entry point every ingest/ loader
uses to turn a raw name string into an Ingredient row.

Resolution order, first match wins:
  1. exact      — lower(name) matches an existing Ingredient.name exactly.
  2. sy         — matches an IngredientAlias row with tier=SY (RxNorm
                  synonyms, loaded by app.ingest.alias_prepass).
  3. normalized — app.ingest.normalization.normalize_salt_form(name)
                  matches an existing ingredient's normalized name (strips
                  salt-form suffixes: hydrochloride, HCl, sodium, sulfate,
                  maleate, besylate, tartrate).
  4. inn_usan   — matches an IngredientAlias row with tier=INN_USAN, the
                  hand-verified INN/USAN divergence map
                  (data/inn_usan_map.csv, e.g. paracetamol/acetaminophen).
  5. curated    — matches an IngredientAlias row with tier=CURATED, the
                  open-ended hand-curated data/aliases.csv.

inn_usan sits before curated because it's a narrower, individually-
verified source (each row confirmed against loaded RxNorm data where
possible, with a citable rxcui) rather than a catch-all.

NEVER fuzzy. Every tier above is a deterministic, exact-string-after-a-
fixed-transform match — there is no similarity score, no threshold, no
"close enough". A name that resolves via none of the five tiers becomes a
brand NEW ingredient row (get_or_create), not a guess at an existing one.
Silently merging two different real ingredients because their names looked
similar is a worse failure mode for a safety tool than under-merging (which
just means an interaction check is missed for that one spelling until an
alias is added) — see coverage reporting in scripts/coverage_report.py for
surfacing exactly which names are under-merged so a human can fix it via
data/aliases.csv.

Every resolution is counted per-tier and logged (log_summary()) so a loader
run makes it obvious which tier is doing the work.
"""

import logging
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingest.normalization import normalize_salt_form
from app.models.enums import AliasTier
from app.models.ingredient import Ingredient
from app.models.ingredient_alias import IngredientAlias

logger = logging.getLogger(__name__)

RESOLUTION_TIERS = ("exact", "sy", "normalized", "inn_usan", "curated", "created")


class IngredientResolver:
    def __init__(self, db: Session):
        self.db = db
        self._by_id: dict[int, Ingredient] = {}
        self._exact: dict[str, Ingredient] = {}
        self._normalized: dict[str, Ingredient] = {}
        self._sy_alias: dict[str, Ingredient] = {}
        self._inn_usan_alias: dict[str, Ingredient] = {}
        self._curated_alias: dict[str, Ingredient] = {}
        self.tier_counts: Counter[str] = Counter()
        self.created_count = 0  # kept for IngestResult compatibility

    def warm(self) -> None:
        for ingredient in self.db.execute(select(Ingredient)).scalars():
            self._index_ingredient(ingredient)
        for alias in self.db.execute(select(IngredientAlias)).scalars():
            self._index_alias_row(alias)

    def _index_ingredient(self, ingredient: Ingredient) -> None:
        self._by_id[ingredient.id] = ingredient
        if ingredient.deprecated:
            # Still trackable via _by_id (get_by_id, find_by_rxcui,
            # find_deprecated_ingredients) but invisible to exact/
            # normalized matching — see deprecate() below.
            return
        self._exact[ingredient.name.lower()] = ingredient
        norm = normalize_salt_form(ingredient.name)
        if norm:
            # First writer wins — if two canonical ingredients normalize to
            # the same string (rare), later ones just won't get a
            # "normalized" shortcut; they're still reachable via "exact".
            self._normalized.setdefault(norm, ingredient)

    def _index_alias_row(self, alias: IngredientAlias) -> None:
        target = self._by_id.get(alias.ingredient_id)
        if target is None:
            return
        self.register_alias(alias.alias_name, target, AliasTier(alias.tier))

    def get_by_id(self, ingredient_id: int) -> Ingredient | None:
        return self._by_id.get(ingredient_id)

    def find_by_rxcui(self, rxcui: str) -> Ingredient | None:
        """Linear scan — fine for occasional lookups (e.g.
        scripts/propose_aliases.py); not used in any hot ingest path."""
        for ingredient in self._by_id.values():
            if ingredient.rxcui == rxcui:
                return ingredient
        return None

    @property
    def known_ingredient_count(self) -> int:
        return len(self._by_id)

    @property
    def known_alias_count(self) -> int:
        return len(self._sy_alias) + len(self._inn_usan_alias) + len(self._curated_alias)

    def _bucket_for(self, tier: AliasTier) -> dict[str, Ingredient]:
        if tier == AliasTier.SY:
            return self._sy_alias
        if tier == AliasTier.INN_USAN:
            return self._inn_usan_alias
        return self._curated_alias

    def deprecate(self, ingredient: Ingredient) -> None:
        """Marks `ingredient` deprecated and removes it from exact/
        normalized matching for the rest of this run. The row itself is
        NOT deleted — existing Interaction/ProductIngredient rows
        referencing it keep working, preserving history — it just stops
        being reachable as a fresh resolution target.

        Only called from app.ingest.alias_prepass, and only for the
        inn_usan/curated tiers attaching to a pre-existing orphan (an
        ingredient found via plain "exact" match, not sy/normalized —
        deliberately not deprecating for those, see that module).
        `ingredient` must already be a session-attached ORM object (e.g.
        from warm()'s query) — setting .deprecated here is enough; the
        caller's next commit() persists it, no separate UPDATE needed.
        """
        ingredient.deprecated = True
        key = ingredient.name.lower()
        if self._exact.get(key) is ingredient:
            del self._exact[key]
        norm = normalize_salt_form(ingredient.name)
        if norm and self._normalized.get(norm) is ingredient:
            del self._normalized[norm]
        logger.info(
            "Deprecated ingredient #%d (%r) — its exact name no longer resolves; "
            "an inn_usan/curated alias now points elsewhere for it",
            ingredient.id,
            ingredient.name,
        )

    def register_alias(self, alias_name: str, ingredient: Ingredient, tier: AliasTier) -> None:
        """Update the in-memory index only — callers (app.ingest.alias_prepass)
        own writing the actual IngredientAlias row to the DB. Split this way
        so a bulk loader can batch its DB inserts while still keeping
        resolution correct for the rest of the same run."""
        self._bucket_for(tier)[alias_name.strip().lower()] = ingredient

    def resolve(self, raw_name: str) -> tuple[Ingredient | None, str]:
        name = " ".join(raw_name.strip().split())
        key = name.lower()

        hit = self._exact.get(key)
        if hit is not None:
            return hit, "exact"

        hit = self._sy_alias.get(key)
        if hit is not None:
            return hit, "sy"

        norm_key = normalize_salt_form(name)
        if norm_key:
            hit = self._normalized.get(norm_key)
            if hit is not None:
                return hit, "normalized"

        hit = self._inn_usan_alias.get(key)
        if hit is not None:
            return hit, "inn_usan"

        hit = self._curated_alias.get(key)
        if hit is not None:
            return hit, "curated"

        return None, "unresolved"

    def get_or_create(self, raw_name: str) -> Ingredient:
        name = " ".join(raw_name.strip().split())
        ingredient, tier = self.resolve(name)
        if ingredient is not None:
            self.tier_counts[tier] += 1
            logger.debug("resolved %r via %s -> ingredient #%d (%s)", name, tier, ingredient.id, ingredient.name)
            return ingredient

        ingredient = Ingredient(name=name)
        self.db.add(ingredient)
        self.db.flush()
        self._index_ingredient(ingredient)
        self.tier_counts["created"] += 1
        self.created_count += 1
        logger.debug("resolved %r via created -> ingredient #%d", name, ingredient.id)
        return ingredient

    def get_or_create_canonical(self, name: str, rxcui: str | None = None) -> Ingredient:
        """For app.ingest.alias_prepass only: load an RxNorm IN/PIN/MIN
        concept as a canonical ingredient, backfilling rxcui if it was
        missing. Matches on exact name only (not SY/normalized/curated) —
        a canonical load must not accidentally attach itself to some other
        ingredient via an alias match; it defines identity, it doesn't look
        it up loosely.
        """
        name = " ".join(name.strip().split())
        key = name.lower()
        existing = self._exact.get(key)
        if existing is not None:
            if rxcui and not existing.rxcui:
                existing.rxcui = rxcui
            self.tier_counts["exact"] += 1
            return existing

        ingredient = Ingredient(name=name, rxcui=rxcui)
        self.db.add(ingredient)
        self.db.flush()
        self._index_ingredient(ingredient)
        self.tier_counts["created"] += 1
        self.created_count += 1
        return ingredient

    def log_summary(self, label: str = "") -> None:
        total = sum(self.tier_counts.values())
        prefix = f"[{label}] " if label else ""
        breakdown = ", ".join(f"{tier}={self.tier_counts.get(tier, 0)}" for tier in RESOLUTION_TIERS)
        logger.info("%sIngredientResolver: %d resolutions — %s", prefix, total, breakdown)
