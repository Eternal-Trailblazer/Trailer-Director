"""Decision logger for observability."""

from __future__ import annotations

import uuid
from typing import Any
from dataclasses import dataclass, field
from datetime import datetime

from src.models.decision_log import DecisionLogEntry


@dataclass
class DecisionLogger:
    """Logs all decisions for observability."""

    entries: list[DecisionLogEntry] = field(default_factory=list)

    def log(
        self,
        component: str,
        decision_type: str,
        description: str,
        evidence: list[str] = None,
        alternatives_considered: list[str] = None,
        confidence: float = 1.0,
        cost_incurred: float = 0.0,
        human_approval_required: bool = False,
    ) -> DecisionLogEntry:
        """Log a decision."""
        entry = DecisionLogEntry(
            entry_id=f"dec_{uuid.uuid4().hex[:8]}",
            timestamp=datetime.now(),
            component=component,
            decision_type=decision_type,
            description=description,
            evidence=evidence or [],
            alternatives_considered=alternatives_considered or [],
            confidence=confidence,
            cost_incurred=cost_incurred,
            human_approval_required=human_approval_required,
        )
        self.entries.append(entry)
        return entry

    def get_entries(self, component: str | None = None, decision_type: str | None = None) -> list[DecisionLogEntry]:
        """Get filtered entries."""
        result = self.entries
        if component:
            result = [e for e in result if e.component == component]
        if decision_type:
            result = [e for e in result if e.decision_type == decision_type]
        return result

    def export_json(self) -> list[dict]:
        """Export all entries as JSON-serializable dicts."""
        result = []
        for e in self.entries:
            d = e.model_dump()
            d['timestamp'] = d['timestamp'].isoformat()
            result.append(d)
        return result

    def clear(self) -> None:
        """Clear all entries."""
        self.entries.clear()