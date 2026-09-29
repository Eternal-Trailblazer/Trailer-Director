"""JSON adapter for structured data."""

from __future__ import annotations

import json
from typing import Any
from pathlib import Path

from src.adapters.base import AdapterBase, AdapterError, CanonicalRecord
from src.models.scene import Scene, Entity
from src.models.timecode import Timecode, parse_timecode
from src.models.story_map import StoryMap, StoryEvent, EmotionalBeat
from src.models.spoiler import SpoilerFact
from src.models.rule import Rule, RuleCondition, RuleScope, RuleEffect
from src.models.audience import AudienceDefinition, AudiencePromise
from src.models.segment import Segment
from src.models.trailer import TrailerPlan, TrailerValidation, ValidationCheck, ValidationStatus
from src.models.change_event import ChangeEvent, ChangeEventType
from src.models.capability import CapabilityReport
from src.models.cost import CostLedger, CostLedgerEntry
from src.models.decision_log import DecisionLogEntry
from src.models.human_approval import HumanApprovalEntry


class JSONAdapter(AdapterBase):
    """Adapter for JSON formatted input files."""

    supported_extensions = [".json"]
    supported_mime_types = ["application/json"]

    def parse(self, raw_bytes: bytes, hints: dict[str, Any] | None = None) -> CanonicalRecord:
        hints = hints or {}
        try:
            text = raw_bytes.decode("utf-8")
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise AdapterError(f"Invalid JSON: {e}", raw_content=raw_bytes.decode("utf-8", errors="replace"))
        except UnicodeDecodeError as e:
            raise AdapterError(f"Invalid UTF-8: {e}", raw_content=raw_bytes.decode("utf-8", errors="replace"))

        target_type = hints.get("target_type", "auto")
        return self._parse_by_type(data, target_type)

    def _parse_by_type(self, data: Any, target_type: str) -> CanonicalRecord:
        """Parse JSON data into the appropriate canonical model."""
        if target_type != "auto":
            return self._parse_specific(data, target_type)

        # Auto-detect based on structure
        if isinstance(data, dict):
            if "episode_id" in data and "scenes" in data:
                return self._parse_story_map(data)
            if "fact_id" in data and "fact_type" in data:
                return self._parse_spoiler_fact(data)
            if "rule_id" in data and "scope" in data:
                return self._parse_rule(data)
            if "audience_id" in data and "goal" in data:
                return self._parse_audience_definition(data)
            if "trailer_id" in data and "segments" in data:
                return self._parse_trailer_plan(data)
            if "event_id" in data and "event_type" in data:
                return self._parse_change_event(data)
        elif isinstance(data, list) and data:
            first = data[0]
            if isinstance(first, dict):
                if "scene_id" in first and "timecode_in" in first:
                    return [self._parse_scene(s) for s in data]
                if "entity_id" in first and "entity_type" in first:
                    return [self._parse_entity(e) for e in data]
                if "fact_id" in first:
                    return [self._parse_spoiler_fact(s) for s in data]
                if "rule_id" in first:
                    return [self._parse_rule(r) for r in data]
                if "audience_id" in first:
                    return [self._parse_audience_definition(a) for a in data]

        raise AdapterError(f"Cannot auto-detect JSON structure for type: {target_type}")

    def _parse_specific(self, data: dict, target_type: str) -> CanonicalRecord:
        parsers = {
            "story_map": self._parse_story_map,
            "scene": self._parse_scene,
            "entity": self._parse_entity,
            "spoiler_fact": self._parse_spoiler_fact,
            "rule": self._parse_rule,
            "audience_definition": self._parse_audience_definition,
            "audience_promise": self._parse_audience_promise,
            "segment": self._parse_segment,
            "trailer_plan": self._parse_trailer_plan,
            "change_event": self._parse_change_event,
            "capability_report": self._parse_capability_report,
            "cost_ledger": self._parse_cost_ledger,
            "decision_log": self._parse_decision_log,
            "human_approval": self._parse_human_approval,
        }
        if target_type not in parsers:
            raise AdapterError(f"Unknown target_type: {target_type}")
        return parsers[target_type](data)

    def _parse_timecode(self, tc_data: dict | str) -> Timecode:
        if isinstance(tc_data, str):
            return parse_timecode(tc_data)
        return Timecode(**tc_data)

    def _parse_scene(self, data: dict) -> Scene:
        return Scene(
            scene_id=data["scene_id"],
            timecode_in=self._parse_timecode(data["timecode_in"]),
            timecode_out=self._parse_timecode(data["timecode_out"]),
            duration_ms=data.get("duration_ms", 0),
            description=data.get("description"),
            entities=data.get("entities", []),
            content_tags=data.get("content_tags", []),
            emotional_tone=data.get("emotional_tone"),
            dialogue_ids=data.get("dialogue_ids", []),
            is_characterised=data.get("is_characterised", True),
            trust_level=data.get("trust_level", "untrusted"),
        )

    def _parse_entity(self, data: dict) -> Entity:
        return Entity(
            entity_id=data["entity_id"],
            entity_type=data["entity_type"],
            name=data["name"],
            aliases=data.get("aliases", []),
            first_appearance_scene=data.get("first_appearance_scene"),
            relationships=[Relationship(**r) for r in data.get("relationships", [])],
        )

    def _parse_story_map(self, data: dict) -> StoryMap:
        return StoryMap(
            episode_id=data["episode_id"],
            scenes=[self._parse_scene(s) for s in data.get("scenes", [])],
            entities=[self._parse_entity(e) for e in data.get("entities", [])],
            major_events=[StoryEvent(**ev) for ev in data.get("major_events", [])],
            emotional_arc=[EmotionalBeat(**eb) for eb in data.get("emotional_arc", [])],
            total_duration_ms=data.get("total_duration_ms", 0),
            metadata=data.get("metadata", {}),
        )

    def _parse_spoiler_fact(self, data: dict) -> SpoilerFact:
        return SpoilerFact(**data)

    def _parse_rule(self, data: dict) -> Rule:
        return Rule(
            rule_id=data["rule_id"],
            source_contract_id=data.get("source_contract_id"),
            source_policy_id=data.get("source_policy_id"),
            source_span=data["source_span"],
            scope=RuleScope(data["scope"]),
            effect=RuleEffect(data["effect"]),
            conditions=[RuleCondition(**c) for c in data.get("conditions", [])],
            confidence=data.get("confidence", 1.0),
            is_ambiguous=data.get("is_ambiguous", False),
            human_approved=data.get("human_approved", False),
        )

    def _parse_audience_definition(self, data: dict) -> AudienceDefinition:
        return AudienceDefinition(**data)

    def _parse_audience_promise(self, data: dict) -> AudiencePromise:
        return AudiencePromise(**data)

    def _parse_segment(self, data: dict) -> Segment:
        return Segment(
            segment_id=data["segment_id"],
            sequence_order=data["sequence_order"],
            source_in=self._parse_timecode(data["source_in"]),
            source_out=self._parse_timecode(data["source_out"]),
            video=data["video"],
            audio=data["audio"],
            subtitle=data.get("subtitle"),
            text_card=data.get("text_card"),
            voice_over=data.get("voice_over"),
            transition=data.get("transition"),
            reason=data["reason"],
            evidence=data.get("evidence", []),
            risk_flags=data.get("risk_flags", []),
            duration_ms=data["duration_ms"],
        )

    def _parse_trailer_plan(self, data: dict) -> TrailerPlan:
        return TrailerPlan(
            trailer_id=data["trailer_id"],
            audience=data["audience"],
            audience_promise=self._parse_audience_promise(data["audience_promise"]),
            duration_seconds=data["duration_seconds"],
            segments=[self._parse_segment(s) for s in data.get("segments", [])],
            validation=TrailerValidation(**data["validation"]) if data.get("validation") else None,
            estimated_cost=data.get("estimated_cost", 0.0),
            fallback_plan=data.get("fallback_plan"),
            assumptions=data.get("assumptions", []),
            human_approvals_pending=data.get("human_approvals_pending", []),
        )

    def _parse_change_event(self, data: dict) -> ChangeEvent:
        return ChangeEvent(**data)

    def _parse_capability_report(self, data: dict) -> CapabilityReport:
        return CapabilityReport(**data)

    def _parse_cost_ledger(self, data: dict) -> CostLedger:
        return CostLedger(
            entries=[CostLedgerEntry(**e) for e in data.get("entries", [])],
            total_cost=data.get("total_cost", 0.0),
            budget_limit=data.get("budget_limit", 0.0),
            budget_remaining=data.get("budget_remaining", 0.0),
        )

    def _parse_decision_log(self, data: dict) -> DecisionLogEntry:
        return DecisionLogEntry(**data)

    def _parse_human_approval(self, data: dict) -> HumanApprovalEntry:
        return HumanApprovalEntry(**data)


# Need to import Relationship for entity parsing
from src.models.scene import Relationship