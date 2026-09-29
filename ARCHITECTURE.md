# Architecture Document

## Autonomous Trailer Director — ARCHITECTURE.md

> **Purpose:** Documents the system architecture, design decisions, and technical implementation of the Autonomous Trailer Director for the OTT Dialect Platform assignment.

---

## 1. System Overview

The Autonomous Trailer Director is an end-to-end pipeline that generates compliant, creative trailer plans for multiple audiences from episode materials. It implements the requirements from §4–§8 of the assignment specification.

### 1.1 High-Level Pipeline

```
INGEST → NORMALIZE → STORY MAP → SPOILER MAP → CONSTRAINT COMPILATION
    → AUDIENCE STRATEGY → CANDIDATE GENERATION → INDEPENDENT VERIFICATION
    → REPAIR / REJECT → EDL EMISSION → CHANGE HANDLING (reactive loop)
```

### 1.2 Core Design Principles

1. **Generality First**: No episode-specific constants in core logic. All configurable values come from input data or config files.
2. **Deterministic Enforcement**: Safety-critical rules (rights, spoilers, policies) are compiled to a DSL and evaluated by pure Python — never by LLM prompt compliance.
3. **Generator/Verifier Independence**: Separate code paths, no shared mutable state. Verifier never sees generator's creative justification.
4. **Graceful Degradation**: `CapabilityReport` tracks what checks can/cannot run. Conservative defaults when inputs missing.
5. **Observability**: Structured decision logs, cost ledger, human-approval registry, change logs.
6. **Replayability**: Mock/Replay providers enable deterministic runs without API keys.

---

## 2. Module Architecture

### 2.1 Input Layer (`src/adapters/`)
- **AdapterBase**: Abstract base class for format-specific parsers
- **Registry**: Format detection + dispatch (JSON, SRT, VTT, ASS, CSV, plain text, PDF)
- **QuarantineGate**: Injection detection/neutralization on all untrusted text
- **CapabilityReport**: Emitted after ingestion, lists degraded capabilities

### 2.2 Canonical Data Store (`src/models/`)
- **Timecode**: Normalised millisecond representation with format conversion
- **Scene/Entity/Relationship**: Core episode structure
- **StoryMap**: Scenes, entities, events, emotional arc, causal graph
- **SpoilerFact**: Derived spoiler facts with evidence and confidence
- **Rule DSL**: Scope, effect, conditions with provenance
- **AudienceDefinition/Promise**: Configurable audiences with grounded promises
- **Segment/TrailerPlan**: Trailer structure with validation
- **ChangeEvent**: Generic change event model for §7 surprises

### 2.3 Planning Layer
- **StoryMapper** (`src/story_mapper/`): Builds StoryMap from episode materials using LLM extraction
- **SpoilerEngine** (`src/spoiler_engine/`): Derives SpoilerFacts from StoryMap using 5 heuristics
- **RuleCompiler** (`src/rule_compiler/`): LLM extracts rules from policies/contracts → DSL
- **BiasAuditor** (`src/bias_auditor/`): Statistical checks on audience profiles before personalisation
- **AudienceStrategist** (`src/audience_strategist/`): Plans audience promise BEFORE clip selection

### 2.4 Generation Layer (`src/generator/`)
- **TrailerGenerator**: Scores scenes by promise relevance, filters by rules/spoilers, selects per arc template (setup→tension→hook), ensures diversity

### 2.5 Verification Layer (`src/verifier/`)
- **Deterministic checks** (run first):
  - SourceAccuracy: Scene existence, timecode bounds
  - RightsChecker: RuleEvaluator on all DENY/LIMIT rules
  - AudienceSafety: Rating policy enforcement
  - TimecodeValidator: Ordering, frame-rate consistency
  - Accessibility: Subtitle presence, text readability
  - BudgetCheck: Cost ledger vs limit
- **LLM checks** (run second):
  - SpoilerChecker: Direct, ordering, inferential reveals
  - StoryTruthJudge: No manufactured relationships/threats
  - DialectDriftChecker: Cross-check dialect subtitles vs source
  - CreativeQualityJudge: Arc structure, engagement-only guardrail

### 2.6 Repair Layer (`src/repair_engine/`)
- **RepairEngine**: Max 3 iterations, replaces failed segments, re-verifies only affected checks, never forces PASS

### 2.7 Change Handling (`src/change_handler/`)
- **DependencyGraph**: Tracks scene↔entity↔rule↔spoiler↔segment↔trailer dependencies
- **ChangeHandler**: Impact analysis → selective replan → targeted re-verification → changelog

### 2.8 Output Layer (`src/edl_emitter/`)
- **EDLEmitter**: Creative brief + EDL (JSON) per trailer, validation summary, cost ledger

### 2.9 Infrastructure
- **ModelProvider** abstraction with FallbackChain (`src/providers/`)
- **BudgetController**: Real-time cost tracking with limits
- **DecisionLogger**: Structured decision log with evidence
- **HumanRegistry**: Approval tracking for ambiguous/cultural decisions

---

## 3. Data Flow

### 3.1 Ingestion Phase
```
Raw Files → Adapters → Schema Validation → QuarantineGate → Canonical Records → CapabilityReport
```

### 3.2 Planning Phase
```
StoryMap + SpoilerFacts + Rules + Audiences → BiasAudit → AudiencePromises (per audience)
```

### 3.3 Generation Phase
```
AudiencePromise + StoryMap + SpoilerFacts + Rules → Scene Scoring → Arc Selection → Segments → TrailerPlan
```

### 3.4 Verification Phase
```
TrailerPlan + StoryMap + SpoilerFacts + Rules → Deterministic Checks → LLM Judges → TrailerValidation
```

### 3.5 Repair Phase
```
FAIL checks → Replacement Search → Re-verify (affected only) → PASS/REJECT
```

### 3.6 Change Handling
```
ChangeEvent → DependencyGraph.affected() → Selective Regeneration → Targeted Re-verification → Changelog
```

---

## 4. Key Algorithms

### 4.1 Spoiler Detection (3-layer)
1. **Direct Reveal**: Segment scene ∈ SpoilerFact.involved_scenes
2. **Ordering Reveal**: Trailer segment order reveals causal chain prematurely
3. **Inferential Reveal**: LLM judge on combined dialogue (requires evidence citation)

### 4.2 Rule Evaluation
- Pure Python predicate evaluation: `field operator value`
- Operators: eq, ne, gt, lt, gte, lte, in, not_in, contains, before, after
- Short-circuit on first DENY; collect all LIMITs

### 4.3 Arc-Based Scene Selection
- Template: Setup(1-2) → Tension(2-3) → Hook(1)
- Scoring: Promise evidence + emotional arc alignment + event type
- Filtering: Rules (DENY), Spoilers (direct), Characterisation
- Diversity: Jaccard distance ≥ 0.4 across trailers

### 4.4 Bias Auditing
1. Proxy correlation detection (Cramér's V approximation)
2. Small sample warning (n < 30)
3. Feature allow-list enforcement (behavioural only)
4. Identity-only justification flag

---

## 5. Configuration

All configurable via `config/default_config.yaml`:
- Audiences (list, not hardcoded)
- Budget limits (USD, call count, media processing)
- Model provider priority chain
- Trailer constraints (duration, segments, diversity)
- Spoiler thresholds (late_episode_threshold, confidence)
- Repair limits (max_iterations)

---

## 6. Error Handling & Degradation

| Missing Input | Degradation | Warning |
|--------------|-------------|---------|
| Video files | Text-only mode, no visual analysis | `WARN_NO_VIDEO` |
| Scene descriptions | Partial story map, uncharacterised scenes restricted | `WARN_NO_SCENE_DESC` |
| Source dialogue | No dialect drift check | `WARN_NO_SOURCE_DIALOGUE` |
| Policies | Maximally restrictive defaults | `WARN_NO_POLICIES` |
| Contracts | DENY all asset use | `WARN_NO_CONTRACTS` |
| Audience profiles | Generic promise from story map only | `WARN_NO_AUDIENCE_DATA` |
| LLM unavailable | Deterministic checks only, escalate LLM checks | `WARN_LLM_UNAVAILABLE` |

---

## 7. Testing Strategy

### 7.1 Required Tests (§10)
- `test_missing_scene`: Source accuracy FAIL
- `test_rights_restriction`: Rights FAIL on DENY rule
- `test_spoiler_detection`: Spoiler FAIL on twist scene
- `test_policy_failure`: Audience safety FAIL for family+violence
- `test_changed_contract`: Selective replan on asset expiry

### 7.2 Extended Mutation Tests
- Injection blocking, bias detection, model fallback, budget limit, hallucination, diversity

### 7.3 Property-Based Invariants (Hypothesis)
- Segments resolve to existing scenes
- Timecodes within scene bounds
- No PASS with unresolved FAIL
- Budget not exceeded
- Replay determinism

---

## 8. Security Considerations

1. **Prompt Injection**: QuarantineGate on all untrusted text (scene descriptions, dialogue, audience profiles, historic data)
2. **Rule Enforcement**: Deterministic evaluator — LLM cannot override DENY rules
3. **Conservative Defaults**: Ambiguous clauses → DENY + human review flag
4. **Evidence Requirements**: Every LLM verdict must cite resolvable evidence IDs

---

## 9. Scalability Considerations

| Component | Scaling Behavior | Mitigation |
|-----------|------------------|------------|
| Deterministic checks | O(segments × rules) | Fast, no API calls |
| LLM verification | O(scenes × checks × trailers) | Parallelize, pre-filter, cache |
| Rule extraction | O(policy_length) | One-time, cache results |
| Dependency graph | O(nodes + edges) | Incremental updates |

**Bottleneck**: LLM verification layer at scale. Mitigations: chunking, parallelism, aggressive pre-filtering.

---

## 10. Deployment

- **CLI**: `python -m src.cli run --package ... --config ... --output ...`
- **Mock Mode**: `--mock` flag for API-key-free execution
- **Replay Mode**: `--replay` for deterministic regression testing
- **Outputs**: `sample_run/` with story_map.json, spoiler_map.json, constraint_map.json, *_trailer.json, decision_log.json, cost_ledger.json, validation_report.md