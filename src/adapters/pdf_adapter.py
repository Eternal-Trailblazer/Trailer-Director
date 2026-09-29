"""PDF adapter for document input."""

from __future__ import annotations

from typing import Any
from pathlib import Path

from src.adapters.base import AdapterBase, AdapterError, CanonicalRecord


class PDFAdapter(AdapterBase):
    """Adapter for PDF files - extracts text and delegates to plain text adapter."""

    supported_extensions = [".pdf"]
    supported_mime_types = ["application/pdf"]

    def __init__(self):
        self._has_pdf_support = False
        try:
            import pdfplumber  # type: ignore
            self._has_pdf_support = True
        except ImportError:
            pass

    def parse(self, raw_bytes: bytes, hints: dict[str, Any] | None = None) -> CanonicalRecord:
        hints = hints or {}
        
        if not self._has_pdf_support:
            raise AdapterError(
                "PDF support requires 'pdfplumber' package. Install with: pip install pdfplumber",
                raw_content="PDF parsing not available"
            )

        import pdfplumber
        import io

        try:
            text_parts = []
            with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)
            
            full_text = "\n\n".join(text_parts)
            if not full_text.strip():
                raise AdapterError("No text extracted from PDF")

            # Delegate to plain text adapter logic
            from src.adapters.plain_text_adapter import PlainTextAdapter
            plain_adapter = PlainTextAdapter()
            return plain_adapter.parse(full_text.encode("utf-8"), hints)

        except Exception as e:
            if isinstance(e, AdapterError):
                raise
            raise AdapterError(f"Failed to parse PDF: {e}")