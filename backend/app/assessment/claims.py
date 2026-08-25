"""A statement the student made about the chart, and whether it holds.

Correct claims are recorded as well as incorrect ones. "You read four trends
and got three right" is the educational figure, and it cannot be recovered from
the errors alone — a student with no issues might have made three correct
claims or none at all.

``UNVERIFIED`` is the honest majority case and is stored too. "We could not
check this" and "we checked it and it was fine" are different, and only one of
them should encourage anybody.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.enums import ClaimType, ClaimVerdict


@dataclass(frozen=True, slots=True)
class GraphClaim:
    """One checkable statement, located in the student's own text."""

    claim_type: ClaimType
    verdict: ClaimVerdict
    #: What the student said — "decrease", "2020", "above".
    claimed: str
    #: What the chart says. For an unverified claim this records *why* it could
    #: not be judged, so a teacher reviewing a false negative can see whether
    #: the fault was the sentence or the data.
    actual: str
    #: The dataset it resolved to, or ``None`` when it resolved to none.
    series_label: str | None
    start: int
    end: int
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < self.start:
            raise ValueError(
                f"Claim span [{self.start}, {self.end}) is not a valid half-open range."
            )
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Claim confidence {self.confidence} is outside 0-1.")
        if self.verdict is ClaimVerdict.UNVERIFIED and self.series_label is not None:
            # A claim that resolved to a series is one this engine could judge.
            # Recording it as unverified *and* attributed would make the
            # accuracy figure unreadable.
            raise ValueError("An unverified claim cannot name a series.")

    @property
    def is_verified(self) -> bool:
        return self.verdict is not ClaimVerdict.UNVERIFIED

    @property
    def is_correct(self) -> bool:
        return self.verdict is ClaimVerdict.CORRECT

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_type": self.claim_type.value,
            "verdict": self.verdict.value,
            "claimed": self.claimed,
            "actual": self.actual,
            "series_label": self.series_label,
            "start": self.start,
            "end": self.end,
            "confidence": round(self.confidence, 4),
        }


__all__ = ["GraphClaim"]
