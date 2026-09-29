"""Story mapper - builds canonical story map from episode materials."""

from __future__ import annotations

import uuid
from typing import Any, Optional
from dataclasses import dataclass

from src.models.scene import Scene, Entity, EntityType, Relationship
from src.models.story_map import StoryMap, StoryEvent, EmotionalBeat
from src.models.timecode import Timecode
from src.providers.base import ModelProvider
from src.quarantine import QuarantineGate


@dataclass
class StoryMapperResult:
    """Result of story mapping."""
    story_map: StoryMap
    capability_warnings: list[str]


class StoryMapper:
    """Builds story map from episode package, scene descriptions, and dialogue."""

    def __init__(self, model_provider: ModelProvider, quarantine: QuarantineGate):
        self.model_provider = model_provider
        self.quarantine = quarantine

    def build_story_map(
        self,
        scenes: list[Scene],
        entities: list[Entity],
        dialogue_by_scene: dict[str, list[dict]],
        scene_descriptions: dict[str, str] | None = None,
        capability_report: Any = None,
    ) -> StoryMapperResult:
        """Build complete story map."""
        warnings = []
        
        # 1. Sanitise scene descriptions
        if scene_descriptions:
            sanitised_descriptions = {}
            for scene_id, desc in scene_descriptions.items():
                sanitised = self.quarantine.sanitise(desc, f"scene_desc:{scene_id}")
                if sanitised.was_modified:
                    warnings.append(f"Injection detected in scene description {scene_id}")
                sanitised_descriptions[scene_id] = sanitised.clean_text
            scene_descriptions = sanitised_descriptions

        # 2. Extract entities and relationships from descriptions + dialogue
        extracted_entities, extracted_relationships = self._extract_entities_and_relationships(
            scenes, scene_descriptions, dialogue_by_scene
        )
        
        # Merge with provided entities
        all_entities = {e.entity_id: e for e in entities}
        for entity in extracted_entities:
            if entity.entity_id not in all_entities:
                all_entities[entity.entity_id] = entity
            else:
                # Merge relationships
                existing = all_entities[entity.entity_id]
                existing.relationships.extend(entity.relationships)

        # 3. Build events from scene analysis
        events = self._extract_events(scenes, scene_descriptions, dialogue_by_scene, list(all_entities.values()))
        
        # 4. Build emotional arc
        emotional_arc = self._extract_emotional_arc(scenes, scene_descriptions, dialogue_by_scene)
        
        # 5. Compute total duration
        total_duration = max((s.timecode_out.normalised_ms for s in scenes), default=0)
        
        # 6. Normalise event positions
        for event in events:
            scene = next((s for s in scenes if s.scene_id == event.scene_id), None)
            if scene and total_duration > 0:
                event.normalised_position = scene.timecode_in.normalised_ms / total_duration

        # 7. Build causal graph
        self._build_causal_graph(events)

        story_map = StoryMap(
            episode_id="episode_01",  # Would come from input
            scenes=scenes,
            entities=list(all_entities.values()),
            major_events=events,
            emotional_arc=emotional_arc,
            total_duration_ms=total_duration,
            metadata={},
        )

        return StoryMapperResult(story_map=story_map, capability_warnings=warnings)

    def _extract_entities_and_relationships(
        self,
        scenes: list[Scene],
        descriptions: dict[str, str] | None,
        dialogue_by_scene: dict[str, list[dict]]
    ) -> tuple[list[Entity], list[Relationship]]:
        """Extract entities and relationships using LLM."""
        # Build context from available data
        context_parts = []
        
        for scene in scenes:
            parts = [f"Scene {scene.scene_id}:"]
            if descriptions and scene.scene_id in descriptions:
                parts.append(f"  Description: {descriptions[scene.scene_id]}")
            if scene.scene_id in dialogue_by_scene:
                dialogue_text = " ".join([d.get("text", "") for d in dialogue_by_scene[scene.scene_id]])
                parts.append(f"  Dialogue: {dialogue_text[:500]}")
            context_parts.append("\n".join(parts))
        
        context = "\n\n".join(context_parts)
        
        prompt = f"""Analyze this episode content and extract:
1. All characters, locations, objects, and music tracks mentioned
2. Relationships between entities (e.g., sibling, rival, mentor, parent-child)
3. When each relationship is revealed (scene ID)

Output as JSON with this structure:
{{
  "entities": [
    {{"entity_id": "char_01", "entity_type": "character", "name": "Priya", "aliases": ["Pri"], "first_appearance_scene": "scene_01", "relationships": [{{"target_entity_id": "char_02", "relationship_type": "sibling", "revealed_in_scene": "scene_03", "is_spoiler": true}}]}}
  ]
}}

{self.quarantine.wrap_for_llm(context)}"""

        try:
            response = self.model_provider.complete(
                messages=[{"role": "user", "content": prompt}],
                budget_tag="entity_extraction"
            )
            # Parse response - simplified for now
            # In production, use structured output
            return self._parse_entity_response(response.text, scenes)
        except Exception as e:
            # Fallback: use scene entity lists
            return self._fallback_entities(scenes), []

    def _parse_entity_response(self, response: str, scenes: list[Scene]) -> tuple[list[Entity], list[Relationship]]:
        """Parse LLM entity extraction response."""
        import json
        try:
            data = json.loads(response)
            entities = []
            relationships = []
            
            for ed in data.get("entities", []):
                rels = []
                for rel_data in ed.get("relationships", []):
                    rels.append(Relationship(**rel_data))
                
                entities.append(Entity(
                    entity_id=ed["entity_id"],
                    entity_type=EntityType(ed["entity_type"]),
                    name=ed["name"],
                    aliases=ed.get("aliases", []),
                    first_appearance_scene=ed.get("first_appearance_scene"),
                    relationships=rels,
                ))
                relationships.extend(rels)
            
            return entities, relationships
        except Exception:
            return self._fallback_entities(scenes), []

    def _fallback_entities(self, scenes: list[Scene]) -> list[Entity]:
        """Create entities from scene entity lists."""
        entities = {}
        for scene in scenes:
            for entity_id in scene.entities:
                if entity_id not in entities:
                    entities[entity_id] = Entity(
                        entity_id=entity_id,
                        entity_type=EntityType.CHARACTER,
                        name=entity_id.replace("_", " ").title(),
                        first_appearance_scene=scene.scene_id,
                    )
        return list(entities.values())

    def _extract_events(
        self,
        scenes: list[Scene],
        descriptions: dict[str, str] | None,
        dialogue_by_scene: dict[str, list[dict]],
        entities: list[Entity]
    ) -> list[StoryEvent]:
        """Extract story events from scenes."""
        events = []
        entity_names = {e.entity_id: e.name for e in entities}
        
        for i, scene in enumerate(scenes):
            # Determine event type from position and content
            position = i / max(len(scenes) - 1, 1)
            
            if position < 0.2:
                event_type = "setup"
            elif position < 0.4:
                event_type = "conflict"
            elif position < 0.6:
                event_type = "escalation"
            elif position < 0.8:
                event_type = "climax"
            else:
                event_type = "resolution"
            
            # Check for twist markers in description
            desc = descriptions.get(scene.scene_id, "") if descriptions else ""
            if any(word in desc.lower() for word in ["twist", "reveal", "secret", "hidden", "betrayal"]):
                event_type = "twist"
            
            involved = scene.entities[:3]  # Limit
            
            event = StoryEvent(
                event_id=f"event_{scene.scene_id}",
                description=desc[:200] if desc else f"Events in {scene.scene_id}",
                scene_id=scene.scene_id,
                involved_entities=involved,
                event_type=event_type,
                normalised_position=position,
            )
            events.append(event)
        
        return events

    def _build_causal_graph(self, events: list[StoryEvent]) -> None:
        """Build causal relationships between events."""
        # Simple heuristic: earlier events can cause later events
        for i, event in enumerate(events):
            for j in range(i + 1, min(i + 3, len(events))):  # Look ahead 2 events
                later_event = events[j]
                # Check for shared entities
                shared = set(event.involved_entities) & set(later_event.involved_entities)
                if shared:
                    later_event.causes.append(event.event_id)
                    event.caused_by.append(later_event.event_id)

    def _extract_emotional_arc(
        self,
        scenes: list[Scene],
        descriptions: dict[str, str] | None,
        dialogue_by_scene: dict[str, list[dict]]
    ) -> list[EmotionalBeat]:
        """Extract emotional beats for each scene."""
        beats = []
        emotions = ["neutral", "tension", "joy", "sadness", "fear", "anger", "surprise", "anticipation"]
        
        for scene in scenes:
            # Use description to infer emotion
            desc = descriptions.get(scene.scene_id, "") if descriptions else ""
            emotion = "neutral"
            intensity = 0.5
            
            if any(w in desc.lower() for w in ["fight", "argument", "conflict", "tense"]):
                emotion = "tension"
                intensity = 0.8
            elif any(w in desc.lower() for w in ["happy", "joy", "celebrat", "laugh"]):
                emotion = "joy"
                intensity = 0.7
            elif any(w in desc.lower() for w in ["sad", "cry", "grief", "loss", "death"]):
                emotion = "sadness"
                intensity = 0.8
            elif any(w in desc.lower() for w in ["scary", "fear", "terror", "danger"]):
                emotion = "fear"
                intensity = 0.8
            elif any(w in desc.lower() for w in ["angry", "rage", "furious"]):
                emotion = "anger"
                intensity = 0.7
            elif any(w in desc.lower() for w in ["surprise", "shock", "reveal", "twist"]):
                emotion = "surprise"
                intensity = 0.9
            elif any(w in desc.lower() for w in ["wait", "anticipat", "expect", "coming"]):
                emotion = "anticipation"
                intensity = 0.6
            
            beats.append(EmotionalBeat(
                scene_id=scene.scene_id,
                emotion=emotion,
                intensity=intensity,
            ))
        
        return beats