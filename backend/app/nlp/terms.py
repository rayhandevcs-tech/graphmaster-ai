"""Target vocabulary and the matchers built from it."""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from app.nlp.inflect import phrase_variants, surface_variants
from app.nlp.pipeline import get_nlp

if TYPE_CHECKING:  # pragma: no cover
    from spacy.matcher import PhraseMatcher


@dataclass(frozen=True, slots=True)
class TargetTerm:
    """One term a graph asks the student to use.

    Frozen and hashable so a target set can key the matcher cache: a class of
    forty students working through the same graph then shares one compiled
    matcher instead of rebuilding it forty times.
    """

    term: str
    lemma: str
    category_code: str
    category_name: str
    is_phrase: bool
    is_required: bool = True
    #: Suggestion order only. `scoring.py` never reads it — see the column
    #: comment on `VocabularyItem.weight` for why the name is misleading.
    weight: float = 1.0
    item_id: uuid.UUID | None = None

    @property
    def key(self) -> str:
        """Identity for aggregation. The lemma is unique across the library."""
        return self.lemma


@dataclass(frozen=True, slots=True)
class CompiledTargets:
    """Everything the detector needs, derived once per distinct target set."""

    terms: tuple[TargetTerm, ...]
    #: Single-word terms indexed by the lemma the parser should produce.
    by_lemma: dict[str, TargetTerm]
    #: Single-word terms indexed by every generated surface inflection.
    by_surface: dict[str, TargetTerm]
    #: Phrase terms matched on their lemma sequence.
    phrase_lemma_matcher: PhraseMatcher | None
    #: Phrase terms matched on generated surface inflections.
    phrase_surface_matcher: PhraseMatcher | None
    #: Match key (the term lemma) back to the term.
    by_key: dict[str, TargetTerm]
    #: The vocabulary the matchers were built against.
    #:
    #: A ``PhraseMatcher`` reports matches as hashes into its own ``Vocab``'s
    #: string store, so running one against a document from a *different*
    #: vocabulary raises ``[E018] Can't retrieve string for hash``. Holding the
    #: vocabulary here both records which one this was built for and keeps a
    #: strong reference to it, so the identity check below cannot be fooled by
    #: a recycled object address.
    vocab: Any

    @property
    def required(self) -> tuple[TargetTerm, ...]:
        return tuple(t for t in self.terms if t.is_required)

    @property
    def optional(self) -> tuple[TargetTerm, ...]:
        return tuple(t for t in self.terms if not t.is_required)


def compile_targets(terms: Iterable[TargetTerm]) -> CompiledTargets:
    """Compile a target set, reusing a previous compilation when possible.

    ``lru_cache`` is applied to the tuple form rather than to this function so
    callers can pass any iterable without defeating the cache.

    A compilation is only reusable while the pipeline it was built against is
    still the current one. If the pipeline has been reloaded, every cached
    matcher now refers to a dead string store, so the whole cache is dropped
    rather than handing back one that would fail — or, worse, quietly stop
    matching — on the next document.
    """
    key = tuple(terms)
    compiled = _compile(key)
    if compiled.vocab is not get_nlp().vocab:
        _compile.cache_clear()
        compiled = _compile(key)
    return compiled


@lru_cache(maxsize=256)
def _compile(terms: tuple[TargetTerm, ...]) -> CompiledTargets:
    from spacy.matcher import PhraseMatcher
    from spacy.tokens import Doc

    nlp = get_nlp()

    by_lemma: dict[str, TargetTerm] = {}
    by_surface: dict[str, TargetTerm] = {}
    by_key: dict[str, TargetTerm] = {term.key: term for term in terms}

    lemma_patterns: dict[str, list[Doc]] = {}
    surface_patterns: dict[str, list[Doc]] = {}

    for term in terms:
        if term.is_phrase:
            words = term.lemma.split()
            if words:
                # Built with explicit lemmas rather than by running the
                # pipeline over the pattern string. Lemmatising a bare
                # fragment out of context is exactly where the tagger is least
                # reliable, and a mis-lemmatised pattern is a term that can
                # never match anything — a silent scoring failure rather than
                # a visible one.
                lemma_patterns[term.key] = [
                    Doc(nlp.vocab, words=words, lemmas=words),
                ]
            surface_patterns[term.key] = [
                Doc(nlp.vocab, words=list(variant))
                for variant in sorted(phrase_variants(term.term))
            ]
        else:
            lemma = term.lemma.strip().lower()
            if lemma:
                by_lemma.setdefault(lemma, term)
            for variant in surface_variants(term.term):
                by_surface.setdefault(variant, term)
            # A hand-set lemma is also worth accepting as a surface form: a
            # teacher who typed one has told us what the word looks like.
            by_surface.setdefault(lemma, term)

    phrase_lemma_matcher = None
    if lemma_patterns:
        phrase_lemma_matcher = PhraseMatcher(nlp.vocab, attr="LEMMA")
        for key, patterns in lemma_patterns.items():
            phrase_lemma_matcher.add(key, patterns)

    phrase_surface_matcher = None
    if any(surface_patterns.values()):
        phrase_surface_matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
        for key, patterns in surface_patterns.items():
            if patterns:
                phrase_surface_matcher.add(key, patterns)

    return CompiledTargets(
        terms=terms,
        by_lemma=by_lemma,
        by_surface=by_surface,
        phrase_lemma_matcher=phrase_lemma_matcher,
        phrase_surface_matcher=phrase_surface_matcher,
        by_key=by_key,
        vocab=nlp.vocab,
    )


def clear_cache() -> None:
    """Drop compiled matchers.

    Needed when the vocabulary library changes underneath a running process,
    and by tests that swap the pipeline.
    """
    _compile.cache_clear()


def dedupe(terms: Sequence[TargetTerm]) -> tuple[TargetTerm, ...]:
    """Collapse repeated lemmas, keeping the first occurrence.

    A graph's targets come from a table with a uniqueness constraint, but the
    type-derived default set is assembled from several categories and could
    otherwise offer the same term twice — which would inflate the denominator
    and make the graph unfairly hard.
    """
    seen: set[str] = set()
    unique: list[TargetTerm] = []
    for term in terms:
        if term.key in seen:
            continue
        seen.add(term.key)
        unique.append(term)
    return tuple(unique)
