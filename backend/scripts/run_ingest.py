"""Run all ingest/ loaders in order: the alias pre-pass FIRST (it must load
canonical RxNorm ingredients + SY synonyms + curated aliases before anyone
else resolves names against them), then the three independent sources.

Usage: uv run python scripts/run_ingest.py

Paths below point at your local raw-data downloads (siblings of the
pill-check/ and backend/ repos, not tracked in this repo) — adjust if yours
live elsewhere.
"""

import logging
from pathlib import Path

from app.db import SessionLocal
from app.ingest.ddinter import DDInterLoader
from app.ingest.alias_prepass import AliasPrepassLoader
from app.ingest.indian_medicine import IndianMedicineLoader
from app.ingest.rxnorm_bulk import RxNormBulkLoader

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = BACKEND_ROOT.parent  # medication/, sibling of backend/ and pill-check/

RRF_PATH = DATA_ROOT / "RxNorm_full_prescribe_09082026" / "rrf" / "RXNCONSO.RRF"
DDINTER_DIR = DATA_ROOT / "ddinter"
INDIAN_MEDICINE_CSV = DATA_ROOT / "indian_medicine_data.csv"
CURATED_ALIASES_CSV = BACKEND_ROOT / "data" / "aliases.csv"


def main() -> None:
    db = SessionLocal()
    try:
        loaders = [
            AliasPrepassLoader(rrf_path=RRF_PATH, curated_csv_path=CURATED_ALIASES_CSV),
            DDInterLoader(data_dir=DDINTER_DIR),
            RxNormBulkLoader(rrf_path=RRF_PATH),
            IndianMedicineLoader(csv_path=INDIAN_MEDICINE_CSV),
        ]
        for loader in loaders:
            result = loader.load(db)
            print(f"\n=== {result.source_name} ===")
            print(f"ingredients_created={result.ingredients_created}")
            print(f"products_created={result.products_created}")
            print(f"interactions_created={result.interactions_created}")
            print(f"timing_rules_created={result.timing_rules_created}")
            if result.errors:
                print(f"errors ({len(result.errors)}):")
                for err in result.errors[:10]:
                    print(f"  - {err}")
                if len(result.errors) > 10:
                    print(f"  ... and {len(result.errors) - 10} more")
    finally:
        db.close()


if __name__ == "__main__":
    main()
