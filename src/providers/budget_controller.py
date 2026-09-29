"""Budget controller for tracking and limiting costs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.models.cost import CostLedger, CostLedgerEntry


@dataclass
class BudgetConfig:
    """Budget configuration."""
    total_usd: float = 10.0
    model_call_limit: int = 200
    media_processing_limit: int = 50
    warn_at_percent: float = 80.0


class BudgetController:
    """Controls and tracks budget usage."""

    def __init__(self, config: BudgetConfig):
        self.config = config
        self.ledger = CostLedger(
            budget_limit=config.total_usd,
            budget_remaining=config.total_usd,
        )
        self.call_count = 0
        self.media_count = 0
        self.warnings_issued = set()

    def check_budget(self, estimated_cost: float, tag: str = "") -> bool:
        """Check if operation would exceed budget."""
        # Check monetary budget
        if self.ledger.total_cost + estimated_cost > self.config.total_usd:
            return False
        
        # Check call limit
        if self.call_count >= self.config.model_call_limit:
            return False
        
        return True

    def record_spend(self, actual_cost: float, tag: str = "", tokens_in: int = 0, tokens_out: int = 0, provider: str = "") -> None:
        """Record actual spend."""
        entry = CostLedgerEntry(
            operation=tag or "model_call",
            provider=provider,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost=actual_cost,
            timestamp=datetime.now(),
            budget_tag=tag,
        )
        self.ledger.add_entry(entry)
        self.call_count += 1
        
        # Check warning threshold
        if self.ledger.budget_limit > 0:
            pct = (self.ledger.total_cost / self.ledger.budget_limit) * 100
            if pct >= self.config.warn_at_percent and "budget_warning" not in self.warnings_issued:
                self.warnings_issued.add("budget_warning")
                # Would log warning here

    def record_media_processing(self, cost: float = 0.0) -> None:
        """Record media processing operation."""
        self.media_count += 1
        if cost > 0:
            self.record_spend(cost, "media_processing")

    def remaining(self) -> float:
        """Get remaining budget."""
        return self.ledger.budget_remaining

    def get_ledger(self) -> CostLedger:
        """Get cost ledger."""
        return self.ledger

    def get_usage_stats(self) -> dict[str, Any]:
        """Get usage statistics."""
        return {
            "total_cost": self.ledger.total_cost,
            "budget_limit": self.config.total_usd,
            "budget_remaining": self.ledger.budget_remaining,
            "call_count": self.call_count,
            "call_limit": self.config.model_call_limit,
            "media_count": self.media_count,
            "media_limit": self.config.media_processing_limit,
            "percent_used": (self.ledger.total_cost / self.config.total_usd * 100) if self.config.total_usd > 0 else 0,
        }