"""Deterministic rule evaluator."""

from __future__ import annotations

from typing import Any, Optional
from dataclasses import dataclass
from enum import Enum

from src.models.rule import Rule, RuleScope, RuleEffect, RuleCondition
from src.models.segment import Segment
from src.models.scene import Scene, Entity
from src.models.timecode import Timecode


class Verdict(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE = "require"
    LIMIT = "limit"
    NOT_APPLICABLE = "not_applicable"


@dataclass
class EvaluationResult:
    """Result of evaluating a rule against a segment."""
    rule_id: str
    verdict: Verdict
    matched: bool
    details: str
    limit_value: Optional[Any] = None  # For LIMIT effect


class RuleEvaluator:
    """Deterministic evaluator for compiled rules."""

    OPERATORS = {
        "eq": lambda a, b: a == b,
        "ne": lambda a, b: a != b,
        "gt": lambda a, b: a > b,
        "lt": lambda a, b: a < b,
        "gte": lambda a, b: a >= b,
        "lte": lambda a, b: a <= b,
        "in": lambda a, b: a in b if isinstance(b, (list, set, tuple)) else a == b,
        "not_in": lambda a, b: a not in b if isinstance(b, (list, set, tuple)) else a != b,
        "contains": lambda a, b: b in a if isinstance(a, (list, set, tuple, str)) else False,
        "before": lambda a, b: a < b,
        "after": lambda a, b: a > b,
    }

    def __init__(self):
        pass

    def evaluate(
        self, 
        rule: Rule, 
        segment: Segment, 
        scene: Scene,
        entities: dict[str, Entity],
        context: dict[str, Any]
    ) -> EvaluationResult:
        """Evaluate a single rule against a segment with context."""
        # Check if rule applies to this segment
        if not self._scope_matches(rule.scope, segment, scene, entities, context):
            return EvaluationResult(
                rule_id=rule.rule_id,
                verdict=Verdict.NOT_APPLICABLE,
                matched=False,
                details=f"Rule scope {rule.scope} does not match segment context"
            )

        # Evaluate all conditions
        all_matched = True
        failed_conditions = []
        
        for condition in rule.conditions:
            if not self._evaluate_condition(condition, segment, scene, entities, context):
                all_matched = False
                failed_conditions.append(f"{condition.field} {condition.operator} {condition.value}")

        if not all_matched:
            return EvaluationResult(
                rule_id=rule.rule_id,
                verdict=Verdict.NOT_APPLICABLE,
                matched=False,
                details=f"Conditions not met: {'; '.join(failed_conditions)}"
            )

        # Rule matches - return its effect
        return EvaluationResult(
            rule_id=rule.rule_id,
            verdict=Verdict(rule.effect.value),
            matched=True,
            details=f"All conditions matched; effect: {rule.effect.value}",
            limit_value=self._extract_limit_value(rule) if rule.effect == RuleEffect.LIMIT else None,
        )

    def _scope_matches(
        self, 
        scope: RuleScope, 
        segment: Segment, 
        scene: Scene,
        entities: dict[str, Entity],
        context: dict[str, Any]
    ) -> bool:
        """Check if rule scope is relevant to this segment."""
        scope_fields = {
            RuleScope.SCENE: ["scene_id", "video"],
            RuleScope.ACTOR: ["actor_id", "entities"],
            RuleScope.VOICE: ["voice_actor", "audio"],
            RuleScope.MUSIC_TRACK: ["music_track", "audio"],
            RuleScope.TERRITORY: ["territory", "audience_territories"],
            RuleScope.AUDIENCE: ["audience_id", "target_audience"],
            RuleScope.TIME_WINDOW: ["usage_date", "current_date"],
            RuleScope.DIALOGUE: ["subtitle", "dialogue"],
            RuleScope.VISUAL_CONTENT: ["content_tags", "scene_tags"],
        }
        return scope in scope_fields

    def _evaluate_condition(
        self, 
        condition: RuleCondition, 
        segment: Segment, 
        scene: Scene,
        entities: dict[str, Entity],
        context: dict[str, Any]
    ) -> bool:
        """Evaluate a single condition."""
        operator_fn = self.OPERATORS.get(condition.operator)
        if not operator_fn:
            return False

        # Get the field value from context
        field_value = self._get_field_value(condition.field, segment, scene, entities, context)
        if field_value is None:
            return False

        try:
            return operator_fn(field_value, condition.value)
        except Exception:
            return False

    def _get_field_value(
        self, 
        field: str, 
        segment: Segment, 
        scene: Scene,
        entities: dict[str, Entity],
        context: dict[str, Any]
    ) -> Any:
        """Extract field value from segment/scene/entities/context."""
        # Direct segment fields
        if field == "scene_id" or field == "video":
            return segment.video
        if field == "audio" or field == "music_track":
            return segment.audio
        if field == "subtitle":
            return segment.subtitle
        if field == "segment_id":
            return segment.segment_id

        # Scene fields
        if field == "scene_tags" or field == "content_tags":
            return scene.content_tags
        if field == "entities":
            return scene.entities

        # Entity fields - need to resolve from scene entities
        if field == "actor_id":
            actors = [e for e in scene.entities if e in entities and entities[e].entity_type.value == "character"]
            return actors[0] if actors else None

        # Context fields
        if field in context:
            return context[field]

        # Audience context
        if field == "audience_id":
            return context.get("audience_id")
        if field == "territory" or field == "audience_territories":
            return context.get("territories", [])
        if field == "audience_age_min":
            age_range = context.get("age_range")
            return age_range[0] if age_range else None
        if field == "audience_age_max":
            age_range = context.get("age_range")
            return age_range[1] if age_range else None
        if field == "usage_date":
            return context.get("current_date")
        if field == "current_date":
            return context.get("current_date")

        return None

    def _extract_limit_value(self, rule: Rule) -> Any:
        """Extract limit value from LIMIT rule conditions."""
        for condition in rule.conditions:
            if condition.field in ("max_duration", "max_seconds", "limit"):
                return condition.value
        return None

    def evaluate_all(
        self, 
        rules: list[Rule], 
        segment: Segment, 
        scene: Scene,
        entities: dict[str, Entity],
        context: dict[str, Any]
    ) -> list[EvaluationResult]:
        """Evaluate all rules against a segment."""
        results = []
        for rule in rules:
            result = self.evaluate(rule, segment, scene, entities, context)
            if result.matched:
                results.append(result)
        return results

    def check_deny(self, results: list[EvaluationResult]) -> bool:
        """Check if any rule denies the segment."""
        return any(r.verdict == Verdict.DENY for r in results)

    def check_allow(self, results: list[EvaluationResult]) -> bool:
        """Check if any rule explicitly allows the segment."""
        return any(r.verdict == Verdict.ALLOW for r in results)

    def get_limits(self, results: list[EvaluationResult]) -> dict[str, Any]:
        """Extract all limit values from matching rules."""
        limits = {}
        for r in results:
            if r.verdict == Verdict.LIMIT and r.limit_value is not None:
                limits[r.rule_id] = r.limit_value
        return limits