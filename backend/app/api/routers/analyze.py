"""POST /api/analyze — composition root for the whole pipeline.

This is the ONE place allowed to import from both app.findings and
app.explain (and app.linking, app.alternatives). Each of those packages
stays decoupled from its siblings; this router is what wires them together
per request.
"""

import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependency import require_authenticated_user
from app.auth.firebase import AuthenticatedUser
from app.db import get_db
from app.explain.llm import explain_finding
from app.explain.models import ExplanationRequest
from app.findings.engine import find_interactions
from app.findings.models import Finding
from app.findings.repository import load_interaction_rules, load_timing_rules
from app.findings.timing import find_timing_findings
from app.linking.resolver import LinkResult, resolve
from app.models.ingredient import Ingredient
from app.models.product_ingredient import ProductIngredient
from app.schemas.analyze import (
    AnalyzeRequest,
    AnalyzeResponse,
    DetectedItem,
    InteractionWarning,
    MedicationInfo,
    SuggestedMedication,
    TimingGuidance,
)
from app.schemas.common import MedicationRef, SourceCitation

router = APIRouter(prefix="/api", tags=["analyze"])

_SPLIT_RE = re.compile(r"[,\n;]+")


def _tokenize(raw: str) -> list[str]:
    """Interim placeholder mirroring the frontend mock's parseInput()
    (pill-check repo, src/lib/med-data.ts) — split on comma/semicolon/
    newline. TODO(you): replace with real NLP segmentation once linking/
    needs to handle free-text/OCR input that doesn't arrive pre-delimited.
    """
    return [t.strip() for t in _SPLIT_RE.split(raw) if t.strip()]


_MAX_DISPLAYED_STRENGTHS = 8


def _distinct_salts(db: Session, ingredient: Ingredient) -> list[str]:
    rows = (
        db.execute(
            select(ProductIngredient).where(ProductIngredient.ingredient_id == ingredient.id)
        )
        .scalars()
        .all()
    )
    # Real product data has dozens of near-duplicate (strength, unit) rows
    # per ingredient (unit casing like "mg" vs "MG", and genuinely distinct
    # marketed strengths). Dedup case-insensitively on unit, then present a
    # short, sorted list rather than every raw row — this is display data,
    # not a query result the caller should have to filter itself.
    seen: dict[tuple[float, str], str] = {}
    for row in rows:
        if row.strength_mg is None or not row.unit:
            continue
        unit_normalized = row.unit.strip().lower()
        key = (float(row.strength_mg), unit_normalized)
        if key not in seen:
            # Fixed-point formatting, then strip trailing zeros — Decimal.normalize()
            # would switch to exponential notation for whole numbers (e.g. "1E+2").
            value_str = f"{row.strength_mg:f}"
            if "." in value_str:
                value_str = value_str.rstrip("0").rstrip(".")
            seen[key] = f"{value_str}{unit_normalized}"
    ordered = [label for _, label in sorted(seen.items(), key=lambda kv: kv[0])]
    return ordered[:_MAX_DISPLAYED_STRENGTHS] or [ingredient.name]


def _load_medication_info(db: Session, ingredient_id: int) -> MedicationInfo:
    ingredient = db.get(Ingredient, ingredient_id)
    if ingredient is None:
        # linking/ resolved to an id that no longer exists — a data
        # integrity problem, not a user input problem.
        raise HTTPException(status_code=500, detail=f"Linked ingredient {ingredient_id} not found.")

    return MedicationInfo(
        id=str(ingredient.id),
        name=ingredient.name,
        salts=_distinct_salts(db, ingredient),
        # GAP: the given schema has no human-readable drug-class field or
        # table (only atc_code/rxcui). Falling back to the raw ATC code.
        # TODO(you): either add ingredient.drug_class, or an atc_code ->
        # label lookup, to satisfy docs/api-contract.md's MedicationInfo.drugClass
        # with something a non-clinician can read (e.g. "NSAID").
        drugClass=ingredient.atc_code or "Unclassified",
        # GAP: same-ingredient alternatives (app.alternatives.ranking) need
        # product data ingest/ hasn't loaded yet, AND the given schema has no
        # source_id on product/product_ingredient to satisfy
        # AlternativeSuggestion.citation (required per docs/api-contract.md).
        # Left empty rather than fabricating a citation — see accompanying
        # message for the open schema question this raises.
        alternatives=[],
    )


def _synthesize_title(finding: Finding) -> str:
    """The given DB schema stores only `mechanism` on `interaction`, not a
    separate short title. docs/api-contract.md's InteractionWarning.title
    (e.g. mock data's punchy "Major bleeding risk") is synthesized here
    instead of stored. TODO(you): add a `title` column to `interaction` if a
    curated short title matters more than this generated one.
    """
    if finding.severity_ungraded:
        prefix = "Ungraded interaction"
    else:
        prefix = f"{finding.severity.value.capitalize()}-severity interaction"
    return f"{prefix}: {finding.ingredient_a.name} + {finding.ingredient_b.name}"


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(
    request: AnalyzeRequest,
    db: Session = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_authenticated_user),
) -> AnalyzeResponse:
    tokens = _tokenize(request.input)

    items: list[DetectedItem] = []
    seen_keys: set[str] = set()
    recognized_ingredient_ids: list[int] = []

    for token in tokens:
        try:
            link: LinkResult = resolve(token, db)
        except NotImplementedError as exc:
            raise HTTPException(
                status_code=501,
                detail=(
                    "Ingredient linking is not implemented yet "
                    "(app.linking.resolver.resolve is a stub)."
                ),
            ) from exc

        key = f"id:{link.matched.ingredient_id}" if link.matched else f"raw:{token.strip().lower()}"
        if key in seen_keys:
            continue
        seen_keys.add(key)

        if link.matched is not None:
            recognized_ingredient_ids.append(link.matched.ingredient_id)
            items.append(
                DetectedItem(
                    input=token,
                    recognized=True,
                    medication=_load_medication_info(db, link.matched.ingredient_id),
                    suggestions=None,
                )
            )
        else:
            suggestions = [
                SuggestedMedication(
                    medicationId=str(c.ingredient_id),
                    name=c.ingredient_name,
                    confidence=c.confidence,
                )
                for c in link.candidates
            ] or None
            items.append(
                DetectedItem(input=token, recognized=False, medication=None, suggestions=suggestions)
            )

    rules = load_interaction_rules(db, recognized_ingredient_ids)
    findings = find_interactions(recognized_ingredient_ids, rules)

    interactions = [
        InteractionWarning(
            medications=(
                MedicationRef(id=str(f.ingredient_a.id), name=f.ingredient_a.name),
                MedicationRef(id=str(f.ingredient_b.id), name=f.ingredient_b.name),
            ),
            severity=f.severity.value if f.severity is not None else None,
            severityUngraded=f.severity_ungraded,
            title=_synthesize_title(f),
            explanation=explain_finding(
                ExplanationRequest(
                    ingredient_a_name=f.ingredient_a.name,
                    ingredient_b_name=f.ingredient_b.name,
                    severity=f.severity.value if f.severity is not None else "ungraded",
                    mechanism=f.mechanism,
                    source_name=f.source.name,
                    source_text=f.source_text,
                )
            ),
            citation=SourceCitation(
                source=f.source.name, reference=f.source.reference, url=f.source.url
            ),
        )
        for f in findings
    ]

    timing_rules = load_timing_rules(db, recognized_ingredient_ids)
    timing_findings = find_timing_findings(recognized_ingredient_ids, timing_rules)
    timing = [
        TimingGuidance(
            medication=MedicationRef(id=str(t.ingredient.id), name=t.ingredient.name),
            ruleType=t.rule_type,
            offsetMinutes=t.offset_minutes,
            note=t.note,
            citation=SourceCitation(source=t.source.name, reference=t.source.reference, url=t.source.url),
        )
        for t in timing_findings
    ]

    return AnalyzeResponse(items=items, interactions=interactions, timing=timing)
