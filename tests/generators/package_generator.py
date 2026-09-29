"""Test package generator for creating synthetic episode packages."""

import random
from dataclasses import dataclass
from typing import Any
from src.models.scene import Scene, Entity, EntityType
from src.models.timecode import Timecode, TimecodeFormat
from src.models.story_map import StoryMap, StoryEvent, EmotionalBeat
from src.models.spoiler import SpoilerFact
from src.models.rule import Rule, RuleScope, RuleEffect, RuleCondition
from src.models.audience import AudienceDefinition
from src.models.capability import CapabilityReport


@dataclass
class EpisodePackage:
    """Synthetic episode package for testing."""
    scenes: list[Scene]
    entities: list[Entity]
    story_map: StoryMap
    spoiler_facts: list[SpoilerFact]
    rules: list[Rule]
    audiences: list[AudienceDefinition]
    has_video: bool
    capability_report: CapabilityReport


def generate_package(
    num_scenes: int = 8,
    languages: list[str] = None,
    frame_rate: float = 24.0,
    num_rules: int = 5,
    num_audiences: int = 3,
    missing_materials: list[str] = None,
    malformed_materials: list[str] = None,
    seed: int = 42
) -> EpisodePackage:
    """Generate a parameterised toy episode package for testing."""
    rng = random.Random(seed)
    languages = languages or ["en", "hi"]
    missing_materials = missing_materials or []
    malformed_materials = malformed_materials or []
    
    # Generate scenes
    scenes = []
    entities = []
    current_ms = 0
    scene_duration_ms = 30000  # 30 seconds per scene
    
    for i in range(num_scenes):
        scene_id = f"scene_{i+1:02d}"
        tc_in = Timecode(
            raw=f"{current_ms}ms", hours=0, minutes=0, seconds=0, fractional=0,
            source_format=TimecodeFormat.MILLISECONDS, normalised_ms=current_ms
        )
        tc_out = Timecode(
            raw=f"{current_ms + scene_duration_ms}ms", hours=0, minutes=0, seconds=0, fractional=0,
            source_format=TimecodeFormat.MILLISECONDS, normalised_ms=current_ms + scene_duration_ms
        )
        
        # Add some entities to scenes
        scene_entities = []
        if i < 4:  # First 4 scenes have characters
            for j in range(min(3, i+1)):
                entity_id = f"char_{j+1}"
                scene_entities.append(entity_id)
                # Add entity if new
                if not any(e.entity_id == entity_id for e in entities):
                    entities.append(Entity(
                        entity_id=entity_id,
                        entity_type=EntityType.CHARACTER,
                        name=f"Character {j+1}",
                        first_appearance_scene=scene_id,
                    ))
        
        scene = Scene(
            scene_id=scene_id,
            timecode_in=tc_in,
            timecode_out=tc_out,
            duration_ms=scene_duration_ms,
            description=f"Scene {i+1} description with some content",
            entities=scene_entities,
            content_tags=rng.sample(["dialogue", "action", "emotional", "reveal", "humor"], k=rng.randint(0, 3)),
            emotional_tone=rng.choice(["neutral", "tension", "joy", "sadness", "surprise"]),
            is_characterised=True,
        )
        scenes.append(scene)
        current_ms += scene_duration_ms
    
    # Generate story events
    events = []
    event_types = ["setup", "conflict", "escalation", "climax", "resolution", "twist"]
    for i, scene in enumerate(scenes):
        if i == 0:
            etype = "setup"
        elif i == len(scenes) - 1:
            etype = rng.choice(["resolution", "twist"])
        elif i == len(scenes) - 2:
            etype = "climax"
        else:
            etype = rng.choice(["conflict", "escalation"])
        
        events.append(StoryEvent(
            event_id=f"event_{scene.scene_id}",
            description=f"{etype.capitalize()} in {scene.scene_id}",
            scene_id=scene.scene_id,
            involved_entities=scene.entities[:3],
            event_type=etype,
            normalised_position=scene.timecode_in.normalised_ms / current_ms if current_ms > 0 else 0,
        ))
    
    # Generate emotional arc
    emotional_arc = []
    for scene in scenes:
        emotional_arc.append(EmotionalBeat(
            scene_id=scene.scene_id,
            emotion=scene.emotional_tone or "neutral",
            intensity=rng.uniform(0.2, 0.9),
        ))
    
    # Build story map
    story_map = StoryMap(
        episode_id="test_episode",
        scenes=scenes,
        entities=entities,
        major_events=events,
        emotional_arc=emotional_arc,
        total_duration_ms=current_ms,
    )
    
    # Generate spoiler facts
    spoiler_facts = []
    late_scenes = [s for s in scenes if s.timecode_in.normalised_ms / current_ms >= 0.7]
    for scene in late_scenes[:2]:
        spoiler_facts.append(SpoilerFact(
            fact_id=f"spoiler_{scene.scene_id}",
            fact_type=rng.choice(["causal_reveal", "identity_reveal", "outcome", "twist"]),
            description=f"Spoiler in {scene.scene_id}",
            involved_entities=scene.entities,
            involved_scenes=[scene.scene_id],
            reveal_boundary=0.7,
            evidence=[f"event_{scene.scene_id}"],
            confidence=rng.uniform(0.6, 0.95),
        ))
    
    # Generate rules
    rules = []
    rule_templates = [
        (RuleScope.VISUAL_CONTENT, RuleEffect.DENY, "content_tags", "contains", "violence"),
        (RuleScope.MUSIC_TRACK, RuleEffect.DENY, "music_track", "eq", "music_expired"),
        (RuleScope.ACTOR, RuleEffect.DENY, "actor_id", "eq", "actor_restricted"),
        (RuleScope.TERRITORY, RuleEffect.DENY, "territory", "not_in", ["IN"]),
        (RuleScope.AUDIENCE, RuleEffect.DENY, "audience_id", "eq", "family"),
    ]
    
    for i in range(min(num_rules, len(rule_templates))):
        scope, effect, field, op, value = rule_templates[i]
        rules.append(Rule(
            rule_id=f"rule_{i+1}",
            source_policy_id=f"policy_{i+1}" if scope != RuleScope.MUSIC_TRACK else None,
            source_contract_id=f"contract_{i+1}" if scope == RuleScope.MUSIC_TRACK else None,
            source_span=f"Rule {i+1} description",
            scope=scope,
            effect=effect,
            conditions=[RuleCondition(field=field, operator=op, value=value)],
            confidence=0.9,
        ))
    
    # Generate audiences
    audience_templates = [
        {"audience_id": "family", "name": "Family", "description": "Family audience", "goal": "Wholesome entertainment", "special_care": ["No violence"], "rating_policy_ids": ["policy_family"]},
        {"audience_id": "young_adult", "name": "Young Adult", "description": "Young adult audience", "goal": "Engaging drama", "special_care": ["No spoilers"], "rating_policy_ids": ["policy_ya"]},
        {"audience_id": "dialect_region", "name": "Dialect Region", "description": "Dialect region audience", "goal": "Cultural relevance", "special_care": ["No stereotypes"], "rating_policy_ids": ["policy_dialect"]},
        {"audience_id": "general", "name": "General", "description": "General audience", "goal": "Broad appeal", "special_care": [], "rating_policy_ids": []},
    ]
    
    audiences = []
    for i in range(min(num_audiences, len(audience_templates))):
        t = audience_templates[i]
        audiences.append(AudienceDefinition(**t))
    
    # Capability report
    has_video = "video" not in missing_materials
    capability_report = CapabilityReport(
        has_video=has_video,
        has_audio=has_video,
        has_scene_descriptions="scene_descriptions" not in missing_materials,
        has_source_dialogue="dialogue" not in missing_materials,
        dialect_tracks=languages[1:] if len(languages) > 1 else [],
        has_policies="policies" not in missing_materials,
        has_contracts="contracts" not in missing_materials,
        has_audience_profiles="audience_profiles" not in missing_materials,
        has_historic_data="historic_data" not in missing_materials,
        has_cost_sheet="cost_sheet" not in missing_materials,
        warnings=[],
        degraded_checks=[],
    )
    
    return EpisodePackage(
        scenes=scenes,
        entities=entities,
        story_map=story_map,
        spoiler_facts=spoiler_facts,
        rules=rules,
        audiences=audiences,
        has_video=has_video,
        capability_report=capability_report,
    )


def corrupt(package: EpisodePackage, material: str, rng: random.Random) -> None:
    """Corrupt a material for testing malformed inputs."""
    if material == "scenes" and package.scenes:
        # Make timecodes invalid
        scene = package.scenes[0]
        scene.timecode_out = Timecode(
            raw="invalid", hours=0, minutes=0, seconds=0, fractional=0,
            source_format=TimecodeFormat.MILLISECONDS, normalised_ms=-1
        )
    elif material == "rules" and package.rules:
        # Make rule invalid
        package.rules[0].conditions = [RuleCondition(field="invalid", operator="invalid", value="invalid")]