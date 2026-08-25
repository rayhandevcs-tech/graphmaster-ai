"""The analyzers themselves.

Each takes the deployment's :class:`~app.core.config.Settings` and one
:class:`~app.assessment.protocol.AssessmentContext`, and returns findings. The
uniform constructor is dependency injection rather than ceremony: the
provider-backed analyzers arriving in sprint 18 need somewhere to read a URL
and a timeout from, and a registry that builds every analyzer the same way is
what lets one be swapped for a fake in a test.
"""

from __future__ import annotations

from app.assessment.analyzers.sentence import SentenceAnalyzer
from app.assessment.analyzers.spelling import SpellingAnalyzer
from app.assessment.analyzers.vocabulary import VocabularyAnalyzer
from app.assessment.analyzers.word_usage import WordUsageAnalyzer
from app.assessment.analyzers.writing import WritingAnalyzer

__all__ = [
    "SentenceAnalyzer",
    "SpellingAnalyzer",
    "VocabularyAnalyzer",
    "WordUsageAnalyzer",
    "WritingAnalyzer",
]
