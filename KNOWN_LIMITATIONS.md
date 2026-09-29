# Known Limitations

## Autonomous Trailer Director — KNOWN_LIMITATIONS.md

> **Purpose:** Honest documentation of current limitations, trade-offs, and human-decision requirements.

---

## 1. Architectural Limitations

### 1.1 LLM Verification Layer Scalability
- **Limitation**: LLM-based checks (spoiler inference, story truth, dialect drift, creative quality) scale linearly with scenes × checks × trailers
- **Impact**: At 100+ scenes, verification becomes slow and expensive
- **Mitigation**: Deterministic pre-filtering; parallel execution; chunking; caching
- **Future**: Replace with smaller specialized models or distilled classifiers

### 1.2 No Real Video Analysis
- **Limitation**: `CapabilityReport.has_video = false` path only; no frame-level visual analysis
- **Impact**: Visual content tags, violence detection, emotional tone rely on scene descriptions only
- **Trade-off**: Cut per schedule (see ARCHITECTURE.md cut-list priority 1)
- **Future**: Integrate vision model for keyframe analysis when video present

### 1.3 Rule Extraction Accuracy
- **Limitation**: LLM extraction of rules from legal text may miss nuances or hallucinate conditions
- **Impact**: Ambiguous clauses → conservative DENY + human review flag
- **Mitigation**: Provenance tracking (`source_span`); confidence scores; human approval for `is_ambiguous`
- **Future**: Fine-tuned legal NER model; structured contract templates

---

## 2. Creative Quality Limitations

### 2.1 Template-Based Arc Structure
- **Limitation**: Fixed Setup→Tension→Hook template; no learned narrative structures
- **Impact**: May not fit all episode genres (e.g., anthology, non-linear)
- **Mitigation**: Template configurable via config; evidence-based scene selection
- **Future**: Learn arc templates from successful trailers per genre

### 2.2 Limited NLG Polish
- **Limitation**: `audience_promise` text and segment `reason` fields are LLM-generated but not post-edited
- **Impact**: Creative brief text may be functional but not marketing-ready
- **Trade-off**: Cut per scoring strategy (creative quality 15% — focus on structural enforcement over polish)

### 2.3 Diversity Metric Simplicity
- **Limitation**: Jaccard distance on scene-ID sets only
- **Impact**: Trailers with different scenes but same emotional beats may pass diversity check
- **Future**: Semantic diversity (embedding-based) + arc structure diversity

---

## 3. Safety & Rights Limitations

### 3.1 Conservative Defaults May Over-Block
- **Limitation**: Missing policies/contracts → maximally restrictive (DENY all)
- **Impact**: Usable trailers may not generate without complete rights data
- **Mitigation**: Clear warnings (`WARN_NO_POLICIES`, `WARN_NO_CONTRACTS`); human approval path

### 3.2 Dialect Drift Detection Quality
- **Limitation**: LLM-based cross-check depends on model's proficiency in specific dialect
- **Impact**: Low-resource dialects may have false negatives/positives
- **Mitigation**: Confidence thresholds; human review for `WARN_DIALECT_DRIFT`

### 3.3 Bias Auditor Coverage
- **Limitation**: Statistical checks only (proxy correlation, sample size, feature allow-list, identity-only)
- **Impact**: Cannot detect subtle semantic biases or intersectional biases
- **Future**: Integration with dedicated bias evaluation benchmarks

---

## 4. Change Handling Limitations

### 4.1 Selective Replan Granularity
- **Limitation**: Replans at segment level; cannot do intra-segment edits (e.g., trim 2 seconds from 10s clip)
- **Impact**: May replace entire segment when minor trim would suffice
- **Mitigation**: Timecode validation catches bounds issues; repair tries alternatives

### 4.2 Dependency Graph Completeness
- **Limitation**: Graph built from current outputs; may miss implicit dependencies (e.g., thematic consistency)
- **Impact**: Change to one segment may require creative re-balance not captured
- **Mitigation**: Human review flag on `MARKETING_DIRECTIVE` changes

---

## 5. Input Format Limitations

### 5.1 PDF Adapter Dependency
- **Limitation**: Requires `pdfplumber` package; not in core dependencies
- **Impact**: PDF ingestion fails gracefully with warning if package missing
- **Trade-off**: Cut per schedule (priority 4)

### 5.2 Timecode Format Edge Cases
- **Limitation**: Drop-frame (SMPTE DF) conversion uses approximation
- **Impact**: Sub-frame accuracy loss for long-form content
- **Mitigation**: Frame-accurate conversion library for production

### 5.3 Subtitle Format Coverage
- **Limitation**: SRT, VTT, ASS supported; other formats (TTML, SCC, EBU-STL) not implemented
- **Impact**: Non-standard subtitle files require conversion pre-processing

---

## 6. Human Decision Requirements

The following decisions **require human approval** and cannot be fully automated:

| Decision Type | Trigger | Registry Entry |
|---------------|---------|----------------|
| Ambiguous rule interpretation | `Rule.is_ambiguous = True` | `ambiguous_rule` |
| Cultural sensitivity review | `BiasAuditor` flags `BIAS_IDENTITY_ONLY` or `BIAS_PROXY_CORRELATION` | `cultural_sensitivity` |
| Creative override | Marketing directive conflicts with story truth | `creative_override` |
| Spoiler verdict uncertainty | `SpoilerVerdict.verdict = "UNVERIFIED"` | `cultural_sensitivity` |
| Asset substitution | No valid replacement found in repair | `creative_override` |
| Budget reallocation | Over-budget with critical segments | `creative_override` |

---

## 7. Testing Limitations

### 7.1 Property-Based Tests Reduced
- **Limitation**: Hypothesis tests limited to 50 examples; not exhaustive
- **Impact**: Edge cases in timecode arithmetic, scene ordering may be missed
- **Mitigation**: Mutation tests cover known fault classes

### 7.2 Generalisation Report Sample Size
- **Limitation**: 5 packages (reduced from 20 per cut-list)
- **Impact**: Statistical confidence lower for pass/escalation/cost rates
- **Mitigation**: Core invariants tested exhaustively via mutation tests

### 7.3 No Real Episode Integration Test
- **Limitation**: All tests use synthetic packages; no validation on real episode data
- **Impact**: Real-world format quirks, encoding issues not exercised
- **Future**: Integration test with provided evaluation dataset

---

## 8. Performance Limitations

### 8.1 No Parallelism in Current Implementation
- **Limitation**: Sequential LLM calls in verification, generation, story mapping
- **Impact**: Wall-clock time scales with number of checks × trailers
- **Future**: Async execution with semaphore for rate limiting

### 8.2 No Caching Layer
- **Limitation**: Repeated LLM calls for same inputs (e.g., same scene analyzed multiple times)
- **Impact**: Unnecessary cost and latency
- **Future**: Redis/memory cache keyed by input hash + model version

### 8.3 Memory Usage
- **Limitation**: Full story map, all rules, all segments in memory
- **Impact**: Large episodes (1000+ scenes) may exceed memory
- **Future**: Streaming/chunked processing for story map

---

## 9. Cut List (Per Schedule)

| Priority | Feature Cut | Impact | Documented In |
|----------|-------------|--------|---------------|
| 1 | Frame-level video analysis | Text-only multimodal mode | This file, ARCHITECTURE.md |
| 2 | Sophisticated auto-repair | Simple replacement or escalate | RepairEngine docs |
| 3 | Hypothesis property tests (full) | Manual mutation tests retained | This file |
| 4 | PDF adapter | Graceful degradation warning | Adapter docs |
| 5 | Generalisation report (20→5) | Lower statistical confidence | This file |

**Never Cut** (and verified implemented):
- Core verifier checks (source accuracy, rights, spoiler, safety)
- Rule evaluator (deterministic)
- Spoiler detection (3-layer)
- 5 required tests (§10)
- Mock/replay mode
- Decision log / cost ledger / human registry

---

## 10. Honest Assessment

**What works well:**
- Deterministic constraint enforcement (rules, spoilers, rights)
- Generator/verifier independence with evidence-based verdicts
- Change handling with dependency graph
- Mock/replay mode for deterministic CI
- Comprehensive test coverage of safety-critical paths

**What needs improvement for production:**
- LLM verification latency and cost at scale
- Real video analysis integration
- Rule extraction accuracy on complex contracts
- Creative quality polish (NLG)
- Parallel execution and caching
- Real episode format validation

**Human oversight required for:**
- Ambiguous legal clauses
- Cultural sensitivity edge cases
- Creative disagreements between generator and verifier
- Budget vs quality trade-offs
- Marketing directives that conflict with story truth

---

*This document is living — update as limitations are addressed or new ones discovered.*