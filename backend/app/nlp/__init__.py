"""The analysis and evaluation engine.

Takes a student's graph description plus the target vocabulary for that graph
and produces the vocabulary score, writing-quality score, final score, reward
tier and feedback stored in ``scores``
(docs/architecture/08-nlp-architecture.md).

The package is deliberately free of database and HTTP concerns: everything
here operates on plain text and :class:`~app.nlp.terms.TargetTerm` values, so
the engine can be exercised in a unit test, a notebook or an offline research
script without a running application. ``app.services.analysis`` is the layer
that loads terms from the database and hands them in.
"""

from __future__ import annotations

#: The scoring rules' own version, recorded on every ``Score`` row.
#:
#: Bump the minor part when matching behaviour changes and the major part when
#: the score is no longer comparable with earlier cohorts at all. The value
#: actually stored is this string plus a fingerprint of the deployed rubric —
#: see :func:`app.nlp.scoring.engine_version`, which explains why the code
#: version alone is not enough.
ENGINE_VERSION = "1.0.0"

#: Refuse to analyse anything longer than this.
#:
#: A graph description is a paragraph; the band the rubric rewards tops out at
#: 250 words. Parsing is linear in length, so an unbounded input is a way to
#: spend the server's CPU rather than a legitimate answer.
MAX_ANALYSIS_CHARS = 20_000

__all__ = ["ENGINE_VERSION", "MAX_ANALYSIS_CHARS"]
