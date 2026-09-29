"""Adapter registry for format detection and dispatch."""

from __future__ import annotations

import mimetypes
from typing import Any, Optional
from pathlib import Path

from src.adapters.base import AdapterBase, AdapterError
from src.adapters.json_adapter import JSONAdapter
from src.adapters.srt_adapter import SRTAdapter, VTTAdapter, ASSAdapter
from src.adapters.csv_adapter import CSVAdapter
from src.adapters.plain_text_adapter import PlainTextAdapter
from src.adapters.pdf_adapter import PDFAdapter


class AdapterRegistry:
    """Registry for managing and dispatching adapters."""

    def __init__(self):
        self._adapters: list[AdapterBase] = []
        self._extension_map: dict[str, AdapterBase] = {}
        self._mime_map: dict[str, AdapterBase] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register built-in adapters."""
        adapters = [
            JSONAdapter(),
            SRTAdapter(),
            VTTAdapter(),
            ASSAdapter(),
            CSVAdapter(),
            PlainTextAdapter(),
            PDFAdapter(),
        ]
        for adapter in adapters:
            self.register(adapter)

    def register(self, adapter: AdapterBase) -> None:
        """Register an adapter."""
        self._adapters.append(adapter)
        for ext in adapter.supported_extensions:
            self._extension_map[ext.lower()] = adapter
        for mime in adapter.supported_mime_types:
            self._mime_map[mime.lower()] = adapter

    def get_by_extension(self, path: Path) -> Optional[AdapterBase]:
        """Get adapter by file extension."""
        return self._extension_map.get(path.suffix.lower())

    def get_by_mime(self, mime_type: str) -> Optional[AdapterBase]:
        """Get adapter by MIME type."""
        return self._mime_map.get(mime_type.lower())

    def detect_and_parse(self, path: Path, raw_bytes: bytes, hints: dict[str, Any] | None = None) -> Any:
        """Detect format and parse file."""
        hints = hints or {}
        
        # Try extension first
        adapter = self.get_by_extension(path)
        if adapter:
            try:
                return adapter.parse(raw_bytes, hints)
            except AdapterError:
                pass  # Fall through to content detection

        # Try MIME type detection
        mime_type, _ = mimetypes.guess_type(str(path))
        if mime_type:
            adapter = self.get_by_mime(mime_type)
            if adapter:
                try:
                    return adapter.parse(raw_bytes, hints)
                except AdapterError:
                    pass

        # Try content-based detection for each adapter
        for adapter in self._adapters:
            try:
                return adapter.parse(raw_bytes, hints)
            except AdapterError:
                continue

        raise AdapterError(f"No adapter could parse file: {path}")

    def parse_with_type(self, raw_bytes: bytes, target_type: str, hints: dict[str, Any] | None = None) -> Any:
        """Parse with explicit target type hint."""
        hints = hints or {}
        hints["target_type"] = target_type
        
        for adapter in self._adapters:
            try:
                return adapter.parse(raw_bytes, hints)
            except AdapterError:
                continue

        raise AdapterError(f"No adapter could parse data as {target_type}")


# Global registry instance
registry = AdapterRegistry()