"""CSV adapter for structured data."""

from __future__ import annotations

import csv
import io
from typing import Any
from pathlib import Path

from src.adapters.base import AdapterBase, AdapterError, CanonicalRecord
from src.models.timecode import Timecode, parse_timecode
from src.models.scene import Scene, Entity
from src.models.story_map import StoryMap, StoryEvent, EmotionalBeat
from src.models.spoiler import SpoilerFact
from src.models.rule import Rule, RuleCondition, RuleScope, RuleEffect
from src.models.audience import AudienceDefinition, AudiencePromise
from src.models.segment import Segment
from src.models.trailer import TrailerPlan, TrailerValidation, ValidationCheck, ValidationStatus


class CSVAdapter(AdapterBase):
    """Adapter for CSV formatted input files."""

    supported_extensions = [".csv"]
    supported_mime_types = ["text/csv", "application/csv"]

    def parse(self, raw_bytes: bytes, hints: dict[str, Any] | None = None) -> CanonicalRecord:
        hints = hints or {}
        try:
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = raw_bytes.decode("latin-1")
            except UnicodeDecodeError as e:
                raise AdapterError(f"Unable to decode CSV file: {e}", raw_content=raw_bytes.decode("utf-8", errors="replace"))

        target_type = hints.get("target_type", "auto")
        delimiter = hints.get("delimiter", ",")
        has_header = hints.get("has_header", True)

        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter) if has_header else csv.reader(io.StringIO(text), delimiter=delimiter)
        rows = list(reader)

        if not rows:
            raise AdapterError("CSV file is empty")

        if target_type == "auto":
            # Try to infer from column names
            first_row = rows[0] if has_header else {}
            if isinstance(first_row, dict):
                cols = set(first_row.keys())
                if {"scene_id", "timecode_in", "timecode_out"}.issubset(cols):
                    return self._parse_scenes(rows)
                if {"entity_id", "entity_type", "name"}.issubset(cols):
                    return self._parse_entities(rows)
                if {"fact_id", "fact_type"}.issubset(cols):
                    return self._parse_spoiler_facts(rows)
                if {"rule_id", "scope", "effect"}.issubset(cols):
                    return self._parse_rules(rows)
                if {"audience_id", "goal"}.issubset(cols):
                    return self._parse_audience_definitions(rows)

        return self._parse_by_type(rows, target_type, has_header)

    def _parse_by_type(self, rows: list, target_type: str, has_header: bool) -> CanonicalRecord:
        parsers = {
            "scenes": self._parse_scenes,
            "entities": self._parse_entities,
            "spoiler_facts": self._parse_spoiler_facts,
            "rules": self._parse_rules,
            "audience_definitions": self._parse_audience_definitions,
        }
        if target_type not in parsers:
            raise AdapterError(f"Unknown target_type for CSV: {target_type}")
        return parsers[target_type](rows)

    def _parse_timecode(self, value: str) -> Timecode:
        return parse_timecode(value.strip())

    def _parse_scenes(self, rows: list) -> list[Scene]:
        scenes = []
        for row in rows:
            if isinstance(row, list):
                # No header - assume order: scene_id, timecode_in, timecode_out, duration_ms, description, entities, content_tags, emotional_tone, dialogue_ids, is_characterised, trust_level
                row = dict(zip(
                    ["scene_id", "timecode_in", "timecode_out", "duration_ms", "description", "entities", "content_tags", "emotional_tone", "dialogue_ids", "is_characterised", "trust_level"],
                    row
                ))
            scenes.append(Scene(
                scene_id=row["scene_id"],
                timecode_in=self._parse_timecode(row["timecode_in"]),
                timecode_out=self._parse_timecode(row["timecode_out"]),
                duration_ms=int(row.get("duration_ms", 0)),
                description=row.get("description") or None,
                entities=row.get("entities", "").split(";") if row.get("entities") else [],
                content_tags=row.get("content_tags", "").split(";") if row.get("content_tags") else [],
                emotional_tone=row.get("emotional_tone") or None,
                dialogue_ids=row.get("dialogue_ids", "").split(";") if row.get("dialogue_ids") else [],
                is_characterised=row.get("is_characterised", "true").lower() == "true",
                trust_level=row.get("trust_level", "untrusted"),
            ))
        return scenes

    def _parse_entities(self, rows: list) -> list[Entity]:
        entities = []
        for row in rows:
            if isinstance(row, list):
                row = dict(zip(
                    ["entity_id", "entity_type", "name", "aliases", "first_appearance_scene", "relationships"],
                    row
                ))
            entities.append(Entity(
                entity_id=row["entity_id"],
                entity_type=row["entity_type"],
                name=row["name"],
                aliases=row.get("aliases", "").split(";") if row.get("aliases") else [],
                first_appearance_scene=row.get("first_appearance_scene") or None,
                relationships=[],  # Complex to parse from CSV, skip
            ))
        return entities

    def _parse_spoiler_facts(self, rows: list) -> list[SpoilerFact]:
        facts = []
        for row in rows:
            if isinstance(row, list):
                row = dict(zip(
                    ["fact_id", "fact_type", "description", "involved_entities", "involved_scenes", "reveal_boundary", "evidence", "confidence"],
                    row
                ))
            facts.append(SpoilerFact(
                fact_id=row["fact_id"],
                fact_type=row["fact_type"],
                description=row["description"],
                involved_entities=row.get("involved_entities", "").split(";") if row.get("involved_entities") else [],
                involved_scenes=row.get("involved_scenes", "").split(";") if row.get("involved_scenes") else [],
                reveal_boundary=float(row["reveal_boundary"]),
                evidence=row.get("evidence", "").split(";") if row.get("evidence") else [],
                confidence=float(row["confidence"]),
            ))
        return facts

    def _parse_rules(self, rows: list) -> list[Rule]:
        rules = []
        for row in rows:
            if isinstance(row, list):
                row = dict(zip(
                    ["rule_id", "source_contract_id", "source_policy_id", "source_span", "scope", "effect", "conditions", "confidence", "is_ambiguous", "human_approved"],
                    row
                ))
            # Conditions stored as JSON string
            import json
            conditions = json.loads(row.get("conditions", "[]")) if row.get("conditions") else []
            rules.append(Rule(
                rule_id=row["rule_id"],
                source_contract_id=row.get("source_contract_id") or None,
                source_policy_id=row.get("source_policy_id") or None,
                source_span=row["source_span"],
                scope=RuleScope(row["scope"]),
                effect=RuleEffect(row["effect"]),
                conditions=[RuleCondition(**c) for c in conditions],
                confidence=float(row.get("confidence", 1.0)),
                is_ambiguous=row.get("is_ambiguous", "false").lower() == "true",
                human_approved=row.get("human_approved", "false").lower() == "true",
            ))
        return rules

    def _parse_audience_definitions(self, rows: list) -> list[AudienceDefinition]:
        audiences = []
        for row in rows:
            if isinstance(row, list):
                row = dict(zip(
                    ["audience_id", "name", "description", "goal", "special_care", "rating_policy_ids", "age_range", "territories", "languages", "preferences", "engagement_patterns"],
                    row
                ))
            import json
            audiences.append(AudienceDefinition(
                audience_id=row["audience_id"],
                name=row["name"],
                description=row["description"],
                goal=row["goal"],
                special_care=row.get("special_care", "").split(";") if row.get("special_care") else [],
                rating_policy_ids=row.get("rating_policy_ids", "").split(";") if row.get("rating_policy_ids") else [],
                age_range=tuple(map(int, row["age_range"].split("-"))) if row.get("age_range") else None,
                territories=row.get("territories", "").split(";") if row.get("territories") else [],
                languages=row.get("languages", "").split(";") if row.get("languages") else [],
                preferences=json.loads(row.get("preferences", "{}")) if row.get("preferences") else {},
                engagement_patterns=json.loads(row.get("engagement_patterns", "{}")) if row.get("engagement_patterns") else {},
            ))
        return audiences