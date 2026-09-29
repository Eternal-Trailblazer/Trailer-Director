"""Base adapter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional
from pathlib import Path
from pydantic import BaseModel


@dataclass
class AdapterError(Exception):
    """Raised when an adapter fails to parse input."""
    message: str
    source_path: Optional[str] = None
    raw_content: Optional[str] = None


class AdapterBase(ABC):
    """Abstract base class for all input adapters."""

    supported_extensions: list[str] = []
    supported_mime_types: list[str] = []

    @abstractmethod
    def parse(self, raw_bytes: bytes, hints: dict[str, Any] | None = None) -> Any:
        """Parse raw bytes into canonical record(s)."""
        pass

    def can_handle(self, path: Path) -> bool:
        """Check if this adapter can handle the given file."""
        return path.suffix.lower() in self.supported_extensions

    @classmethod
    def detect_format(cls, raw_bytes: bytes) -> Optional[str]:
        """Attempt to detect format from raw content. Override in subclasses."""
        return None


class CanonicalRecord(BaseModel):
    """Base class for canonical records after parsing."""
    pass