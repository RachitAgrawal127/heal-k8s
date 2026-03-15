from dataclasses import dataclass
from typing import Optional


@dataclass
class Incident:
    """
    Represents a stored incident pattern in the memory database.
    """
    failure_type: str
    fix: str
    confidence: float
    success_count: int
    failure_count: int
    last_seen: Optional[str] = None
    created_at: Optional[str] = None

    @property
    def total_seen(self) -> int:
        return self.success_count + self.failure_count

    @property
    def confidence_label(self) -> str:
        """Human-readable badge label for the dashboard."""
        if self.confidence >= 0.9:
            return "High Confidence"
        elif self.confidence >= 0.7:
            return "Medium Confidence"
        else:
            return "Low Confidence"

    def to_dict(self) -> dict:
        return {
            "failure_type": self.failure_type,
            "fix": self.fix,
            "confidence": self.confidence,
            "confidence_label": self.confidence_label,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "total_seen": self.total_seen,
            "last_seen": self.last_seen,
            "created_at": self.created_at,
        }