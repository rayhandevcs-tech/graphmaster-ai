"""The assessment engine: what the student got wrong, where, and why.

``app.nlp`` answers "what is this answer worth". This package answers "what
should the student do differently", and the two are deliberately separate
concerns with a hard boundary between them:

**Nothing here can change a score.** The 70/30 rubric in
:mod:`app.nlp.scoring` keeps exactly the two inputs it has always had. Every
analyzer in this package is diagnostic — it produces issues, metrics and a
category score that are reported *beside* the score, never folded into it.
Folding them in would re-rank every leaderboard, move every reward tier, and
make the scores already in the corpus incomparable with everything scored
afterwards.

That constraint is enforced by test, not by intention: see
``tests/unit/test_assessment_isolation.py``.
"""

from __future__ import annotations

import hashlib

from app.core.config import Settings

#: The assessment pipeline's own version, independent of ``ENGINE_VERSION``.
#:
#: Two versions rather than one because the two evolve for different reasons.
#: Adding a spelling analyzer changes nothing about how a score was computed,
#: so bumping ``ENGINE_VERSION`` would mark a run of identical scores as
#: belonging to a different engine and break exactly the cohort comparison
#: that field exists to protect. This one moves instead.
ASSESSMENT_VERSION = "1.0.0"

#: Fields of an issue that never vary, kept here so the schema has one home.
MAX_EXPLANATION_CHARS = 400


def assessment_version(settings: Settings) -> str:
    """The version stamped on every assessment.

    Fingerprinted for the same reason ``engine_version`` is: which analyzers
    run, and the confidence floor their issues must clear, are deployment
    configuration. Two assessments produced under different analyzer sets are
    not comparable, and without the fingerprint they would carry the same
    version string and silently look as though they were.

    Turning the grammar provider on therefore produces a visibly different
    version, which is what makes a historical result reproducible: the
    configuration that produced it can be recovered from the row.
    """
    material = "|".join(
        (
            ",".join(sorted(settings.assessment_analyzers)),
            settings.GRAMMAR_PROVIDER,
            f"{settings.ASSESSMENT_ISSUE_CONFIDENCE_FLOOR:.3f}",
            str(settings.ASSESSMENT_MAX_ISSUES_PER_CATEGORY),
        )
    )
    digest = hashlib.blake2s(material.encode("utf-8"), digest_size=4).hexdigest()
    return f"{ASSESSMENT_VERSION}+{digest}"


__all__ = ["ASSESSMENT_VERSION", "MAX_EXPLANATION_CHARS", "assessment_version"]
