"""Human approval registry."""

from __future__ import annotations

import uuid
from typing import Any
from dataclasses import dataclass, field
from datetime import datetime

from src.models.human_approval import HumanApprovalEntry, ApprovalStatus, ApprovalUrgency


@dataclass
class HumanRegistry:
    """Registry for decisions requiring human approval."""

    entries: list[HumanApprovalEntry] = field(default_factory=list)

    def register(
        self,
        decision_type: str,
        description: str,
        affected_trailer_ids: list[str] = None,
        affected_segment_ids: list[str] = None,
        urgency: ApprovalUrgency = ApprovalUrgency.ADVISORY,
    ) -> HumanApprovalEntry:
        """Register a decision requiring human approval."""
        entry = HumanApprovalEntry(
            entry_id=f"approval_{uuid.uuid4().hex[:8]}",
            decision_type=decision_type,
            description=description,
            affected_trailer_ids=affected_trailer_ids or [],
            affected_segment_ids=affected_segment_ids or [],
            urgency=urgency,
            status=ApprovalStatus.PENDING,
        )
        self.entries.append(entry)
        return entry

    def approve(self, entry_id: str) -> bool:
        """Approve a pending entry."""
        for entry in self.entries:
            if entry.entry_id == entry_id:
                entry.status = ApprovalStatus.APPROVED
                return True
        return False

    def reject(self, entry_id: str) -> bool:
        """Reject a pending entry."""
        for entry in self.entries:
            if entry.entry_id == entry_id:
                entry.status = ApprovalStatus.REJECTED
                return True
        return False

    def get_pending(self, urgency: ApprovalUrgency | None = None) -> list[HumanApprovalEntry]:
        """Get pending approvals."""
        pending = [e for e in self.entries if e.status == ApprovalStatus.PENDING]
        if urgency:
            pending = [e for e in pending if e.urgency == urgency]
        return pending

    def get_blocking(self) -> list[HumanApprovalEntry]:
        """Get blocking approvals."""
        return [e for e in self.entries if e.urgency == ApprovalUrgency.BLOCKING and e.status == ApprovalStatus.PENDING]

    def export_json(self) -> list[dict]:
        """Export all entries as JSON."""
        return [e.model_dump() for e in self.entries]

    def clear(self) -> None:
        """Clear all entries."""
        self.entries.clear()