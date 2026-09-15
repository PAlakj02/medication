"""Input shape for the LLM layer.

Deliberately does NOT import anything from app.findings — that is the
architectural boundary: this module must not know how a Finding was
computed, and app.findings must never import this package. The API layer
(app/api/routers/analyze.py) is the composition root that reads a
app.findings.models.Finding and builds one of these from it.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ExplanationRequest:
    ingredient_a_name: str
    ingredient_b_name: str
    severity: str
    mechanism: str
    source_name: str
    source_text: str
