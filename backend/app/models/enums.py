import enum

from sqlalchemy import Enum as SAEnum


def pg_enum(enum_cls: type[enum.Enum], name: str) -> SAEnum:
    """SQLAlchemy's Enum column type defaults to persisting the Python
    member's `.name` (e.g. "HIGH"), not `.value` (e.g. "high"). Every enum
    below is a (str, Enum) specifically so the stored/API-facing value is
    the lowercase string — without values_callable here, SQLAlchemy sends
    "HIGH" to a Postgres enum type whose actual values are ("high",
    "moderate", "low"), which fails at insert time, not at import time (see
    the migrations, which spell out the real DB-side values by hand).
    """
    return SAEnum(enum_cls, name=name, values_callable=lambda obj: [e.value for e in obj])


class Severity(str, enum.Enum):
    """Must stay exactly these three values and this name — the frontend
    contract (docs/api-contract.md in the pill-check repo) switches on this
    exact enum with this precedence order (high > moderate > low)."""

    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"


class Market(str, enum.Enum):
    US = "US"
    IN = "IN"


class OtcStatus(str, enum.Enum):
    OTC = "OTC"
    RX = "RX"


class TimingRuleType(str, enum.Enum):
    """Non-exhaustive — extend as ingest/ encounters more rule shapes.
    `note` on TimingRule always carries the free-text detail regardless of
    which type is picked, so adding a new type here is low-risk.
    """

    SEPARATE_FROM = "separate_from"
    TAKE_WITH_FOOD = "take_with_food"
    TAKE_ON_EMPTY_STOMACH = "take_on_empty_stomach"
    AVOID_ALCOHOL = "avoid_alcohol"
    MONITOR = "monitor"
    OTHER = "other"


class AliasTier(str, enum.Enum):
    """Matches app.ingest.ingredient_resolver's resolution order: exact →
    SY → normalized → inn_usan → curated. "exact" and "normalized" are NOT
    tiers stored here — they're computed live against Ingredient.name, not
    materialized rows. The three that ARE materialized rows in
    ingredient_alias: RxNorm SY synonyms, the hand-verified INN/USAN map
    (data/inn_usan_map.csv), and the open-ended hand-curated
    data/aliases.csv — checked in that order because inn_usan is a
    narrower, individually-verified (has an rxcui, where confirmable)
    source, while curated is a catch-all for everything else.
    """

    SY = "sy"
    INN_USAN = "inn_usan"
    CURATED = "curated"
