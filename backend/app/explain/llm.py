"""The LLM layer: prose rendering ONLY.

ARCHITECTURAL RULE (do not violate): this module renders an explanation for
a finding that already exists — it never decides whether an interaction
exists, never invents a severity, never invents a mechanism. Its only inputs
are a finding's structured fields plus its source_text (the "RAG" context —
retrieval is trivial here because the grounding passage is already attached
to the interaction/timing_rule row; there is no vector search over an
external corpus in this module).

This module must never import from app.findings. It receives an
ExplanationRequest (app.explain.models) built by the API layer, which is
free to import both app.findings and app.explain since it's the composition
root, not part of either pure layer.

Provider is Groq (see app.config.Settings — groq_api_key / groq_model). If no
key is configured, or the call fails for any reason, explain_finding() falls
back to a deterministic template so the API is runnable end-to-end without a
live LLM dependency. The template output already contains everything the
mechanism/source_text fields carry, so it's a legitimate (if unpolished)
explanation, not a placeholder string.
"""

import requests

from app.config import get_settings
from app.explain.models import ExplanationRequest

_GROQ_CHAT_COMPLETIONS_URL = "https://api.groq.com/openai/v1/chat/completions"
_REQUEST_TIMEOUT_SECONDS = 10


def _call_llm(prompt: str) -> str | None:
    """Calls Groq's chat completions API. Never raises — a down/misconfigured
    LLM provider must not break a clinical warning response, so any failure
    (network, auth, malformed response) returns None and explain_finding()
    falls back to the deterministic template instead.
    """
    settings = get_settings()
    if not settings.groq_api_key:
        return None

    try:
        response = requests.post(
            _GROQ_CHAT_COMPLETIONS_URL,
            headers={
                "Authorization": f"Bearer {settings.groq_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.groq_model,
                "messages": [{"role": "user", "content": prompt}],
                # Low temperature: this text renders a clinical finding, not
                # creative writing — stay close to the given mechanism/source.
                "temperature": 0.2,
                "max_tokens": 300,
            },
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return content.strip() or None
    except (requests.RequestException, KeyError, IndexError, ValueError):
        return None


def _build_prompt(request: ExplanationRequest) -> str:
    return (
        "Explain the following medication interaction finding in plain,"
        " patient-facing language. Use ONLY the mechanism and source excerpt"
        " given below — do not introduce any clinical claim that isn't"
        " already stated in them.\n\n"
        f"Ingredients: {request.ingredient_a_name} + {request.ingredient_b_name}\n"
        f"Severity: {request.severity}\n"
        f"Mechanism: {request.mechanism}\n"
        f"Source ({request.source_name}): \"{request.source_text}\"\n"
    )


def _template_fallback(request: ExplanationRequest) -> str:
    return request.mechanism


def explain_finding(request: ExplanationRequest) -> str:
    """Render a human-readable explanation for one finding.

    Never raises on LLM failure — always returns usable text, since a
    clinical warning must render even if the LLM provider is down.
    """
    prompt = _build_prompt(request)
    rendered = _call_llm(prompt)
    return rendered if rendered is not None else _template_fallback(request)
