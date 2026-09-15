"""Pure ingredient-name normalization — the third resolution tier (after
exact and SY, before inn_usan/curated). No DB, no I/O.

Purely mechanical, two fixed transforms applied in order:
  1. Strip a trailing "(qualifier)" parenthetical, e.g. "Brimonidine
     (ophthalmic)" -> "Brimonidine", "Insulin human (isophane)" ->
     "Insulin human". Whatever is inside the parens (route of
     administration, formulation descriptor, salt-adjacent qualifier —
     RxNorm/DDInter data mixes all three under this same "Name (...)"
     shape) is dropped wholesale rather than enumerated, since the pattern
     itself — not the specific word inside — is the reliable signal.
  2. Lowercase, collapse punctuation/whitespace to single spaces, then
     strip ONE trailing salt-form suffix word if present.

NOT fuzzy matching — every step is a fixed, deterministic transform, so two
names either normalize to the same string or they don't; there is no
similarity score and no threshold. That's the whole point: it closes gaps
like "Acetylsalicylic acid" vs "aspirin" or "Brimonidine (ophthalmic)" vs
"Brimonidine" only when the difference is exactly one of these two known
shapes, and refuses everything else rather than guessing.
"""

import re

_SALT_FORMS = frozenset(
    {
        "hydrochloride",
        "hcl",
        "sodium",
        "sulfate",
        "maleate",
        "besylate",
        "tartrate",
    }
)

_TRAILING_PAREN_RE = re.compile(r"\s*\([^()]*\)\s*$")
_APOSTROPHE_RE = re.compile(r"['’]")
_PUNCT_RE = re.compile(r"[^a-z0-9\s]")
_WHITESPACE_RE = re.compile(r"\s+")


def _strip_trailing_qualifier(s: str) -> str:
    """Repeatedly strips a trailing "(...)" block — handles the rare
    doubled case "Name (a) (b)" as well as the common single one. Applied
    before lowercasing so the paren boundaries are still intact; the
    generic punctuation stripper below would otherwise turn "(topical)"
    into a bare, unremovable word "topical"."""
    while True:
        stripped = _TRAILING_PAREN_RE.sub("", s)
        if stripped == s:
            return s
        s = stripped


def normalize_salt_form(raw: str) -> str:
    s = _strip_trailing_qualifier(raw.strip())
    s = s.lower()
    # Apostrophes are deleted outright (not replaced with a space) so a
    # possessive like "St. John's Wort" collapses to "st johns wort", not
    # "st john s wort" — every other punctuation mark becomes a space.
    s = _APOSTROPHE_RE.sub("", s)
    s = _PUNCT_RE.sub(" ", s)
    s = _WHITESPACE_RE.sub(" ", s).strip()
    if not s:
        return s

    words = s.split(" ")
    if len(words) > 1 and words[-1] in _SALT_FORMS:
        words = words[:-1]
    return " ".join(words)
