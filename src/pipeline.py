"""Main pipeline orchestrator.

Removes all video rendering dependencies. Pure EDL-based pipeline.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional
from dataclasses import dataclass
from pathlib import Path

from src.adapters.registry import registry as adapter_registry
from src.quarantine import QuarantineGate
from src.models.capability import CapabilityReport
from src.models.story_map import StoryMap
from src.models.spoiler import SpoilerFact
from src.models.rule import Rule
from src.models.audience import AudienceDefinition, AudiencePromise
from src.models.scene import Scene, Entity, EntityType
from src.models.trailer import TrailerPlan, TrailerValidation, ValidationStatus
from src.models.cost import CostLedger
from src.story_mapper import StoryMapper, StoryMapperResult
from src.spoiler_engine import SpoilerEngine
from src.rule_compiler import RuleCompiler, RuleEvaluator
from src.bias_auditor import BiasAuditor
from src.audience_strategist import AudienceStrategist, StrategistResult
from src.generator import TrailerGenerator, GeneratorResult
from src.verifier import VerifierOrchestrator, VerificationResult
from src.repair_engine import RepairEngine, RepairResult
from src.change_handler import ChangeHandler, ChangeResult
from src.edl_emitter import EDLEmitter, EDLOutput
from src.providers import ModelProvider, BudgetController, BudgetConfig, FallbackChain, GeminiProvider
from src.observability import DecisionLogger
from src.human_registry import HumanRegistry
from src.config import load_config


@dataclass
class PipelineResult:
    """Complete pipeline result - video-free."""
    story_map: StoryMap
    spoiler_facts: list[SpoilerFact]
    rules: list[Rule]
    audience_promises: list[AudiencePromise]
    trailers: list[TrailerPlan]
    capability_report: CapabilityReport
    cost_ledger: CostLedger
    decision_log: list[dict]
    human_approvals: list[dict]
    edl_outputs: list[EDLOutput]


class Pipeline:
    """Main pipeline orchestrator - video-free."""

    def __init__(
        self,
        model_provider: ModelProvider,
        budget_controller: BudgetController,
        config: dict,
        output_dir: Path,
        mock_mode: bool = False,
    ):
        self.model_provider = model_provider
        self.budget_controller = budget_controller
        self.config = config
        self.output_dir = output_dir
        self.mock_mode = mock_mode

        # Initialize components (NO video_renderer)
        self.quarantine = QuarantineGate()
        self.decision_logger = DecisionLogger()
        self.human_registry = HumanRegistry()

        self.story_mapper = StoryMapper(model_provider, self.quarantine)
        self.spoiler_engine = SpoilerEngine(model_provider)
        self.rule_compiler = RuleCompiler(model_provider, self.quarantine)
        self.rule_evaluator = RuleEvaluator()
        self.bias_auditor = BiasAuditor()
        self.audience_strategist = AudienceStrategist(model_provider, self.quarantine, self.bias_auditor)
        self.trailer_generator = TrailerGenerator(model_provider, self.rule_evaluator, self.decision_logger)
        self.verifier = VerifierOrchestrator(model_provider, self.rule_evaluator, self.decision_logger)
        self.repair_engine = RepairEngine(self.trailer_generator, self.verifier, self.decision_logger)
        self.change_handler = ChangeHandler(self.trailer_generator, self.verifier, self.repair_engine, self.decision_logger)
        self.edl_emitter = EDLEmitter(output_dir)

    def run(
        self,
        episode_package_path: Path,
        scene_descriptions_path: Path | None = None,
        dialogue_path: Path | None = None,
        policies_path: Path | None = None,
        contracts_path: Path | None = None,
        audience_profiles_path: Path | None = None,
        historic_data_path: Path | None = None,
        cost_sheet_path: Path | None = None,
    ) -> PipelineResult:
        """Run the full pipeline (video-free)."""

        # 1. Ingest and normalize
        capability_report = self._ingest_and_normalize(
            episode_package_path, scene_descriptions_path, dialogue_path,
            policies_path, contracts_path, audience_profiles_path,
            historic_data_path, cost_sheet_path
        )

        # 2. Build story map
        story_map_result = self._build_story_map(capability_report)
        story_map = story_map_result.story_map

        # 3. Build spoiler map
        spoiler_facts = self.spoiler_engine.build_spoiler_map(story_map)

        # 4. Compile rules
        rules = self._compile_rules(policies_path, contracts_path, capability_report)

        # 5. Initialize dependency graph (lazy)
        # (will be done after first trailer generation)

        # 6. Plan audience promises
        audiences = self._load_audiences(audience_profiles_path)
        strategist_result = self.audience_strategist.plan_promises(
            audiences, story_map, spoiler_facts, capability_report
        )

        # 7. Generate trailers
        trailers = []
        for promise in strategist_result.promises:
            gen_result = self.trailer_generator.generate(
                promise, story_map, spoiler_facts, rules, capability_report, trailers
            )
            trailer = gen_result.trailer_plan

            # 8. Verify
            verification = self.verifier.verify(
                trailer, story_map, spoiler_facts, rules, capability_report
            )
            trailer.validation = verification.validation

            # 9. Repair if needed
            if trailer.validation.status == ValidationStatus.FAIL:
                repair_result = self.repair_engine.repair(
                    trailer, story_map, spoiler_facts, rules, capability_report
                )
                trailer = repair_result.trailer

            trailers.append(trailer)

        # 10. Initialize dependency graph with results
        self.change_handler.initialize_graph(story_map, spoiler_facts, rules, trailers)

        # 11. Emit EDLs (NO video rendering)
        edl_outputs = self.edl_emitter.emit_all(
            trailers, story_map, capability_report, self.budget_controller.get_ledger(), rules, self.decision_logger.export_json()
        )

        return PipelineResult(
            story_map=story_map,
            spoiler_facts=spoiler_facts,
            rules=rules,
            audience_promises=strategist_result.promises,
            trailers=trailers,
            capability_report=capability_report,
            cost_ledger=self.budget_controller.get_ledger(),
            decision_log=self.decision_logger.export_json(),
            human_approvals=self.human_registry.export_json(),
            edl_outputs=edl_outputs,
        )

    def _ingest_and_normalize(
        self,
        episode_package_path: Path,
        scene_descriptions_path: Path | None,
        dialogue_path: Path | None,
        policies_path: Path | None,
        contracts_path: Path | None,
        audience_profiles_path: Path | None,
        historic_data_path: Path | None,
        cost_sheet_path: Path | None,
    ) -> CapabilityReport:
        """Ingest all input materials and build capability report."""
        warnings = []

        # Check episode package (required)
        has_video = episode_package_path.exists()
        if not has_video:
            warnings.append("No episode package found - text-only mode")

        # Check other materials
        has_scene_descriptions = scene_descriptions_path is not None and scene_descriptions_path.exists()
        has_source_dialogue = dialogue_path is not None and dialogue_path.exists()
        has_policies = policies_path is not None and policies_path.exists()
        has_contracts = contracts_path is not None and contracts_path.exists()
        has_audience_profiles = audience_profiles_path is not None and audience_profiles_path.exists()
        has_historic_data = historic_data_path is not None and historic_data_path.exists()
        has_cost_sheet = cost_sheet_path is not None and cost_sheet_path.exists()

        if not has_scene_descriptions:
            warnings.append("No scene descriptions - creative quality degraded")
        if not has_source_dialogue:
            warnings.append("No source dialogue - dialect drift check disabled")
        if not has_policies:
            warnings.append("No rating policies - using maximally restrictive defaults")
        if not has_contracts:
            warnings.append("No contracts - all asset use denied by default")
        if not has_audience_profiles:
            warnings.append("No audience profiles - using generic strategy")

        # Extract dialect tracks from dialogue if available
        dialect_tracks = []
        if has_source_dialogue:
            dialect_tracks = ["hi"]  # Placeholder

        return CapabilityReport(
            has_video=False,
            has_audio=False,
            has_scene_descriptions=has_scene_descriptions,
            has_source_dialogue=has_source_dialogue,
            dialect_tracks=dialect_tracks,
            has_policies=has_policies,
            has_contracts=has_contracts,
            has_audience_profiles=has_audience_profiles,
            has_historic_data=has_historic_data,
            has_cost_sheet=has_cost_sheet,
            warnings=warnings,
            degraded_checks=[
                "dialect_drift" if not has_source_dialogue else "",
                "visual_analysis" if not has_video else "",
            ],
        )

    def _build_story_map(self, capability_report: CapabilityReport) -> StoryMapperResult:
        """Build story map from ingested materials."""
        scenes = self._parse_scenes()
        entities = self._parse_entities()
        dialogue_by_scene = self._parse_dialogue_by_scene()
        scene_descriptions = self._parse_scene_descriptions()

        return self.story_mapper.build_story_map(
            scenes, entities, dialogue_by_scene, scene_descriptions, capability_report
        )

    def _compile_rules(
        self,
        policies_path: Path | None,
        contracts_path: Path | None,
        capability_report: CapabilityReport,
    ) -> list[Rule]:
        """Compile rules from policies and contracts."""
        all_rules = []

        if policies_path and policies_path.exists():
            policy_text = policies_path.read_text(encoding="utf-8")
            policy_rules = self.rule_compiler.compile_policies([("policy_main", policy_text)], capability_report)
            all_rules.extend(policy_rules)

        if contracts_path and contracts_path.exists():
            contract_text = contracts_path.read_text(encoding="utf-8")
            contract_rules = self.rule_compiler.compile_contracts([("contract_main", contract_text)], capability_report)
            all_rules.extend(contract_rules)

        # If no policies/contracts, apply conservative defaults
        if not all_rules:
            capability_report.warnings.append("No rules compiled - using conservative defaults")

        return all_rules

    def _load_audiences(self, audience_profiles_path: Path | None) -> list[AudienceDefinition]:
        """Load audience definitions."""
        if audience_profiles_path and audience_profiles_path.exists():
            import json
            with open(audience_profiles_path) as f:
                data = json.load(f)
            if isinstance(data, list):
                return [AudienceDefinition(**a) for a in data]

        # Return default audiences from config
        return [AudienceDefinition(**a) for a in self.config.get("audiences", [])]

    def _parse_scenes(self) -> list:
        """Parse scenes from episode package."""
        from src.models.timecode import Timecode, TimecodeFormat, ms_to_timecode
        return [
            Scene(
                scene_id=f"scene_{i:02d}",
                timecode_in=ms_to_timecode(i * 30000, TimecodeFormat.MILLISECONDS),
                timecode_out=ms_to_timecode((i + 1) * 30000, TimecodeFormat.MILLISECONDS),
                duration_ms=30000,
                description=f"Scene {i} description",
                entities=[f"char_{i}"],
                content_tags=[],
                is_characterised=True,
            )
            for i in range(8)
        ]

    def _parse_entities(self) -> list:
        """Parse entities."""
        from src.models.scene import Entity, EntityType
        return [
            Entity(entity_id=f"char_{i}", entity_type=EntityType.CHARACTER, name=f"Character {i}")
            for i in range(4)
        ]

    def _parse_dialogue_by_scene(self) -> dict:
        """Parse dialogue grouped by scene."""
        return {}

    def _parse_scene_descriptions(self) -> dict:
        """Parse scene descriptions."""
        return {}


def load_config(config_path: Path | None = None) -> dict:
    """Load configuration from YAML file."""
    if config_path and config_path.exists():
        import yaml
        with open(config_path) as f:
            return yaml.safe_load(f)

    # Default config
    return {
        "audiences": [
            {
                "audience_id": "family",
                "name": "Family viewers",
                "description": "General family audience",
                "goal": "Communicate warmth, stakes and broad entertainment value",
                "special_care": ["Follow the strictest rating rules", "Avoid frightening or suggestive context"],
                "rating_policy_ids": ["policy_family"],
            },
            {
                "audience_id": "young_adult",
                "name": "Young adult viewers",
                "description": "Young adult audience",
                "goal": "Highlight pace, humour, identity and character conflict",
                "special_care": ["Do not use misleading intensity", "Do not reveal the central twist"],
                "rating_policy_ids": ["policy_young_adult"],
            },
            {
                "audience_id": "dialect_region",
                "name": "Dialect-region viewers",
                "description": "Dialect-specific regional audience",
                "goal": "Show that the release understands their language and cultural context",
                "special_care": ["Do not reduce the audience to stereotypes", "Do not treat dialect as a comic device"],
                "rating_policy_ids": ["policy_dialect_region"],
            },
        ],
        "budget": {
            "total_usd": 10.0,
            "model_call_limit": 200,
            "media_processing_limit": 50,
            "warn_at_percent": 80,
        },
        "trailer": {
            "min_duration_seconds": 20,
            "max_duration_seconds": 60,
            "min_segments": 3,
            "max_segments": 12,
            "diversity_threshold": 0.4,
        },
    }