from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, sourced from environment variables / .env.

    See .env.example for the full list with descriptions.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = (
        "postgresql+psycopg://pillcheck:pillcheck@localhost:5432/pillcheck"
    )

    # Dimension of the vectors stored in ingredient.name_embedding. Must match
    # whatever embedding model linking/ ends up calling. 1536 is a placeholder
    # matching common OpenAI/Anthropic-adjacent embedding sizes — revisit once
    # linking/ picks a concrete embedding model.
    embedding_dim: int = 1536

    # Below the abstain threshold, linking/resolver treats a match as "not
    # confident enough" and reports it as unrecognized-with-suggestions rather
    # than an accepted match. Tune once real matching is implemented.
    linking_abstain_threshold: float = 0.55

    # Groq (OpenAI-compatible chat completions API) — used by app.explain.llm
    # to render finding prose. Falls back to a deterministic template
    # (finding.mechanism verbatim) when unset, so the API stays runnable
    # without a live key.
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-120b"

    # Login gate only — app.auth.firebase verifies ID tokens against Google's
    # public certs using just the project id (no service account secret needed,
    # since we never call the Admin API or store any per-user data).
    firebase_project_id: str = "medicine-app-aa799"

    # Vite picks the first free port from 8080 up when 8080 is taken, so the
    # dev-server origin isn't fixed — allow the common range rather than one guess.
    cors_allow_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
        "http://localhost:8081",
        "http://localhost:8082",
        "https://medication-one.vercel.app",
    ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
