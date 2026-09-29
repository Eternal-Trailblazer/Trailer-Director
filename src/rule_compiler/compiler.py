"""Rule compiler for extracting rules from policies and contracts."""

from __future__ import annotations

import json
import uuid
from typing import Any, Optional
from dataclasses import dataclass

from src.models.rule import Rule, RuleScope, RuleEffect, RuleCondition
from src.models.capability import CapabilityReport
from src.quarantine import QuarantineGate
from src.providers.base import ModelProvider, ModelCapabilities


@dataclass
class ExtractedRule:
    """Rule extracted from LLM with metadata."""
    rule: Rule
    source_text: str
    extraction_confidence: float
    ambiguous_spans: list[str]


class RuleCompiler:
    """Compiles natural language policies/contracts into deterministic rules."""

    def __init__(self, model_provider: ModelProvider, quarantine: QuarantineGate):
        self.model_provider = model_provider
        self.quarantine = quarantine

    def compile_policies(self, policy_texts: list[tuple[str, str]], capability_report: CapabilityReport) -> list[Rule]:
        """Compile rating policies into rules.
        
        Args:
            policy_texts: List of (policy_id, policy_text) tuples
            capability_report: Report to update with warnings
            
        Returns:
            List of compiled rules
        """
        all_rules = []
        for policy_id, text in policy_texts:
            rules = self._extract_rules_from_text(text, policy_id, "policy", capability_report)
            all_rules.extend(rules)
        return all_rules

    def compile_contracts(self, contract_texts: list[tuple[str, str]], capability_report: CapabilityReport) -> list[Rule]:
        """Compile contracts into rules.
        
        Args:
            contract_texts: List of (contract_id, contract_text) tuples
            capability_report: Report to update with warnings
            
        Returns:
            List of compiled rules
        """
        all_rules = []
        for contract_id, text in contract_texts:
            rules = self._extract_rules_from_text(text, contract_id, "contract", capability_report)
            all_rules.extend(rules)
        return all_rules

    def _extract_rules_from_text(
        self, 
        text: str, 
        source_id: str, 
        source_type: str,
        capability_report: CapabilityReport
    ) -> list[Rule]:
        """Extract rules from a single policy/contract text."""
        # Sanitise input
        sanitised = self.quarantine.sanitise(text, f"{source_type}:{source_id}")
        if sanitised.was_modified:
            capability_report.warnings.append(f"Injection detected in {source_type} {source_id}")

        # Use LLM to extract structured rules
        prompt = self._build_extraction_prompt(sanitised.clean_text, source_type)
        
        try:
            response = self.model_provider.complete(
                messages=[{"role": "user", "content": prompt}],
                schema=RuleExtractionResponse,
                budget_tag=f"rule_extraction_{source_type}"
            )
            extraction = response.parsed
        except Exception as e:
            capability_report.warnings.append(f"Rule extraction failed for {source_id}: {e}")
            # Conservative fallback: deny all
            return [self._create_conservative_deny_rule(source_id, source_type, text)]

        rules = []
        for extracted in extraction.rules:
            rule = self._build_rule(extracted, source_id, source_type, sanitised.clean_text)
            rules.append(rule)

        return rules

    def _build_extraction_prompt(self, text: str, source_type: str) -> str:
        return f"""Extract access control rules from this {source_type} text. 
Output as JSON matching the RuleExtractionResponse schema.

Rules should specify:
- scope: one of [scene, actor, voice, music_track, territory, audience, time_window, dialogue, visual_content]
- effect: one of [allow, deny, require, limit]
- conditions: list of {{field, operator, value}} where operator is one of [eq, ne, gt, lt, gte, lte, in, not_in, contains, before, after]

Be conservative: if a clause is ambiguous, mark it as ambiguous and set effect to DENY.
Include the exact source span for each rule.

{self.quarantine.wrap_for_llm(text)}"""

    def _build_rule(self, extracted: "ExtractedRuleData", source_id: str, source_type: str, source_text: str) -> Rule:
        rule_id = f"{source_type}-{source_id}-{uuid.uuid4().hex[:8]}"
        
        if source_type == "policy":
            source_policy_id = source_id
            source_contract_id = None
        else:
            source_policy_id = None
            source_contract_id = source_id

        conditions = [
            RuleCondition(field=c.field, operator=c.operator, value=c.value)
            for c in extracted.conditions
        ]

        return Rule(
            rule_id=rule_id,
            source_contract_id=source_contract_id,
            source_policy_id=source_policy_id,
            source_span=extracted.source_span,
            scope=RuleScope(extracted.scope),
            effect=RuleEffect(extracted.effect),
            conditions=conditions,
            confidence=extracted.confidence,
            is_ambiguous=extracted.is_ambiguous,
            human_approved=False,
        )

    def _create_conservative_deny_rule(self, source_id: str, source_type: str, text: str) -> Rule:
        """Create a conservative deny-all rule when extraction fails."""
        rule_id = f"{source_type}-{source_id}-deny-all-{uuid.uuid4().hex[:8]}"
        return Rule(
            rule_id=rule_id,
            source_contract_id=source_id if source_type == "contract" else None,
            source_policy_id=source_id if source_type == "policy" else None,
            source_span=text[:500],
            scope=RuleScope.SCENE,
            effect=RuleEffect.DENY,
            conditions=[],
            confidence=0.1,
            is_ambiguous=True,
            human_approved=False,
        )


# Schema for LLM structured output
class RuleExtractionResponse:
    """Schema for rule extraction response."""
    pass


class ExtractedRuleData:
    """Individual extracted rule data."""
    scope: str
    effect: str
    conditions: list[dict]
    source_span: str
    confidence: float
    is_ambiguous: bool


# We'll use a simpler approach with function calling / structured output
# The actual schema will be defined when calling the model provider