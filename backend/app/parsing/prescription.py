"""Orchestrates one prescription line: strips route/dose/frequency/duration
via app.parsing.dosage's extractors, leaving a drug-name candidate. Pure —
no DB. Resolving that candidate against the gazetteer is a separate step,
done by app.linking.resolver (which calls into this module).

Order matters: route/form prefix is anchored at the START of the string, so
it must be stripped first or a later match could shift what "start" means.
Dose, then frequency, then duration — chosen because dose almost always
sits closest to the drug name in real prescriptions ("Paracetamol 500mg
BD"), so removing it first leaves the cleanest text for the next extractor
to search. Order among dose/frequency/duration rarely matters in practice
since each pattern is narrow enough not to overlap the others.
"""

from dataclasses import dataclass

from app.parsing.dosage import (
    DoseAmount,
    Duration,
    Frequency,
    extract_dose,
    extract_duration,
    extract_frequency,
    extract_route_form,
)


@dataclass(frozen=True)
class ParsedPrescriptionLine:
    drug_candidate: str
    """Whatever text remains after stripping route/dose/frequency/duration
    — NOT yet resolved against the gazetteer. Empty string if the whole
    line was consumed by those (e.g. a line that was only a dosage
    instruction with no drug name, which shouldn't happen in practice but
    isn't assumed away)."""
    dose: DoseAmount | None
    frequency: Frequency | None
    duration: Duration | None
    route_form: str | None
    raw_text: str


def parse_prescription_line(raw_text: str) -> ParsedPrescriptionLine:
    text = raw_text.strip()

    route_form, text = extract_route_form(text)
    dose, text = extract_dose(text)
    frequency, text = extract_frequency(text)
    duration, text = extract_duration(text)

    return ParsedPrescriptionLine(
        drug_candidate=text.strip(),
        dose=dose,
        frequency=frequency,
        duration=duration,
        route_form=route_form,
        raw_text=raw_text,
    )
