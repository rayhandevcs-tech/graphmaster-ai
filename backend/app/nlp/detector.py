"""Vocabulary detection (FR-6.2 to FR-6.5)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.nlp.normalise import NormalisedText
from app.nlp.terms import CompiledTargets, TargetTerm

if TYPE_CHECKING:  # pragma: no cover
    from spacy.tokens import Doc, Span

#: Parts of speech a single-word term may be credited in.
#:
#: Restricting to content words stops an unrelated homograph in a function-word
#: role counting as a vocabulary hit (08-nlp-architecture.md §4.1). ``PROPN`` is
#: included because the tagger routinely labels a sentence-initial capitalised
#: noun as a proper noun — "Fluctuation was common throughout" would otherwise
#: earn nothing for a term the student used correctly and prominently.
CONTENT_POS = frozenset({"VERB", "NOUN", "PROPN", "ADJ", "ADV"})


@dataclass(frozen=True, slots=True)
class Occurrence:
    """One place a term was found, located in the student's original text."""

    matched_form: str
    start: int
    end: int


@dataclass(slots=True)
class DetectedTerm:
    """A target term the student used, with every place they used it."""

    term: TargetTerm
    occurrences: list[Occurrence] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.occurrences)

    @property
    def matched_forms(self) -> list[str]:
        """Distinct surface forms, in order of first appearance.

        Shown back to the student in the feedback, so it must be their own
        spelling rather than the library's headword — being told you used
        "increase" when you wrote "increased" reads as a correction.
        """
        seen: dict[str, None] = {}
        for occurrence in self.occurrences:
            seen.setdefault(occurrence.matched_form, None)
        return list(seen)

    def to_dict(self) -> dict[str, Any]:
        return {
            "term": self.term.term,
            "lemma": self.term.lemma,
            "category": self.term.category_code,
            "category_name": self.term.category_name,
            "is_required": self.term.is_required,
            "count": self.count,
            "matched_forms": self.matched_forms,
            "positions": [[o.start, o.end] for o in self.occurrences],
        }


@dataclass(slots=True)
class DetectionResult:
    detected: list[DetectedTerm]
    missing: list[TargetTerm]

    @property
    def total_occurrences(self) -> int:
        """Every hit, including repeats (FR-6.4)."""
        return sum(d.count for d in self.detected)

    @property
    def unique_terms(self) -> int:
        return len(self.detected)


def detect(doc: Doc, normalised: NormalisedText, targets: CompiledTargets) -> DetectionResult:
    """Find every target term in ``doc``.

    Phrases are matched first and their tokens masked. Without the mask,
    "higher than" would also register a ``high`` detection where the library
    holds one, counting a single piece of student writing as two vocabulary
    hits (08-nlp-architecture.md §4.2).
    """
    found: dict[str, DetectedTerm] = {}

    spans = _phrase_spans(doc, targets)
    masked: set[int] = set()

    for span, term in spans:
        masked.update(range(span.start, span.end))
        _record(found, term, span.start_char, span.end_char, normalised)

    for token in doc:
        if token.i in masked or token.is_punct or token.is_space:
            continue
        if token.pos_ not in CONTENT_POS:
            continue

        term = targets.by_lemma.get(token.lemma_.lower())
        if term is None:
            # The lemma did not match. Fall back to the surface inflections
            # generated from the target term itself, which is what rescues the
            # terms spaCy's suffix rules lemmatise wrongly (see app.nlp.inflect).
            term = targets.by_surface.get(token.lower_)
        if term is None:
            continue

        _record(found, term, token.idx, token.idx + len(token.text), normalised)

    detected = [found[key] for key in sorted(found, key=lambda k: _first_position(found[k]))]
    missing = [term for term in targets.terms if term.key not in found]

    return DetectionResult(detected=detected, missing=missing)


def _phrase_spans(doc: Doc, targets: CompiledTargets) -> list[tuple[Span, TargetTerm]]:
    """Non-overlapping phrase matches, longest first."""
    from spacy.tokens import Span
    from spacy.util import filter_spans

    raw: list[Span] = []
    for matcher in (targets.phrase_lemma_matcher, targets.phrase_surface_matcher):
        if matcher is None:
            continue
        for match_id, start, end in matcher(doc):
            # The term key rides along as the span's label. The two matchers
            # can produce the same span for the same term — a phrase whose
            # lemma pattern and surface pattern both fire — and identical
            # labelled spans collapse to one in `filter_spans`.
            raw.append(Span(doc, start, end, label=doc.vocab.strings[match_id]))

    if not raw:
        return []

    # Longest match wins: "lowest point" must not lose to a bare "point", and
    # overlapping credit would double-count one phrase as two terms.
    resolved: list[tuple[Span, TargetTerm]] = []
    for span in filter_spans(raw):
        term = targets.by_key.get(span.label_)
        if term is not None:
            resolved.append((span, term))
    return resolved


def _record(
    found: dict[str, DetectedTerm],
    term: TargetTerm,
    start_char: int,
    end_char: int,
    normalised: NormalisedText,
) -> None:
    start, end = normalised.to_original(start_char, end_char)
    entry = found.get(term.key)
    if entry is None:
        entry = DetectedTerm(term=term)
        found[term.key] = entry
    entry.occurrences.append(
        Occurrence(
            matched_form=normalised.original[start:end].strip() or term.term,
            start=start,
            end=end,
        )
    )


def _first_position(entry: DetectedTerm) -> int:
    return entry.occurrences[0].start if entry.occurrences else 0
