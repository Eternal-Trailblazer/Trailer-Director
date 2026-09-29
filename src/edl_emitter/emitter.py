"""EDL emitter - outputs creative brief and EDL per trailer in exact JSON format per specification."""

from __future__ import annotations

import json
from typing import Any
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

from src.models.trailer import TrailerPlan, TrailerValidation, ValidationStatus
from src.models.story_map import StoryMap
from src.models.audience import AudiencePromise
from src.models.segment import Segment
from src.models.capability import CapabilityReport
from src.models.cost import CostLedger


@dataclass
class EDLOutput:
    """Complete EDL output for a trailer in exact specification format."""
    trailer_id: str
    audience: str
    duration_seconds: float
    audience_promise: str
    segments: list[dict]
    validation: dict
    # Additional metadata not in spec but useful
    creative_brief: dict = None
    edl: list = None
    validation_summary: dict = None
    metadata: dict = None


class EDLEmitter:
    """Emits EDL and creative brief in exact JSON format per specification."""

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def emit_trailer(
        self,
        trailer: TrailerPlan,
        story_map: StoryMap,
        capability_report: CapabilityReport,
        cost_ledger: CostLedger,
        decision_log: list[dict] | None = None,
    ) -> EDLOutput:
        """Emit complete output for a single trailer in exact spec format."""
        
        # Build segments in exact spec format
        segments = self._build_segments_spec(trailer)
        
        # Build validation in exact spec format
        validation = self._build_validation_spec(trailer.validation)
        
        # Create the exact spec format
        output_data = {
            "trailer_id": trailer.trailer_id,
            "audience": trailer.audience,
            "duration_seconds": trailer.duration_seconds,
            "audience_promise": trailer.audience_promise.promise_text,
            "segments": self._build_segments_spec(trailer),
            "validation": self._build_validation_spec(trailer.validation)
        }
        
        # Also build additional data for internal use
        creative_brief = self._build_creative_brief(trailer, story_map, capability_report)
        edl = self._build_edl(trailer, story_map)
        validation_summary = self._build_validation_summary(trailer.validation)
        metadata = self._build_metadata(trailer, story_map, capability_report, cost_ledger)
        
        # Write the exact spec format to file
        output_file = self.output_dir / f"{trailer.trailer_id}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({
                "trailer_id": trailer.trailer_id,
                "audience": trailer.audience,
                "duration_seconds": trailer.duration_seconds,
                "audience_promise": trailer.audience_promise.promise_text,
                "segments": self._build_segments_spec(trailer),
                "validation": self._build_validation_spec(trailer.validation)
            }, f, indent=2, ensure_ascii=False)
        
        # Also save extended version with all details
        extended_file = self.output_dir / f"{trailer.trailer_id}_extended.json"
        with open(extended_file, "w", encoding="utf-8") as f:
            json.dump({
                "trailer_id": trailer.trailer_id,
                "audience": trailer.audience,
                "duration_seconds": trailer.duration_seconds,
                "audience_promise": trailer.audience_promise.promise_text,
                "segments": self._build_segments_spec(trailer),
                "validation": self._build_validation_spec(trailer.validation),
                "creative_brief": self._build_creative_brief(trailer, story_map, capability_report),
                "edl": self._build_edl(trailer, story_map),
                "validation_summary": self._build_validation_summary(trailer.validation),
                "metadata": self._build_metadata(trailer, story_map, capability_report, cost_ledger)
            }, f, indent=2, ensure_ascii=False)
        
        return EDLOutput(
            trailer_id=trailer.trailer_id,
            audience=trailer.audience,
            duration_seconds=trailer.duration_seconds,
            audience_promise=trailer.audience_promise.promise_text,
            segments=self._build_segments_spec(trailer),
            validation=self._build_validation_spec(trailer.validation),
            creative_brief=self._build_creative_brief(trailer, story_map, capability_report),
            edl=self._build_edl(trailer, story_map),
            validation_summary=self._build_validation_summary(trailer.validation),
            metadata=self._build_metadata(trailer, story_map, capability_report, cost_ledger)
        )

    def emit_all(
        self,
        trailers: list[TrailerPlan],
        story_map: StoryMap,
        capability_report: CapabilityReport,
        cost_ledger: CostLedger,
        rules: list = None,
        decision_log: list[dict] | None = None,
    ) -> list[EDLOutput]:
        """Emit outputs for all trailers."""
        outputs = []
        for trailer in trailers:
            output = self.emit_trailer(trailer, story_map, capability_report, cost_ledger, decision_log)
            outputs.append(output)
        
        # Write summary files
        self._write_summary(trailers, story_map, capability_report, cost_ledger)
        self._write_story_map(story_map)
        self._write_constraint_map(rules if rules else [])
        print(f"[DEBUG] Calling _write_decision_log with: {decision_log}")
        self._write_decision_log(decision_log)
        self._write_cost_ledger(cost_ledger)
        
        return outputs

    def _build_segments_spec(self, trailer: TrailerPlan) -> list[dict]:
        """Build segments in exact specification format."""
        segments = []
        for segment in trailer.segments:
            seg_dict = {
                "source_in": segment.source_in.to_srt() if hasattr(segment.source_in, 'to_srt') else str(segment.source_in),
                "source_out": segment.source_out.to_srt() if hasattr(segment.source_out, 'to_srt') else str(segment.source_out),
                "video": segment.video,
                "audio": segment.audio,
                "subtitle": segment.subtitle,
                "reason": segment.reason,
                "evidence": segment.evidence,
                "risk_flags": segment.risk_flags
            }
            # Only add optional fields if present
            if segment.text_card:
                seg_dict["text_card"] = segment.text_card
            if segment.voice_over:
                seg_dict["voice_over"] = segment.voice_over
            if segment.transition:
                seg_dict["transition"] = segment.transition.value if hasattr(segment.transition, 'value') else str(segment.transition)
            segments.append(seg_dict)
        return segments

    def _build_validation_spec(self, validation: TrailerValidation | None) -> dict:
        """Build validation in exact spec format."""
        if not validation:
            return {"status": "NOT_VALIDATED"}
        
        return {
            "status": validation.status.value,
            "warnings": validation.warnings,
            "failures": validation.failures,
            "human_approvals_required": validation.human_approvals_required
        }

    def _build_audience_promise_text(self, promise: AudiencePromise) -> str:
        """Build audience promise text."""
        return promise.promise_text

    def _build_creative_brief(
        self, 
        trailer: TrailerPlan, 
        story_map: StoryMap, 
        capability_report: CapabilityReport
    ) -> dict:
        """Build creative brief from trailer plan."""
        promise = trailer.audience_promise
        
        return {
            "trailer_id": trailer.trailer_id,
            "audience": trailer.audience,
            "audience_promise": {
                "promise_text": promise.promise_text,
                "intended_emotions": promise.intended_emotions,
                "narrative_arc": promise.narrative_arc,
                "tone": promise.tone,
                "avoid": promise.avoid,
                "evidence": promise.evidence,
            },
            "story_map_summary": {
                "episode_id": story_map.episode_id,
                "total_scenes": len(story_map.scenes),
                "total_duration_ms": story_map.total_duration_ms,
                "key_events": [
                    {
                        "event_id": e.event_id,
                        "type": e.event_type,
                        "description": e.description[:200],
                        "scene": e.scene_id,
                        "position": e.normalised_position,
                    }
                    for e in story_map.major_events[:5]
                ],
                "emotional_arc": [
                    {"scene": b.scene_id, "emotion": b.emotion, "intensity": b.intensity}
                    for b in story_map.emotional_arc[:10]
                ],
            },
            "capability_mode": {
                "video": capability_report.has_video,
                "audio": capability_report.has_audio,
                "scene_descriptions": capability_report.has_scene_descriptions,
                "source_dialogue": capability_report.has_source_dialogue,
                "dialect_tracks": capability_report.dialect_tracks,
                "degraded_checks": capability_report.degraded_checks,
            },
        }

    def _build_edl(self, trailer: TrailerPlan, story_map: StoryMap) -> list[dict]:
        """Build Edit Decision List."""
        edl = []
        scene_map = {s.scene_id: s for s in story_map.scenes}
        
        for segment in trailer.segments:
            scene = scene_map.get(segment.video)
            
            edl_entry = {
                "segment_id": segment.segment_id,
                "sequence_order": segment.sequence_order,
                "source": {
                    "scene_id": segment.video,
                    "scene_description": scene.description if scene else None,
                    "source_in": segment.source_in.to_srt() if hasattr(segment.source_in, 'to_srt') else str(segment.source_in),
                    "source_out": segment.source_out.to_srt() if hasattr(segment.source_out, 'to_srt') else str(segment.source_out),
                    "source_in_ms": segment.source_in.normalised_ms if hasattr(segment.source_in, 'normalised_ms') else 0,
                    "source_out_ms": segment.source_out.normalised_ms if hasattr(segment.source_out, 'normalised_ms') else 0,
                    "duration_ms": segment.duration_ms,
                },
                "audio": {
                    "type": segment.audio,
                    "track_id": segment.audio if segment.audio not in ("dialogue", "music", "dialogue_and_music", "silence") else None,
                },
                "subtitle": segment.subtitle,
                "text_card": segment.text_card,
                "voice_over": segment.voice_over,
                "transition": segment.transition.value if segment.transition else "cut",
                "creative_reason": segment.reason,
                "evidence": segment.evidence,
                "risk_flags": segment.risk_flags,
            }
            edl.append(edl_entry)
        
        return edl

    def _build_validation_summary(self, validation: TrailerValidation | None) -> dict:
        """Build validation summary."""
        if not validation:
            return {"status": "NOT_VALIDATED", "checks": []}
        
        return {
            "overall_status": validation.status.value,
            "checks": [
                {
                    "check_id": c.check_id,
                    "check_type": c.check_type,
                    "verdict": c.verdict,
                    "evidence": c.evidence,
                    "details": c.details,
                }
                for c in validation.checks
            ],
            "warnings": validation.warnings,
            "failures": validation.failures,
            "human_approvals_required": validation.human_approvals_required,
        }

    def _build_metadata(self, trailer: TrailerPlan, story_map: StoryMap, capability_report: CapabilityReport, cost_ledger: CostLedger) -> dict:
        """Build metadata."""
        return {
            "trailer_id": trailer.trailer_id,
            "audience": trailer.audience,
            "generated_at": datetime.now().isoformat(),
            "duration_seconds": trailer.duration_seconds,
            "segment_count": len(trailer.segments),
            "estimated_cost": trailer.estimated_cost,
            "capability_report": capability_report.model_dump() if hasattr(capability_report, 'model_dump') else {},
            "cost_ledger_summary": {
                "total_cost": cost_ledger.total_cost,
                "budget_limit": cost_ledger.budget_limit,
                "budget_remaining": cost_ledger.budget_remaining,
            },
        }

    def _write_output(self, trailer_id: str, output: EDLOutput) -> None:
        """Write output to JSON file."""
        # This is now handled in emit_trailer
        pass

    def _write_summary(
        self,
        trailers: list[TrailerPlan],
        story_map: StoryMap,
        capability_report: CapabilityReport,
        cost_ledger: CostLedger,
    ) -> None:
        """Write validation report summary."""
        summary = {
            "generated_at": datetime.now().isoformat(),
            "episode_id": story_map.episode_id if story_map else "unknown",
            "trailers": [
                {
                    "trailer_id": t.trailer_id,
                    "audience": t.audience,
                    "status": t.validation.status.value if t.validation else "PENDING",
                    "duration_seconds": t.duration_seconds,
                    "segments": len(t.segments),
                    "estimated_cost": t.estimated_cost,
                }
                for t in trailers
            ],
            "overall_status": "PASS" if all(
                t.validation and t.validation.status in (ValidationStatus.PASS, ValidationStatus.PASS_WITH_WARNINGS)
                for t in trailers
            ) else "FAIL",
            "cost_ledger": {
                "total_cost": cost_ledger.total_cost,
                "budget_limit": cost_ledger.budget_limit,
                "budget_remaining": cost_ledger.budget_remaining,
                "entries": [
                    {
                        "operation": e.operation,
                        "provider": e.provider,
                        "tokens_in": e.tokens_in,
                        "tokens_out": e.tokens_out,
                        "cost": e.cost,
                        "budget_tag": e.budget_tag,
                    }
                    for e in cost_ledger.entries
                ],
            },
            "capability_report": cost_ledger.__dict__ if hasattr(cost_ledger, '__dict__') else {},
        }
        
        summary_file = self.output_dir / "validation_report.json"
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        # Also write human-readable markdown
        self._write_validation_report_md(summary)

    def _write_validation_report_md(self, summary: dict) -> None:
        """Write human-readable validation report."""
        md_lines = [
            "# Validation Report",
            f"\nGenerated: {summary['generated_at']}",
            f"\nEpisode: {summary['episode_id']}",
            f"\nOverall Status: {summary['overall_status']}",
            "\n## Trailers",
        ]
        
        for t in summary["trailers"]:
            md_lines.append(f"\n### {t['trailer_id']} ({t['audience']})")
            md_lines.append(f"- Status: {t['status']}")
            md_lines.append(f"- Duration: {t['duration_seconds']:.1f}s")
            md_lines.append(f"- Segments: {t['segments']}")
            md_lines.append(f"- Estimated Cost: ${t['estimated_cost']:.4f}")
        
        md_lines.append(f"\n## Cost Summary")
        md_lines.append(f"- Total Cost: ${summary['cost_ledger']['total_cost']:.4f}")
        md_lines.append(f"- Budget Limit: ${summary['cost_ledger']['budget_limit']:.2f}")
        md_lines.append(f"- Budget Remaining: ${summary['cost_ledger']['budget_remaining']:.4f}")
        
        md_file = self.output_dir / "validation_report.md"
        with open(md_file, "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines))

    def _write_story_map(self, story_map: StoryMap) -> None:
        """Write story map to JSON."""
        if not story_map:
            return
        
        data = {
            "episode_id": story_map.episode_id,
            "total_duration_ms": story_map.total_duration_ms,
            "scenes": [
                {
                    "scene_id": s.scene_id,
                    "timecode_in": s.timecode_in.to_srt() if hasattr(s.timecode_in, 'to_srt') else str(s.timecode_in),
                    "timecode_out": s.timecode_out.to_srt() if hasattr(s.timecode_out, 'to_srt') else str(s.timecode_out),
                    "duration_ms": s.duration_ms,
                    "description": s.description,
                    "entities": s.entities,
                    "content_tags": s.content_tags,
                    "emotional_tone": s.emotional_tone,
                    "is_characterised": s.is_characterised,
                }
                for s in story_map.scenes
            ],
            "entities": [
                {
                    "entity_id": e.entity_id,
                    "entity_type": e.entity_type.value if hasattr(e.entity_type, 'value') else str(e.entity_type),
                    "name": e.name,
                    "aliases": e.aliases,
                    "first_appearance_scene": e.first_appearance_scene,
                    "relationships": [
                        {
                            "target_entity_id": r.target_entity_id,
                            "relationship_type": r.relationship_type,
                            "revealed_in_scene": r.revealed_in_scene,
                            "is_spoiler": r.is_spoiler
                        }
                        for r in e.relationships
                    ]
                }
                for e in story_map.entities
            ],
            "major_events": [
                {
                    "event_id": e.event_id,
                    "description": e.description,
                    "scene_id": e.scene_id,
                    "involved_entities": e.involved_entities,
                    "event_type": e.event_type,
                    "normalised_position": e.normalised_position,
                    "causes": e.causes,
                    "caused_by": e.caused_by,
                }
                for e in story_map.major_events
            ],
            "emotional_arc": [
                {
                    "scene_id": b.scene_id,
                    "emotion": b.emotion,
                    "intensity": b.intensity
                }
                for b in story_map.emotional_arc
            ],
            "metadata": story_map.metadata,
        }
        
        output_file = self.output_dir / "story_map.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _write_constraint_map(self, rules: list) -> None:
        """Write constraint map to JSON."""
        data = {
            "rules": [
                {
                    "rule_id": r.rule_id,
                    "source_contract_id": r.source_contract_id,
                    "source_policy_id": r.source_policy_id,
                    "source_span": r.source_span,
                    "scope": r.scope.value if hasattr(r.scope, 'value') else str(r.scope),
                    "effect": r.effect.value if hasattr(r.effect, 'value') else str(r.effect),
                    "conditions": [
                        {
                            "field": c.field,
                            "operator": c.operator,
                            "value": c.value
                        }
                        for c in r.conditions
                    ],
                    "confidence": r.confidence,
                    "is_ambiguous": r.is_ambiguous,
                    "human_approved": r.human_approved,
                }
                for r in rules
            ]
        }
        
        output_file = self.output_dir / "constraint_map.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _write_decision_log(self, decision_log: list[dict] | None) -> None:
        """Write decision log to JSON."""
        if not decision_log:
            return
        
        output_file = self.output_dir / "decision_log.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(decision_log, f, indent=2, ensure_ascii=False)

    def _write_cost_ledger(self, cost_ledger: CostLedger) -> None:
        """Write cost ledger to JSON."""
        if not cost_ledger:
            return
        
        data = {
            "entries": [
                {
                    "operation": e.operation,
                    "provider": e.provider,
                    "tokens_in": e.tokens_in,
                    "tokens_out": e.tokens_out,
                    "cost": e.cost,
                    "timestamp": e.timestamp.isoformat() if hasattr(e.timestamp, 'isoformat') else str(e.timestamp),
                    "budget_tag": e.budget_tag,
                }
                for e in cost_ledger.entries
            ],
            "total_cost": cost_ledger.total_cost,
            "budget_limit": cost_ledger.budget_limit,
            "budget_remaining": cost_ledger.budget_remaining,
        }
        
        output_file = self.output_dir / "cost_ledger.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


@dataclass
class EDLOutput:
    """Complete EDL output for a trailer in exact specification format."""
    trailer_id: str
    audience: str
    duration_seconds: float
    audience_promise: str
    segments: list[dict]
    validation: dict
    creative_brief: dict = None
    edl: list = None
    validation_summary: dict = None
    metadata: dict = None