"""STUB — CDSCO (Central Drugs Standard Control Organisation), India's
national drug regulator; source of IN market product/approval data.
https://cdsco.gov.in/

TODO(you):
  - CDSCO does not expose a clean public REST API like RxNav — this likely
    means scraping published approval lists / notifications, or licensing a
    third-party feed. Confirm data access approach before building this out.
  - Upsert into `product` with market=Market.IN.
  - Map to canonical `ingredient` rows by name (fuzzy match against existing
    ingredients, e.g. via linking/resolver.py's approach) since CDSCO
    listings are unlikely to carry RxCUI/ATC codes directly.
"""

from sqlalchemy.orm import Session

from app.ingest.base import IngestResult, SourceLoader


class CdscoLoader(SourceLoader):
    source_name = "CDSCO"

    def load(self, db: Session) -> IngestResult:
        raise NotImplementedError("CdscoLoader.load is a stub")
