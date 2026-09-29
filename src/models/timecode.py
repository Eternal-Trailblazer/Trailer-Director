"""Timecode parsing, normalisation, and conversion."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class TimecodeFormat(str, Enum):
    MILLISECONDS = "ms"          # HH:MM:SS.mmm
    FRAMES = "frames"            # HH:MM:SS:FF
    DROP_FRAME = "drop_frame"    # HH:MM:SS;FF
    CENTISECONDS = "cs"          # H:MM:SS.cc


@dataclass
class ParsedTimecode:
    """Intermediate parsed timecode before normalisation."""
    hours: int
    minutes: int
    seconds: int
    fractional: int
    format: TimecodeFormat
    frame_rate: Optional[float] = None


class Timecode(BaseModel):
    """Canonical timecode with normalised millisecond representation."""
    
    raw: str
    hours: int
    minutes: int
    seconds: int
    fractional: int
    source_format: TimecodeFormat
    source_frame_rate: Optional[float] = None
    normalised_ms: int

    @field_validator("normalised_ms")
    @classmethod
    def must_be_nonnegative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Timecode cannot be negative")
        return v

    @field_validator("hours", "minutes", "seconds", "fractional")
    @classmethod
    def must_be_nonnegative_fields(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Timecode components cannot be negative")
        return v

    @model_validator(mode="after")
    def validate_time_ranges(self) -> "Timecode":
        if self.minutes >= 60:
            raise ValueError("Minutes must be < 60")
        if self.seconds >= 60:
            raise ValueError("Seconds must be < 60")
        return self

    def to_srt(self) -> str:
        """Convert to SRT format HH:MM:SS,mmm"""
        h = self.normalised_ms // 3600000
        m = (self.normalised_ms % 3600000) // 60000
        s = (self.normalised_ms % 60000) // 1000
        ms = self.normalised_ms % 1000
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def to_vtt(self) -> str:
        """Convert to VTT format HH:MM:SS.mmm"""
        h = self.normalised_ms // 3600000
        m = (self.normalised_ms % 3600000) // 60000
        s = (self.normalised_ms % 60000) // 1000
        ms = self.normalised_ms % 1000
        return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

    def to_frames(self, frame_rate: float) -> str:
        """Convert to frame-based format HH:MM:SS:FF"""
        total_frames = round(self.normalised_ms * frame_rate / 1000)
        h = total_frames // (3600 * frame_rate)
        m = (total_frames % (3600 * frame_rate)) // (60 * frame_rate)
        s = (total_frames % (60 * frame_rate)) // frame_rate
        f = total_frames % frame_rate
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d}:{int(f):02d}"

    def __lt__(self, other: "Timecode") -> bool:
        return self.normalised_ms < other.normalised_ms

    def __le__(self, other: "Timecode") -> bool:
        return self.normalised_ms <= other.normalised_ms

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Timecode):
            return NotImplemented
        return self.normalised_ms == other.normalised_ms

    def __sub__(self, other: "Timecode") -> int:
        """Return difference in milliseconds."""
        return self.normalised_ms - other.normalised_ms


# --- Parsing functions ---

SRT_PATTERN = re.compile(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})")
VTT_PATTERN = re.compile(r"(\d{2}):(\d{2}):(\d{2})\.(\d{3})")
FRAMES_PATTERN = re.compile(r"(\d{2}):(\d{2}):(\d{2}):(\d{2})")
DROP_FRAME_PATTERN = re.compile(r"(\d{2}):(\d{2}):(\d{2});(\d{2})")
ASS_PATTERN = re.compile(r"(\d):(\d{2}):(\d{2})\.(\d{2})")


def parse_timecode(raw: str, hint_format: Optional[TimecodeFormat] = None, frame_rate: Optional[float] = None) -> Timecode:
    """Parse a timecode string into a canonical Timecode object."""
    raw = raw.strip()
    
    # Try each format
    for pattern, fmt in [
        (SRT_PATTERN, TimecodeFormat.MILLISECONDS),
        (VTT_PATTERN, TimecodeFormat.MILLISECONDS),
        (FRAMES_PATTERN, TimecodeFormat.FRAMES),
        (DROP_FRAME_PATTERN, TimecodeFormat.DROP_FRAME),
        (ASS_PATTERN, TimecodeFormat.CENTISECONDS),
    ]:
        match = pattern.fullmatch(raw)
        if match:
            return _parse_matched(match, fmt, frame_rate, raw)
    
    # If hint provided, try to parse with that format
    if hint_format:
        return _parse_with_hint(raw, hint_format, frame_rate)
    
    raise ValueError(f"Unable to parse timecode: {raw}")


def _parse_matched(match: re.Match, fmt: TimecodeFormat, frame_rate: Optional[float], raw: str) -> Timecode:
    groups = match.groups()
    
    if fmt == TimecodeFormat.MILLISECONDS:
        h, m, s, ms = map(int, groups)
        normalised = ((h * 3600 + m * 60 + s) * 1000) + ms
        return Timecode(
            raw=raw, hours=h, minutes=m, seconds=s, fractional=ms,
            source_format=fmt, normalised_ms=normalised
        )
    
    elif fmt == TimecodeFormat.FRAMES:
        if frame_rate is None:
            raise ValueError("Frame rate required for frame-based timecode")
        h, m, s, f = map(int, groups)
        total_frames = int((h * 3600 + m * 60 + s) * frame_rate + f)
        normalised = round(total_frames * 1000 / frame_rate)
        return Timecode(
            raw=raw, hours=h, minutes=m, seconds=s, fractional=f,
            source_format=fmt, source_frame_rate=frame_rate, normalised_ms=normalised
        )
    
    elif fmt == TimecodeFormat.DROP_FRAME:
        if frame_rate is None:
            raise ValueError("Frame rate required for drop-frame timecode")
        # SMPTE drop-frame conversion (29.97 DF)
        h, m, s, f = map(int, groups)
        # Drop-frame: drop 2 frames every minute except every 10th minute
        total_minutes = h * 60 + m
        dropped_frames = 2 * (total_minutes - total_minutes // 10)
        total_frames = int((h * 3600 + m * 60 + s) * 30 + f - dropped_frames)
        normalised = round(total_frames * 1000 / 30)
        return Timecode(
            raw=raw, hours=h, minutes=m, seconds=s, fractional=f,
            source_format=fmt, source_frame_rate=frame_rate, normalised_ms=normalised
        )
    
    elif fmt == TimecodeFormat.CENTISECONDS:
        h, m, s, cs = map(int, groups)
        normalised = ((h * 3600 + m * 60 + s) * 1000) + (cs * 10)
        return Timecode(
            raw=raw, hours=h, minutes=m, seconds=s, fractional=cs,
            source_format=fmt, normalised_ms=normalised
        )
    
    raise ValueError(f"Unknown format: {fmt}")


def _parse_with_hint(raw: str, hint: TimecodeFormat, frame_rate: Optional[float]) -> Timecode:
    """Parse with a specific format hint."""
    if hint == TimecodeFormat.MILLISECONDS:
        parts = raw.replace(",", ".").split(":")
        if len(parts) == 3:
            h, m, s_ms = parts
            s, ms = s_ms.split(".")
            return Timecode(
                raw=raw, hours=int(h), minutes=int(m), seconds=int(s), fractional=int(ms.ljust(3, "0")[:3]),
                source_format=hint, normalised_ms=((int(h) * 3600 + int(m) * 60 + int(s)) * 1000) + int(ms.ljust(3, "0")[:3])
            )
    elif hint in (TimecodeFormat.FRAMES, TimecodeFormat.DROP_FRAME):
        if frame_rate is None:
            raise ValueError("Frame rate required for frame-based timecode")
        parts = raw.replace(";", ":").split(":")
        if len(parts) == 4:
            h, m, s, f = map(int, parts)
            if hint == TimecodeFormat.FRAMES:
                total_frames = int((h * 3600 + m * 60 + s) * frame_rate + f)
                normalised = round(total_frames * 1000 / frame_rate)
            else:
                total_minutes = h * 60 + m
                dropped_frames = 2 * (total_minutes - total_minutes // 10)
                total_frames = int((h * 3600 + m * 60 + s) * 30 + f - dropped_frames)
                normalised = round(total_frames * 1000 / 30)
            return Timecode(
                raw=raw, hours=h, minutes=m, seconds=s, fractional=f,
                source_format=hint, source_frame_rate=frame_rate, normalised_ms=normalised
            )
    elif hint == TimecodeFormat.CENTISECONDS:
        parts = raw.split(":")
        if len(parts) == 3:
            h, m, s_cs = parts
            s, cs = s_cs.split(".")
            return Timecode(
                raw=raw, hours=int(h), minutes=int(m), seconds=int(s), fractional=int(cs.ljust(2, "0")[:2]),
                source_format=hint, normalised_ms=((int(h) * 3600 + int(m) * 60 + int(s)) * 1000) + (int(cs.ljust(2, "0")[:2]) * 10)
            )
    raise ValueError(f"Unable to parse {raw} with hint {hint}")


def ms_to_timecode(ms: int, fmt: TimecodeFormat = TimecodeFormat.MILLISECONDS, frame_rate: Optional[float] = None) -> Timecode:
    """Create a Timecode from milliseconds."""
    if ms < 0:
        raise ValueError("Milliseconds cannot be negative")
    h = ms // 3600000
    m = (ms % 3600000) // 60000
    s = (ms % 60000) // 1000
    frac = ms % 1000
    
    if fmt == TimecodeFormat.MILLISECONDS:
        raw = f"{h:02d}:{m:02d}:{s:02d}.{frac:03d}"
    elif fmt == TimecodeFormat.FRAMES:
        if frame_rate is None:
            raise ValueError("Frame rate required")
        total_frames = round(ms * frame_rate / 1000)
        f = total_frames % frame_rate
        raw = f"{h:02d}:{m:02d}:{s:02d}:{int(f):02d}"
    elif fmt == TimecodeFormat.DROP_FRAME:
        if frame_rate is None:
            raise ValueError("Frame rate required")
        # Approximate reverse of drop-frame
        total_frames = round(ms * 30 / 1000)
        total_minutes = h * 60 + m
        dropped_frames = 2 * (total_minutes - total_minutes // 10)
        adjusted = total_frames + dropped_frames
        f = adjusted % 30
        raw = f"{h:02d}:{m:02d}:{s:02d};{f:02d}"
    elif fmt == TimecodeFormat.CENTISECONDS:
        cs = round(frac / 10)
        raw = f"{h}:{m:02d}:{s:02d}.{cs:02d}"
    else:
        raw = f"{h:02d}:{m:02d}:{s:02d}.{frac:03d}"
    
    return Timecode(
        raw=raw, hours=h, minutes=m, seconds=s, fractional=frac,
        source_format=fmt, source_frame_rate=frame_rate, normalised_ms=ms
    )