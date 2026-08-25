"""Turning LanguageTool's rule metadata into our own vocabulary.

LanguageTool reports several thousand rules across a dozen categories. Three
decisions are made here, and each of them is about **not** reporting something:

1. **Misspellings are dropped.** ``app.assessment.analyzers.spelling`` already
   owns that category, and it owns it with information LanguageTool does not
   have: the curated target vocabulary for this exercise and every word
   written on the chart. LanguageTool would flag "Sylhet", "Hokkaido" and half
   the target terms. Letting it through under ``GRAMMAR`` would also relabel a
   spelling mistake as a grammar mistake and corrupt the analytics slug that
   "the mistakes this class makes most" is grouped by.

2. **Style and register matches are dropped.** LanguageTool's style rules are
   tuned for general English prose: they object to the passive voice, to long
   sentences and to hedging — which is the register academic graph description
   is *taught in*. ``word_usage`` covers register with domain knowledge instead.
   The requirement that acceptable stylistic variation is never penalised is
   not served by reporting those findings quietly; it is served by not
   reporting them.

3. **Everything unrecognised is reported at the lowest useful grade.** A rule
   this table has never seen still produces a real finding, so it is kept —
   but as ``grammar_error`` at ``LOW``, not guessed into a specific subtype
   whose analytics would then be wrong.

The subtype is an analytics key with a long life: it groups a year of class
reports, so it is derived from the rule *identifier*, which LanguageTool keeps
stable, rather than from the message, which is localised and rewritten
between releases.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.enums import IssueSeverity

#: LanguageTool ``issueType`` values whose findings belong to another analyzer.
#:
#: Not a quality judgement on the rules — a boundary. Two analyzers reporting
#: the same ground is how a result page starts contradicting itself.
FOREIGN_ISSUE_TYPES = frozenset(
    {
        "misspelling",  # the spelling analyzer, with the exemption set
        "style",  # word_usage, with the register the exercise teaches
        "register",
        "locale-violation",
    }
)

#: LanguageTool category identifiers that belong to another analyzer.
FOREIGN_CATEGORIES = frozenset({"TYPOS", "STYLE", "REDUNDANCY", "PLAIN_ENGLISH", "WIKIPEDIA"})

#: Substrings of a rule identifier that pin it to a specific subtype, in
#: priority order.
#:
#: Ordered rather than a plain mapping because identifiers overlap:
#: ``SUBJECT_VERB_AGREEMENT`` contains both "AGREEMENT" and "VERB", and the
#: first match must be the more specific one. Matched against the identifier
#: with underscores intact so "AN_" cannot match inside "MEAN_".
RULE_SUBTYPES: tuple[tuple[str, str], ...] = (
    ("SUBJECT_VERB", "subject_verb_agreement"),
    ("AGREEMENT", "subject_verb_agreement"),
    ("_AGR", "subject_verb_agreement"),
    ("PLURAL", "subject_verb_agreement"),
    ("TENSE", "verb_tense"),
    ("PAST_PART", "verb_tense"),
    ("IRREGULAR_VERB", "verb_tense"),
    ("DID_BASEFORM", "verb_tense"),
    ("A_VS_AN", "article_use"),
    ("ARTICLE", "article_use"),
    ("DT_", "article_use"),
    ("_DT", "article_use"),
    ("COMMA", "punctuation"),
    ("APOSTROPHE", "punctuation"),
    ("PUNCT", "punctuation"),
    ("SENTENCE_FRAGMENT", "sentence_structure"),
    ("RUN_ON", "sentence_structure"),
    ("SENT_START", "sentence_structure"),
    ("PREPOSITION", "preposition_use"),
    ("CONFUSION", "word_confusion"),
    ("CONFUSED", "word_confusion"),
)

#: Fallback subtype per ``issueType``, when no rule identifier matched.
ISSUE_TYPE_SUBTYPES: dict[str, str] = {
    "grammar": "grammar_error",
    "typographical": "punctuation",
    "whitespace": "punctuation",
    "duplication": "repeated_word",
    "inconsistency": "inconsistency",
    "non-conformance": "grammar_error",
    "characters": "punctuation",
}

#: How much each subtype costs the reader.
#:
#: ``MEDIUM`` for the things the exercise is teaching — agreement, tense,
#: articles — because those are errors against the conventions being marked.
#: ``LOW`` for punctuation and repetition: real, but the reader did not
#: stumble. ``INFO`` for inconsistency, which asserts no mistake at all —
#: writing "organise" in one sentence and "organize" in the next is a
#: consistency choice, not an error, and ``INFO`` is the rung that says so.
SUBTYPE_SEVERITY: dict[str, IssueSeverity] = {
    "subject_verb_agreement": IssueSeverity.MEDIUM,
    "verb_tense": IssueSeverity.MEDIUM,
    "article_use": IssueSeverity.MEDIUM,
    "preposition_use": IssueSeverity.MEDIUM,
    "word_confusion": IssueSeverity.MEDIUM,
    "sentence_structure": IssueSeverity.MEDIUM,
    "punctuation": IssueSeverity.LOW,
    "repeated_word": IssueSeverity.LOW,
    "inconsistency": IssueSeverity.INFO,
    "grammar_error": IssueSeverity.LOW,
}

#: A single unambiguous replacement from a rule this table recognises.
CONFIDENCE_SPECIFIC = 0.85
#: A single replacement, from a rule the table did not recognise.
CONFIDENCE_GENERAL = 0.7
#: Several replacements offered, or none. The finding stands; the fix does not.
CONFIDENCE_AMBIGUOUS = 0.6


@dataclass(frozen=True, slots=True)
class Classification:
    """What one LanguageTool match means in our vocabulary."""

    subtype: str
    severity: IssueSeverity
    #: Whether the rule identifier was recognised, which is what separates a
    #: confident correction from a plausible one.
    specific: bool


def classify(rule: dict[str, Any]) -> Classification | None:
    """Classify one match's ``rule`` object. ``None`` means "not ours".

    Reads only ``id``, ``issueType`` and ``category.id`` — the three fields
    LanguageTool keeps stable. Anything missing is treated as absent rather
    than raising: a response shape that drifts must degrade to a lower-grade
    finding, not fail a student's submission.
    """
    issue_type = str(rule.get("issueType") or "").lower()
    category = rule.get("category")
    category_id = (
        str((category or {}).get("id") or "").upper() if isinstance(category, dict) else ""
    )

    if issue_type in FOREIGN_ISSUE_TYPES or category_id in FOREIGN_CATEGORIES:
        return None

    rule_id = str(rule.get("id") or "").upper()
    for needle, subtype in RULE_SUBTYPES:
        if needle in rule_id:
            return Classification(subtype, SUBTYPE_SEVERITY[subtype], specific=True)

    subtype = ISSUE_TYPE_SUBTYPES.get(issue_type, "grammar_error")
    return Classification(subtype, SUBTYPE_SEVERITY[subtype], specific=False)


def confidence_for(classification: Classification, replacements: int) -> float:
    """How much to trust a match, from how specific it is.

    LanguageTool reports no confidence of its own. What it does report is how
    precisely it identified the problem, and that is a usable proxy: a rule
    this table recognises, offering exactly one replacement, is a correction
    worth showing. Several replacements means the engine could not choose, and
    a student should not be asked to.
    """
    if replacements != 1:
        return CONFIDENCE_AMBIGUOUS
    return CONFIDENCE_SPECIFIC if classification.specific else CONFIDENCE_GENERAL


__all__ = [
    "CONFIDENCE_AMBIGUOUS",
    "CONFIDENCE_GENERAL",
    "CONFIDENCE_SPECIFIC",
    "Classification",
    "classify",
    "confidence_for",
]
