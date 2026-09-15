"""STUB — Jan Aushadhi (PMBJP, India's generic-medicine scheme), source of
low-cost generic-equivalent product data for the IN market.
https://janaushadhi.gov.in/

TODO(you):
  - PMBJP publishes a product price list (generic name, strength, pack size,
    MRP) — no interaction/timing data, purely product/pricing.
  - Upsert into `product` (market=Market.IN, otc_status likely OTC/RX per
    item — check the source list) and `product_ingredient`.
  - This is the loader most directly useful to alternatives/ranking.py for
    India-market "generic equivalent, lower cost" substitute suggestions.
"""

from sqlalchemy.orm import Session

from app.ingest.base import IngestResult, SourceLoader


class JanAushadhiLoader(SourceLoader):
    source_name = "Jan Aushadhi"

    def load(self, db: Session) -> IngestResult:
        raise NotImplementedError("JanAushadhiLoader.load is a stub")
