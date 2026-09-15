"""STUB — RxNav (NLM RxNorm REST API), source of US ingredient/rxcui data.
https://lhncbc.nlm.nih.gov/RxNav/APIs/RxNormAPIs.html

TODO(you):
  - Pull ingredient names + RxCUIs (e.g. /REST/rxcui, /REST/rxcui/{rxcui}/properties).
  - Upsert into `ingredient` keyed on rxcui.
  - Consider also pulling RxNorm's brand-name (SBD/SCD) relationships to seed
    `product` / `product_ingredient` for US market products.
  - Populate name_embedding at insert/update time if this is the loader
    responsible for it (decide once, keep consistent — see linking/resolver.py).
"""

from sqlalchemy.orm import Session

from app.ingest.base import IngestResult, SourceLoader


class RxNavLoader(SourceLoader):
    source_name = "RxNav"

    def load(self, db: Session) -> IngestResult:
        raise NotImplementedError("RxNavLoader.load is a stub")
