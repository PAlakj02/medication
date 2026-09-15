from pydantic import BaseModel

from app.models.enums import Severity

__all__ = ["Severity", "SourceCitation", "MedicationRef"]


class SourceCitation(BaseModel):
    """Required on every clinical finding — see docs/api-contract.md
    (pill-check repo) §"Decisions confirmed" item 3."""

    source: str
    reference: str
    url: str | None = None


class MedicationRef(BaseModel):
    id: str
    name: str
