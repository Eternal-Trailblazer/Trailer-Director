"""Cost Ledger models."""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class CostLedgerEntry(BaseModel):
    operation: str
    provider: str
    tokens_in: int
    tokens_out: int
    cost: float
    timestamp: datetime = Field(default_factory=datetime.now)
    budget_tag: str = ""


class CostLedger(BaseModel):
    entries: list[CostLedgerEntry] = Field(default_factory=list)
    total_cost: float = 0.0
    budget_limit: float = 0.0
    budget_remaining: float = 0.0

    def add_entry(self, entry: CostLedgerEntry) -> None:
        self.entries.append(entry)
        self.total_cost += entry.cost
        self.budget_remaining = self.budget_limit - self.total_cost

    def is_over_budget(self) -> bool:
        return self.total_cost > self.budget_limit