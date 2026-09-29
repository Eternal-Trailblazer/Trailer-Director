"""Plain text adapter for unstructured text input."""

from __future__ import annotations

import re
from typing import Any
from pathlib import Path

from src.adapters.base import AdapterBase, AdapterError, CanonicalRecord
from src.models.scene import Scene
from src.models.timecode import Timecode, parse_timecode, TimecodeFormat


class PlainTextAdapter(AdapterBase):
    """Adapter for plain text files with scene descriptions."""

    supported_extensions = [".txt", ".md"]
    supported_mime_types = ["text/plain", "text/markdown"]

    # Pattern: Scene ID: description
    SCENE_PATTERN = re.compile(
        r"^(?:Scene\s+)?(\w+)\s*[:|-]\s*(.+)$",
        re.MULTILINE | re.IGNORECASE
    )

    # Pattern with timecodes: Scene ID [HH:MM:SS - HH:MM:SS]: description
    SCENE_TC_PATTERN = re.compile(
        r"^(?:Scene\s+)?(\w+)\s*[\[\(]\s*(\d{2}:\d{2}:\d{2}[.,:;]\d{2,3})\s*[-–—]\s*(\d{2}:\d{2}:\d{2}[.,:;]\d{2,3})\s*[\]\)]\s*[:|-]?\s*(.+)$",
        re.MULTILINE | re.IGNORECASE
    )

    def parse(self, raw_bytes: bytes, hints: dict[str, Any] | None = None) -> CanonicalRecord:
        hints = hints or {}
        try:
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = raw_bytes.decode("latin-1")
            except UnicodeDecodeError as e:
                raise AdapterError(f"Unable to decode text file: {e}", raw_content=raw_bytes.decode("utf-8", errors="replace"))

        target_type = hints.get("target_type", "scene_descriptions")
        return self._parse_by_type(text, target_type, hints)

    def _parse_by_type(self, text: str, target_type: str, hints: dict[str, Any]) -> CanonicalRecord:
        if target_type == "scene_descriptions":
            return self._parse_scene_descriptions(text, hints)
        raise AdapterError(f"Unknown target_type for plain text: {target_type}")

    def _parse_scene_descriptions(self, text: str, hints: dict[str, Any]) -> list[Scene]:
        """Parse scene descriptions from plain text."""
        scenes = []
        frame_rate = hints.get("frame_rate", 24.0)

        # Try timecode pattern first
        for match in self.SCENE_TC_PATTERN.finditer(text):
            scene_id = match.group(1)
            tc_in_raw = match.group(2)
            tc_out_raw = match.group(3)
            description = match.group(4).strip()

            try:
                tc_in = parse_timecode(tc_in_raw)
                tc_out = parse_timecode(tc_out_raw)
            except ValueError as e:
                # Fallback: create timecodes from hints
                tc_in = Timecode(
                    raw=tc_in_raw, hours=0, minutes=0, seconds=0, fractional=0,
                    source_format=TimecodeFormat.MILLISECONDS, normalised_ms=0
                )
                tc_out = Timecode(
                    raw=tc_out_raw, hours=0, minutes=0, seconds=0, fractional=0,
                    source_format=TimecodeFormat.MILLISECONDS, normalised_ms=0
                )

            duration = tc_out.normalised_ms - tc_in.normalised_ms
            scenes.append(Scene(
                scene_id=scene_id,
                timecode_in=tc_in,
                timecode_out=tc_out,
                duration_ms=max(0, duration),
                description=description,
                entities=[],
                content_tags=[],
                is_characterised=True,
                trust_level="untrusted",
            ))

        # If no timecode patterns found, try simple pattern
        if not scenes:
            for match in self.SCENE_PATTERN.finditer(text):
                scene_id = match.group(1)
                description = match.group(2).strip()

                # Assign sequential timecodes based on hints
                base_ms = hints.get("base_timecode_ms", 0)
                scene_duration = hints.get("default_scene_duration_ms", 30000)
                idx = len(scenes)
                tc_in = Timecode(
                    raw=f"{idx * scene_duration}ms", hours=0, minutes=0, seconds=0, fractional=0,
                    source_format=TimecodeFormat.MILLISECONDS, normalised_ms=base_ms + idx * scene_duration
                )
                tc_out = Timecode(
                    raw=f"{(idx + 1) * scene_duration}ms", hours=0, minutes=0, seconds=0, fractional=0,
                    source_format=TimecodeFormat.MILLISECONDS, normalised_ms=base_ms + (idx + 1) * scene_duration
                )

                scenes.append(Scene(
                    scene_id=scene_id,
                    timecode_in=tc_in,
                    timecode_out=tc_out,
                    duration_ms=scene_duration,
                    description=description,
                    entities=[],
                    content_tags=[],
                    is_characterised=True,
                    trust_level="untrusted",
                ))

        if not scenes:
            # Last resort: treat entire text as one scene
            scenes.append(Scene(
                scene_id="scene_01",
                timecode_in=Timecode(
                    raw="0ms", hours=0, minutes=0, seconds=0, fractional=0,
                    source_format=TimecodeFormat.MILLISECONDS, normalised_ms=0
                ),
                timecode_out=Timecode(
                    raw="30000ms", hours=0, minutes=0, seconds=0, fractional=0,
                    source_format=TimecodeFormat.MILLISECONDS, normalised_ms=30000
                ),
                duration_ms=30000,
                description=text.strip(),
                entities=[],
                content_tags=[],
                is_characterised=True,
                trust_level="untrusted",
            ))

        return scenes