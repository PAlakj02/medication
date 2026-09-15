"""Same-ingredient substitute ranking.

NOTE on scope, flagged rather than silently assumed: this module ranks
*other products containing the same canonical ingredient* (e.g. a cheaper
generic vs. the branded product the user typed) — a purely mechanical,
deterministic lookup, same spirit as findings/ (rules over DB rows, no LLM).

That is narrower than what the pill-check frontend's mock data currently
calls "alternatives" (e.g. suggesting Acetaminophen instead of Aspirin —
a *different* ingredient, recommended for a different safety profile). This
scaffold implements only the same-ingredient case per the module layout you
specified ("alternatives/ — same-ingredient substitute ranking"). Reconciling
that with the frontend's current different-ingredient suggestions is a
product decision, not made here — see the accompanying message.

Pure function over plain data, like findings/ — no Session, no LLM.
"""

from dataclasses import dataclass
from enum import Enum


class Market(str, Enum):
    US = "US"
    IN = "IN"


class OtcStatus(str, Enum):
    OTC = "OTC"
    RX = "RX"


@dataclass(frozen=True)
class ProductCandidate:
    product_id: int
    name: str
    market: Market
    # Nullable: bulk sources (RxNorm, the Indian medicine dataset) don't
    # reliably carry OTC/Rx status — see app.models.product.Product.otc_status.
    otc_status: OtcStatus | None
    manufacturer: str | None


@dataclass(frozen=True)
class RankedAlternative:
    product_id: int
    name: str
    rank_reason: str


def rank_alternatives(
    source_product_id: int,
    candidates: list[ProductCandidate],
    preferred_market: Market | None = None,
) -> list[RankedAlternative]:
    """Rank other products sharing an ingredient with `source_product_id`.

    `candidates` is the caller-loaded set of other products containing the
    same ingredient (join through product_ingredient — the DB query itself
    belongs in a repository module alongside this, analogous to
    findings/repository.py, once ingest/ has real product data to query).

    Ranking today is a simple deterministic preference order:
      1. Same market as the input, if `preferred_market` given.
      2. OTC before Rx before unknown (a safer default suggestion —
         swapping to a prescription-only alternative isn't something to
         surface as a casual "alternative"; unknown status is treated as
         worse than a confirmed Rx, since it's an even weaker guarantee).
      3. Alphabetical, for stability.
    This is intentionally simple and reviewable; replace with a real cost/
    availability-aware ranking once ingest/ provides pricing data (e.g. from
    Jan Aushadhi for the IN market).
    """
    others = [c for c in candidates if c.product_id != source_product_id]

    def otc_rank(status: OtcStatus | None) -> int:
        if status == OtcStatus.OTC:
            return 0
        if status == OtcStatus.RX:
            return 1
        return 2  # unknown

    def sort_key(c: ProductCandidate) -> tuple:
        same_market = 0 if (preferred_market and c.market == preferred_market) else 1
        return (same_market, otc_rank(c.otc_status), c.name.lower())

    ranked = sorted(others, key=sort_key)

    return [
        RankedAlternative(
            product_id=c.product_id,
            name=c.name,
            rank_reason=(
                f"Same active ingredient, "
                f"{c.otc_status.value if c.otc_status else 'OTC/Rx status unknown'} in {c.market.value}."
            ),
        )
        for c in ranked
    ]
