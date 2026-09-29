"""SRT subtitle adapter."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from pathlib import Path

from src.adapters.base import AdapterBase, AdapterError, CanonicalRecord
from src.models.timecode import Timecode, parse_timecode, TimecodeFormat


@dataclass
class SubtitleCue:
    index: int
    start: Timecode
    end: Timecode
    text: str
    language: str = "unknown"


class SRTAdapter(AdapterBase):
    """Adapter for SRT subtitle files."""

    supported_extensions = [".srt"]
    supported_mime_types = ["application/x-subrip", "text/srt"]

    # SRT format: index\nHH:MM:SS,mmm --> HH:MM:SS,mmm\nText\n\n
    SRT_PATTERN = re.compile(
        r"(\d+)\s*\n"
        r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\n"
        r"(.*?)(?:\n\s*\n|\Z)",
        re.DOTALL | re.MULTILINE
    )

    def parse(self, raw_bytes: bytes, hints: dict[str, Any] | None = None) -> CanonicalRecord:
        hints = hints or {}
        try:
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = raw_bytes.decode("latin-1")
            except UnicodeDecodeError as e:
                raise AdapterError(f"Unable to decode SRT file: {e}", raw_content=raw_bytes.decode("utf-8", errors="replace"))

        language = hints.get("language", "unknown")
        cues = self._parse_srt(text, language)
        return cues

    def _parse_srt(self, text: str, language: str) -> list[SubtitleCue]:
        cues = []
        for match in self.SRT_PATTERN.finditer(text):
            index = int(match.group(1))
            start_raw = match.group(2)
            end_raw = match.group(3)
            cue_text = match.group(4).strip().replace("\n", " ")

            try:
                start = parse_timecode(start_raw, TimecodeFormat.MILLISECONDS)
                end = parse_timecode(end_raw, TimecodeFormat.MILLISECONDS)
            except ValueError as e:
                raise AdapterError(f"Invalid timecode in SRT at cue {index}: {e}")

            cues.append(SubtitleCue(
                index=index,
                start=start,
                end=end,
                text=cue_text,
                language=language
            ))

        if not cues:
            raise AdapterError("No valid subtitle cues found in SRT file")

        return cues


class VTTAdapter(AdapterBase):
    """Adapter for WebVTT subtitle files."""

    supported_extensions = [".vtt"]
    supported_mime_types = ["text/vtt", "application/vtt"]

    # VTT format: WEBVTT\n\nHH:MM:SS.mmm --> HH:MM:SS.mmm\nText\n\n
    VTT_PATTERN = re.compile(
        r"(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})[^\n]*\n"
        r"(.*?)(?:\n\s*\n|\Z)",
        re.DOTALL | re.MULTILINE
    )

    def parse(self, raw_bytes: bytes, hints: dict[str, Any] | None = None) -> CanonicalRecord:
        hints = hints or {}
        try:
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as e:
            raise AdapterError(f"Unable to decode VTT file: {e}", raw_content=raw_bytes.decode("utf-8", errors="replace"))

        # Skip WEBVTT header
        if text.startswith("WEBVTT"):
            text = text[6:].lstrip()

        language = hints.get("language", "unknown")
        cues = self._parse_vtt(text, language)
        return cues

    def _parse_vtt(self, text: str, language: str) -> list[SubtitleCue]:
        cues = []
        for i, match in enumerate(self.VTT_PATTERN.finditer(text), 1):
            start_raw = match.group(1)
            end_raw = match.group(2)
            cue_text = match.group(3).strip().replace("\n", " ")

            try:
                start = parse_timecode(start_raw, TimecodeFormat.MILLISECONDS)
                end = parse_timecode(end_raw, TimecodeFormat.MILLISECONDS)
            except ValueError as e:
                raise AdapterError(f"Invalid timecode in VTT at cue {i}: {e}")

            cues.append(SubtitleCue(
                index=i,
                start=start,
                end=end,
                text=cue_text,
                language=language
            ))

        if not cues:
            raise AdapterError("No valid subtitle cues found in VTT file")

        return cues


class ASSAdapter(AdapterBase):
    """Adapter for ASS/SSA subtitle files."""

    supported_extensions = [".ass", ".ssa"]
    supported_mime_types = ["text/x-ass", "application/x-ssa"]

    # ASS format: Dialogue: 0,0:00:00.00,0:00:00.00,Style,,0,0,0,,Text
    ASS_PATTERN = re.compile(
        r"^Dialogue:\s*\d+,"
        r"(\d:\d{2}:\d{2}\.\d{2}),"
        r"(\d:\d{2}:\d{2}\.\d{2}),"
        r"[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,"
        r"(.*)$",
        re.MULTILINE
    )

    def parse(self, raw_bytes: bytes, hints: dict[str, Any] | None = None) -> CanonicalRecord:
        hints = hints or {}
        try:
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as e:
            raise AdapterError(f"Unable to decode ASS file: {e}", raw_content=raw_bytes.decode("utf-8", errors="replace"))

        language = hints.get("language", "unknown")
        cues = self._parse_ass(text, language)
        return cues

    def _parse_ass(self, text: str, language: str) -> list[SubtitleCue]:
        cues = []
        for i, match in enumerate(self.ASS_PATTERN.finditer(text), 1):
            start_raw = match.group(1)
            end_raw = match.group(2)
            cue_text = match.group(3).strip().replace("\\N", " ").replace("\\n", " ")

            try:
                start = parse_timecode(start_raw, TimecodeFormat.CENTISECONDS)
                end = parse_timecode(end_raw, TimecodeFormat.CENTISECONDS)
            except ValueError as e:
                raise AdapterError(f"Invalid timecode in ASS at cue {i}: {e}")

            cues.append(SubtitleCue(
                index=i,
                start=start,
                end=end,
                text=cue_text,
                language=language
            ))

        if not cues:
            raise AdapterError("No valid subtitle cues found in ASS file")

        return cues