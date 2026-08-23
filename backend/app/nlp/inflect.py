"""Surface-form variants of a vocabulary term.

Lemma matching is the primary mechanism and handles irregular forms that no
rule could — ``rose`` to ``rise``, ``fell`` to ``fall``. It is not, however,
complete. spaCy's lemmatiser falls back to suffix rules for words absent from
its lookup tables, and for at least one seeded term those rules are wrong:

    >>> [(t.text, t.lemma_) for t in nlp("Prices plateaued after the surge.")]
    [..., ('plateaued', 'plateaue'), ...]

``plateaued``, ``plateauing`` and even the plural ``plateaus`` all lemmatise to
something other than ``plateau``, so a student using the term correctly would
score zero for it. ``steadily`` is a milder case of the same thing: adverbs
carry their own lemma, so ``rose steadily`` earns no credit for ``steady``.

The safety net is to generate the inflections of *the target term* and match
those on surface form. The direction matters. Nothing is inferred from what
the student wrote; forms are derived only from a term a teacher has curated,
so crediting one requires the student to have written an actual inflection of
that term — which is exactly the behaviour FR-6.2 asks for. A generated form
that is not a real word simply never matches.
"""

from __future__ import annotations

VOWELS = frozenset("aeiou")

#: Consonants doubled before ``-ed`` / ``-ing`` in a stressed final syllable
#: (``drop`` → ``dropped``). ``w``, ``x`` and ``y`` are excluded because English
#: never doubles them.
DOUBLING_CONSONANTS = frozenset("bdglmnprtz")

#: Endings that take ``-es`` rather than a bare ``-s``.
SIBILANT_ENDINGS = ("s", "x", "z", "ch", "sh", "o")


def _third_person(stem: str) -> str:
    if stem.endswith("y") and len(stem) > 1 and stem[-2] not in VOWELS:
        return stem[:-1] + "ies"
    if stem.endswith(SIBILANT_ENDINGS):
        return stem + "es"
    return stem + "s"


def _should_double(stem: str) -> bool:
    """Whether the final consonant doubles before a vowel-initial suffix.

    Approximates the consonant-vowel-consonant rule. It is an approximation on
    purpose: getting it wrong produces a non-word, which costs nothing because
    a non-word never appears in a student's answer. Getting it wrong in the
    other direction — failing to generate ``dropped`` — costs a student marks.
    Both spellings are therefore generated whenever the rule is uncertain.
    """
    if len(stem) < 3:
        return False
    return stem[-1] in DOUBLING_CONSONANTS and stem[-2] in VOWELS and stem[-3] not in VOWELS


def _past(stem: str) -> set[str]:
    forms = set()
    if stem.endswith("e"):
        forms.add(stem + "d")
    elif stem.endswith("y") and len(stem) > 1 and stem[-2] not in VOWELS:
        forms.add(stem[:-1] + "ied")
    else:
        forms.add(stem + "ed")
    if _should_double(stem):
        forms.add(stem + stem[-1] + "ed")
    return forms


def _progressive(stem: str) -> set[str]:
    forms = set()
    if stem.endswith("e") and not stem.endswith("ee"):
        forms.add(stem[:-1] + "ing")
    else:
        forms.add(stem + "ing")
    if _should_double(stem):
        forms.add(stem + stem[-1] + "ing")
    return forms


def _adverb(stem: str) -> set[str]:
    if stem.endswith("y") and len(stem) > 1 and stem[-2] not in VOWELS:
        return {stem[:-1] + "ily"}
    if stem.endswith("le") and len(stem) > 2 and stem[-3] not in VOWELS:
        return {stem[:-1] + "y"}  # stable -> stably
    return {stem + "ly"}


def _comparatives(stem: str) -> set[str]:
    """``-er`` and ``-est``, generated only for short words.

    Long adjectives take *more* and *most* instead, and generating ``constanter``
    is harmless but pointless. The four-syllable-ish cut-off is a length proxy.
    """
    if len(stem) > 8:
        return set()
    if stem.endswith("y") and len(stem) > 1 and stem[-2] not in VOWELS:
        base = stem[:-1] + "i"
    elif stem.endswith("e"):
        base = stem[:-1]
    else:
        base = stem
    forms = {base + "er", base + "est"}
    if _should_double(stem):
        forms |= {stem + stem[-1] + "er", stem + stem[-1] + "est"}
    return forms


def _derived_nouns(stem: str) -> set[str]:
    """Nominalisations of a term, plus their plurals.

    Graph description leans on noun forms constantly — "a sharp fluctuation",
    "a steady reduction", "considerable growth" — and these are *derivations*,
    not inflections: ``fluctuation`` is its own lemma, so neither lemma
    matching nor the inflection rules above reach it. Left out, the engine
    systematically under-credits the more sophisticated construction, which is
    the opposite of what the rubric is for.

    The rules are productive where English is and best-effort where it is not.
    A rule that misfires produces a non-word, which never matches; the cost of
    omitting one is a student's marks.
    """
    forms: set[str] = set()

    if stem.endswith("ate"):
        forms.add(stem[:-1] + "ion")  # fluctuate -> fluctuation
    if stem.endswith("ce"):
        forms.add(stem[:-2] + "ction")  # reduce -> reduction
    if stem.endswith("ble"):
        forms.add(stem[:-2] + "ility")  # stable -> stability
    if stem.endswith("y") and len(stem) > 1 and stem[-2] not in VOWELS:
        forms.add(stem[:-1] + "iation")  # vary -> variation
        forms.add(stem[:-1] + "iness")  # steady -> steadiness
    else:
        forms.add(stem + "ness")

    forms.add(stem + "ion")
    forms.add(stem + "ation")
    forms.add(stem + "ment")
    forms.add(stem + "th")  # grow -> growth

    return forms | {_third_person(form) for form in forms}


def surface_variants(word: str) -> set[str]:
    """Lower-cased inflections and derivations of a word, including the word itself.

    Verb, noun and adjective forms are all generated regardless of the term's
    actual part of speech. Which of them are real words depends on the
    term, and deciding that would need a lexicon this layer does not have — but
    an unreal form costs nothing, because the matcher only ever looks for these
    strings and no student writes ``constantest``.
    """
    stem = word.strip().lower()
    if not stem or not stem.isalpha():
        return {stem} if stem else set()

    forms = {stem, _third_person(stem)}
    forms |= _past(stem)
    forms |= _progressive(stem)
    forms |= _adverb(stem)
    forms |= _comparatives(stem)
    forms |= _derived_nouns(stem)
    return {f for f in forms if f}


def phrase_variants(phrase: str) -> set[tuple[str, ...]]:
    """Token sequences for a multi-word term.

    Only the **first** word is inflected. In every phrase the library holds,
    that is the word that carries the inflection — ``bottomed out``, ``compared
    with``, ``higher than`` — while the remainder is a fixed particle or
    preposition. Inflecting the tail as well would multiply the pattern count
    for combinations English does not produce.
    """
    words = phrase.strip().lower().split()
    if not words:
        return set()
    if len(words) == 1:
        return {(form,) for form in surface_variants(words[0])}

    tail = tuple(words[1:])
    return {(form, *tail) for form in surface_variants(words[0])}
