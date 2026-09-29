"""Dependency graph for change impact analysis."""

from __future__ import annotations

from typing import Any
from dataclasses import dataclass, field
from collections import defaultdict, deque


@dataclass
class DependencyNode:
    """Node in the dependency graph."""
    node_id: str
    node_type: str  # "scene", "entity", "rule", "spoiler_fact", "segment", "trailer"
    data: dict = field(default_factory=dict)


@dataclass
class DependencyEdge:
    """Edge in the dependency graph."""
    source_id: str
    target_id: str
    relation_type: str  # "contains", "references", "governs", "derived_from"


class DependencyGraph:
    """Tracks relationships for selective replanning."""

    def __init__(self):
        self.nodes: dict[str, DependencyNode] = {}
        self.edges: list[DependencyEdge] = []
        self._adjacency: dict[str, set[str]] = defaultdict(set)
        self._reverse_adjacency: dict[str, set[str]] = defaultdict(set)

    def add_node(self, node_id: str, node_type: str, data: dict | None = None) -> None:
        """Add a node to the graph."""
        self.nodes[node_id] = DependencyNode(node_id=node_id, node_type=node_type, data=data or {})

    def add_edge(self, source_id: str, target_id: str, relation_type: str) -> None:
        """Add a directed edge from source to target."""
        self.edges.append(DependencyEdge(source_id, target_id, relation_type))
        self._adjacency[source_id].add(target_id)
        self._reverse_adjacency[target_id].add(source_id)

    def get_affected(self, changed_node_id: str) -> set[str]:
        """BFS from changed node to find all affected downstream nodes."""
        if changed_node_id not in self.nodes:
            return set()
        
        affected = set()
        queue = deque([changed_node_id])
        visited = set()
        
        while queue:
            node_id = queue.popleft()
            if node_id in visited:
                continue
            visited.add(node_id)
            affected.add(node_id)
            
            for neighbor in self._adjacency.get(node_id, []):
                if neighbor not in visited:
                    queue.append(neighbor)
        
        return affected

    def get_affected_segments(self, changed_node_id: str) -> list[str]:
        """Filter affected nodes to only segment IDs."""
        affected = self.get_affected(changed_node_id)
        return [n for n in affected if n.startswith("segment:") or n.startswith("seg_")]

    def get_affected_trailers(self, changed_node_id: str) -> list[str]:
        """Filter affected nodes to only trailer IDs."""
        affected = self.get_affected(changed_node_id)
        return [n for n in affected if n.startswith("trailer:")]

    def get_upstream(self, node_id: str) -> set[str]:
        """Get all upstream nodes that affect this node."""
        upstream = set()
        queue = deque([node_id])
        visited = set()
        
        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            upstream.add(current)
            
            for neighbor in self._reverse_adjacency.get(current, []):
                if neighbor not in visited:
                    queue.append(neighbor)
        
        return upstream

    def build_from_pipeline(
        self,
        story_map: "StoryMap",
        spoiler_facts: list["SpoilerFact"],
        rules: list["Rule"],
        trailers: list["TrailerPlan"],
    ) -> None:
        """Build dependency graph from pipeline outputs."""
        from src.models.story_map import StoryMap
        from src.models.spoiler import SpoilerFact
        from src.models.rule import Rule
        from src.models.trailer import TrailerPlan
        
        # Add story map nodes
        for scene in story_map.scenes:
            self.add_node(f"scene:{scene.scene_id}", "scene", {"scene_id": scene.scene_id})
            for entity_id in scene.entities:
                self.add_node(f"entity:{entity_id}", "entity", {"entity_id": entity_id})
                self.add_edge(f"scene:{scene.scene_id}", f"entity:{entity_id}", "contains")
        
        for entity in story_map.entities:
            self.add_node(f"entity:{entity.entity_id}", "entity", {"entity_id": entity.entity_id})
            for rel in entity.relationships:
                self.add_edge(f"entity:{entity.entity_id}", f"entity:{rel.target_entity_id}", "relationship")
        
        for event in story_map.major_events:
            self.add_node(f"event:{event.event_id}", "event", {"event_id": event.event_id})
            self.add_edge(f"event:{event.event_id}", f"scene:{event.scene_id}", "occurs_in")
            for entity_id in event.involved_entities:
                self.add_edge(f"event:{event.event_id}", f"entity:{entity_id}", "involves")
            for cause_id in event.causes:
                self.add_edge(f"event:{cause_id}", f"event:{event.event_id}", "causes")
        
        # Add spoiler facts
        for fact in spoiler_facts:
            self.add_node(f"spoiler:{fact.fact_id}", "spoiler_fact", {"fact_id": fact.fact_id})
            for scene_id in fact.involved_scenes:
                self.add_edge(f"spoiler:{fact.fact_id}", f"scene:{scene_id}", "revealed_in")
            for entity_id in fact.involved_entities:
                self.add_edge(f"spoiler:{fact.fact_id}", f"entity:{entity_id}", "involves")
        
        # Add rules
        for rule in rules:
            self.add_node(f"rule:{rule.rule_id}", "rule", {"rule_id": rule.rule_id})
            for cond in rule.conditions:
                if cond.field in ("scene_id", "video"):
                    self.add_edge(f"rule:{rule.rule_id}", f"scene:{cond.value}", "governs")
                elif cond.field in ("actor_id", "entity_id"):
                    self.add_edge(f"rule:{rule.rule_id}", f"entity:{cond.value}", "governs")
                elif cond.field == "music_track":
                    self.add_edge(f"rule:{rule.rule_id}", f"music:{cond.value}", "governs")
        
        # Add trailer and segment nodes
        for trailer in trailers:
            self.add_node(f"trailer:{trailer.trailer_id}", "trailer", {"trailer_id": trailer.trailer_id})
            for segment in trailer.segments:
                self.add_node(f"segment:{segment.segment_id}", "segment", {"segment_id": segment.segment_id})
                self.add_edge(f"trailer:{trailer.trailer_id}", f"segment:{segment.segment_id}", "contains")
                self.add_edge(f"segment:{segment.segment_id}", f"scene:{segment.video}", "references")
                if segment.audio.startswith("music_"):
                    self.add_edge(f"segment:{segment.segment_id}", f"music:{segment.audio}", "uses_music")
                for entity_id in segment.evidence:
                    if entity_id.startswith("entity:") or entity_id.startswith("scene:") or entity_id.startswith("event:"):
                        self.add_edge(f"segment:{segment.segment_id}", entity_id, "evidence")