"""STUB — DailyMed (NLM structured product labels), source of US
interaction/timing-rule text (drug label sections) and source_text
excerpts for citations. https://dailymed.nlm.nih.gov/dailymed/spl-resources-all-drug-labels.cfm

TODO(you):
  - Pull SPL (Structured Product Label) XML for products of interest.
  - Extract "Drug Interactions" and dosage/administration-timing sections.
  - Create one `source` row per label (name="DailyMed", url=label permalink,
    retrieved_at=fetch time), then `interaction` / `timing_rule` rows with
    `source_text` set to the verbatim excerpt supporting each rule — this is
    the grounding text explain/ uses, so keep it verbatim, not paraphrased.
"""

from sqlalchemy.orm import Session

from app.ingest.base import IngestResult, SourceLoader


class DailyMedLoader(SourceLoader):
    source_name = "DailyMed"

    def load(self, db: Session) -> IngestResult:
        raise NotImplementedError("DailyMedLoader.load is a stub")
