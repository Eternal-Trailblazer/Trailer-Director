# AI Collaboration Document

## Autonomous Trailer Director — AI_COLLABORATION.md

> **Purpose:** Documents the AI collaboration process, delegation patterns, verification practices, and "plausible but wrong" instances encountered during development.

---

## 1. AI Tools Used

- **Primary**: Claude (Anthropic) for code generation, architecture design, test scaffolding, documentation drafting
- **Secondary**: GitHub Copilot / Codex for boilerplate completion, import management, minor refactoring

---

## 2. Delegation Patterns

| Task | Delegated to AI? | Verification Method |
|------|------------------|---------------------|
| Pydantic schema generation (40+ models) | ✅ Yes | Manual review of field types, validators, relationships; `mypy` strict mode |
| Adapter boilerplate (JSON, SRT, VTT, CSV, plain text, PDF) | ✅ Yes | Unit tests with sample data; format edge cases |
| Rule extraction prompts | ✅ Yes | Verify extracted rules against source text manually; round-trip test |
| Spoiler detection logic | ⚠️ Partial | AI drafted heuristics; manually walked through each detection pathway with test cases |
| Rule evaluator (deterministic) | ❌ No | Written manually; safety-critical; line-by-line review |
| Test generation (fixtures, mutation tests, property tests) | ✅ Yes | Verify assertions are correct, not vacuously true; run and confirm failures |
| Documentation drafts (ARCHITECTURE.md, this file, KNOWN_LIMITATIONS.md) | ✅ Yes | Edit for accuracy, honesty, completeness |
| Creative prompts (audience promise, arc templates) | ✅ Yes | Review for story-truth grounding; check against §6 constraints |
| CLI command structure | ✅ Yes | Manual testing of all subcommands |

---

## 3. Challenge-and-Verify Practice

For every AI-generated code block:

1. **Read line by line** before accepting
2. **Challenge**: "What input would make this fail?" → Write that test
3. **Verify against spec**: Does this match the §6 constraint it implements?
4. **Run tests**: Ensure new code doesn't break existing tests

---

## 4. "Plausible but Wrong" Log

### Entry 1
- **Date/Time**: 2026-09-28 10:15
- **Tool**: Claude
- **Prompt summary**: "Generate spoiler detection heuristics for the SpoilerEngine"
- **Suggestion**: 
  ```python
  # AI suggested keyword-based spoiler detection
  SPOILER_KEYWORDS = ["dies", "death", "killer", "murder", "twist", "reveal", "secret", "betrayal"]
  def is_spoiler(text):
      return any(kw in text.lower() for kw in SPOILER_KEYWORDS)
  ```
- **Why it looked plausible**: Simple, fast, catches obvious spoilers
- **Why it was wrong**: 
  - High false positives (e.g., "character *dies* of laughter" in comedy)
  - Misses contextual spoilers (causal reveals without keywords)
  - Violates §8 "no domain knowledge" requirement — keywords are domain-specific
  - No evidence citation as required by §6
- **How I caught it**: Unit test with "dies of laughter" scene → false positive; mutation test inserting keyword in non-spoiler scene
- **Corrected approach**: Story-map-derived SpoilerFacts with 3-layer detection (direct, ordering, inferential) + evidence citations

### Entry 2
- **Date/Time**: 2026-09-28 11:30
- **Tool**: Claude
- **Prompt summary**: "Design the scene selection algorithm for TrailerGenerator"
- **Suggestion**:
  ```python
  # AI suggested engagement-score-based selection
  def select_scenes(scenes, engagement_scores, n):
      return sorted(scenes, key=lambda s: engagement_scores.get(s.scene_id, 0), reverse=True)[:n]
  ```
- **Why it looked plausible**: Common industry practice; maximizes predicted engagement
- **Why it was wrong**:
  - Violates §11 anti-pattern: "Selecting clips only from historic engagement scores"
  - Violates §4.3: "Plan audience promise BEFORE clip selection"
  - Violates §8: "Creative planning: audience promise → narrative arc (not clip-ranking)"
  - No story-truth grounding, no arc structure
- **How I caught it**: Re-read §11 scoring strategy and anti-patterns table; wrote guardrail test `WARN_ENGAGEMENT_ONLY`
- **Corrected approach**: Arc-template selection (setup→tension→hook) scored by promise evidence + emotional arc alignment

### Entry 3
- **Date/Time**: 2026-09-28 13:45
- **Tool**: Claude
- **Prompt summary**: "How to handle rating policies in the verifier?"
- **Suggestion**:
  ```python
  # AI suggested putting policy text in LLM system prompt
  SYSTEM_PROMPT = f"""You are a trailer verifier. Enforce these policies:
  {policy_text}
  Check each segment for violations."""
  ```
- **Why it looked plausible**: Natural language policies → LLM understands nuance
- **Why it was wrong**:
  - Violates §8: "Constraint reasoning: policies/contracts as decision rules, not prompt paragraphs"
  - Violates §6: "Hard constraint" — LLM prompt compliance is not deterministic enforcement
  - No provenance, no audit trail, cannot be independently verified
  - Prompt injection could override policies
- **How I caught it**: Cross-referenced with §8 "Constraint reasoning" requirement and §6 "Hard constraint" type
- **Corrected approach**: RuleCompiler extracts DSL rules with provenance; RuleEvaluator enforces deterministically

### Entry 4
- **Date/Time**: 2026-09-28 15:20
- **Tool**: Codex
- **Prompt summary**: "Write a test for the verifier's spoiler check"
- **Suggestion**:
  ```python
  def test_spoiler_check():
      result = run_verifier(trailer)
      assert result.validation.status != "FAIL"  # Vacuous!
  ```
- **Why it looked plausible**: Test passes, looks like it checks something
- **Why it was wrong**: 
  - Vacuously true — doesn't assert specific spoiler detection behavior
  - Doesn't verify evidence citation requirement
  - Doesn't test the three check types (direct, ordering, inferential)
- **How I caught it**: Code review — "What does this test actually verify?" → realized it asserts nothing meaningful
- **Corrected approach**: Mutation test injecting spoiler scene → assert FAIL with specific evidence

### Entry 5
- **Date/Time**: 2026-09-28 16:00
- **Tool**: Claude
- **Prompt summary**: "Generate a diverse set of test audiences for the package generator"
- **Suggestion**:
  ```python
  # AI generated audiences with stereotypical associations
  audiences = [
      {"audience_id": "rural", "preferences": {"genre": "action"}},
      {"audience_id": "urban", "preferences": {"genre": "romance"}},
      {"audience_id": "elderly", "preferences": {"genre": "drama"}},
  ]
  ```
- **Why it looked plausible**: Creates variety for testing
- **Why it was wrong**:
  - Encodes demographic stereotypes (rural→action, urban→romance, elderly→drama)
  - Would trigger BiasAuditor proxy correlation flags in our own tests
  - Violates §6 "Cultural respect: no dialect/location stereotypes"
- **How I caught it**: Ran BiasAuditor on generated test data → flagged `BIAS_PROXY_CORRELATION`
- **Corrected approach**: Generate audiences with randomized preferences, no demographic correlations

---

## 5. Verification Discipline

### 5.1 Code Review Checklist for AI-Generated Code
- [ ] No hardcoded episode/audience/dialect constants
- [ ] Deterministic enforcement for safety-critical paths
- [ ] Evidence citations on all LLM verdicts
- [ ] Conservative defaults for ambiguous inputs
- [ ] Graceful degradation with CapabilityReport updates
- [ ] Decision logging with evidence and alternatives

### 5.2 Test Verification Checklist
- [ ] Assertions check specific behavior, not just "not FAIL"
- [ ] Mutation tests exist for each guardrail
- [ ] Property tests cover invariants, not just happy path
- [ ] Tests fail when injected with known violations

---

## 6. Human-in-the-Loop Decisions

The following decisions were made by human judgment, not delegated:

1. **RuleEvaluator implementation**: Pure Python predicate evaluation — safety-critical
2. **SpoilerFact derivation heuristics**: 5 specific heuristic types — domain-agnostic but require design
3. **Arc template structure**: Setup→Tension→Hook — creative constraint from §4.4
4. **Diversity threshold (0.4 Jaccard)**: Calibrated from §11 anti-pattern table
5. **Bias feature allow-lists**: IDENTITY_FEATURES vs BEHAVIOURAL_FEATURES — policy decision
6. **Repair iteration cap (3)**: Balance between auto-recovery and infinite loops
7. **Conservative defaults**: DENY on ambiguity — risk tolerance decision

---

## 7. Summary

**AI was delegated**: Schema generation, adapter boilerplate, test scaffolding, documentation drafts, creative prompts, CLI structure, mutation test patterns.

**AI was challenged**: Spoiler detection approach, scene selection algorithm, policy enforcement mechanism, test assertion quality, demographic stereotyping in test data.

**Human retained**: Safety-critical deterministic logic, heuristic design, creative constraints, risk decisions, verification discipline.

This collaboration pattern — AI for velocity on well-specified tasks, human for safety-critical design and verification — aligns with §11 evaluation criteria for "Use of AI tools."