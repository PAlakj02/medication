"""Pydantic models matching docs/api-contract.md (pill-check repo,
docs/api-contract.md) field-for-field. Keep these two in sync — if you
change one, change the other in the same change.
"""

from pydantic import BaseModel, Field

from app.schemas.common import MedicationRef, Severity, SourceCitation


class AnalyzeRequest(BaseModel):
    input: str = Field(..., min_length=1, description="Raw pasted/typed text, unsplit.")


class SuggestedMedication(BaseModel):
    medication_id: str = Field(..., alias="medicationId")
    name: str
    confidence: float = Field(..., ge=0, le=1)

    model_config = {"populate_by_name": True}


class AlternativeSuggestion(BaseModel):
    text: str
    citation: SourceCitation


class MedicationInfo(BaseModel):
    id: str
    name: str
    salts: list[str]
    drug_class: str = Field(..., alias="drugClass")
    alternatives: list[AlternativeSuggestion]

    model_config = {"populate_by_name": True}


class DetectedItem(BaseModel):
    input: str
    recognized: bool
    medication: MedicationInfo | None
    suggestions: list[SuggestedMedication] | None = None


class InteractionWarning(BaseModel):
    medications: tuple[MedicationRef, MedicationRef]
    # None iff severityUngraded is true — the source recorded this pair
    # without a severity grade (e.g. DDInter's "Unknown" level). Still a
    # real, sourced interaction; the frontend needs a distinct render path
    # for this (not just "severity missing"), see docs/api-contract.md.
    severity: Severity | None
    severity_ungraded: bool = Field(..., alias="severityUngraded")
    title: str
    explanation: str
    citation: SourceCitation

    model_config = {"populate_by_name": True}


class AnalyzeResponse(BaseModel):
    items: list[DetectedItem]
    interactions: list[InteractionWarning]
