"""Text -> ingredient resolution — the gazetteer half of Module 1. The
regex half (dose/frequency/duration/route-form extraction) is
app.parsing.dosage, called from here to strip those spans out of the input
BEFORE attempting a gazetteer match, so "Paracetamol 500mg BD" resolves via
its drug-name portion ("Paracetamol") rather than failing to match the
whole string.

Gazetteer match = app.ingest.ingredient_resolver.IngredientResolver, used
read-only here (warm() + resolve(), never get_or_create — this module must
never mint new ingredients from user-typed text; that would let a typo
silently become a "canonical" entry). Reuses the exact/SY/normalized/
inn_usan/curated tiers built and tested for ingest — not a second matching
mechanism, the same one.

Scope of this initial version, deliberately not done yet (see
docs/api-contract.md's linking section and Module 1's plan):
  - No fuzzy/typo-tolerant matching (pg_trgm trigram similarity or
    pgvector semantic search against ingredient.name_embedding). A name
    that doesn't hit the gazetteer's exact-after-transform tiers abstains
    (matched=None) rather than guessing — silently matching the wrong
    ingredient is worse than surfacing "not recognized". `candidates`
    stays empty for the same reason: real ranked suggestions need the
    fuzzy pass this version doesn't have.
  - ABSTAIN_THRESHOLD (a confidence cutoff) is therefore unused right now
    — gazetteer tier matches are exact-after-transform, not probabilistic,
    so there's no fractional confidence to threshold against yet. It'll
    matter once the fuzzy pass above is built.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import get_settings
from app.ingest.ingredient_resolver import IngredientResolver
from app.parsing.prescription import parse_prescription_line

ABSTAIN_THRESHOLD = get_settings().linking_abstain_threshold


@dataclass(frozen=True)
class LinkCandidate:
    ingredient_id: int
    ingredient_name: str
    confidence: float


@dataclass(frozen=True)
class LinkResult:
    input_text: str
    matched: LinkCandidate | None
    """None means: no candidate cleared ABSTAIN_THRESHOLD."""
    candidates: list[LinkCandidate]
    """Ranked candidates considered, for surfacing as suggestions — includes
    `matched` (if any) plus runner-ups, highest confidence first."""


def resolve(token: str, db: Session) -> LinkResult:
    """Resolve one already-segmented input token to an ingredient.

    Strips dose/frequency/duration/route-form via app.parsing.dosage first
    (a token from a real prescription list, e.g. "Paracetamol 500mg BD",
    otherwise fails every gazetteer tier as a whole string), then matches
    whatever text remains against the gazetteer. Never raises for "no
    match found" — returns a LinkResult with matched=None instead.
    """
    parsed_line = parse_prescription_line(token)
    drug_candidate = parsed_line.drug_candidate

    if not drug_candidate:
        return LinkResult(input_text=token, matched=None, candidates=[])

    resolver = IngredientResolver(db)
    resolver.warm()
    ingredient, tier = resolver.resolve(drug_candidate)

    if ingredient is None:
        return LinkResult(input_text=token, matched=None, candidates=[])

    # Gazetteer tiers are exact-after-a-fixed-transform, not probabilistic
    # — every hit is treated as fully confident. See module docstring for
    # why there's no fractional score yet.
    candidate = LinkCandidate(ingredient_id=ingredient.id, ingredient_name=ingredient.name, confidence=1.0)
    return LinkResult(input_text=token, matched=candidate, candidates=[candidate])
