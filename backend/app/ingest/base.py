"""Shared shape for every ingest/ source loader. Each concrete loader in this
package (rxnav.py, dailymed.py, cdsco.py, jan_aushadhi.py) is a stub
implementing this protocol — real HTTP calls / file parsing / upserts are
TODOs for you.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class IngestResult:
    source_name: str
    ingredients_created: int
    ingredients_updated: int
    products_created: int
    products_updated: int
    interactions_created: int
    timing_rules_created: int
    errors: list[str]


class SourceLoader(ABC):
    """One loader per upstream data source. `load()` should be idempotent —
    safe to re-run against a DB that already has some/all of this source's
    rows (upsert by natural key, e.g. rxcui or atc_code, not blind insert).
    """

    #: Human-readable name, stored on app.models.source.Source.name for every
    #: row this loader creates — this is what ends up in API citations.
    source_name: str

    @abstractmethod
    def load(self, db: Session) -> IngestResult:
        """Fetch from the upstream source and upsert into the DB. Must
        commit (or leave commit to the caller — pick one convention and
        document it here once decided) and return a summary for logging/
        monitoring. Should not raise on a single bad record; collect it into
        IngestResult.errors and continue.
        """
        raise NotImplementedError
