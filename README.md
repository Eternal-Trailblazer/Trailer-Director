# Autonomous Trailer Director

> **OTT Dialect Platform — "Build an Autonomous Trailer Director" Assignment Submission**

## Overview

This system generates compliant, creative trailer plans for multiple audiences from episode materials. It implements all requirements from the assignment specification (§4–§12) with emphasis on **generality**, **safety**, **verifiability**, and **observability**.

## Key Features

- **Multi-audience planning**: Family, Young Adult, Dialect-Region (configurable)
- **Spoiler protection**: 3-layer detection (direct, ordering, inferential) with evidence citations
- **Rights enforcement**: Deterministic rule DSL compiled from policies/contracts
- **Bias auditing**: Proxy correlation, sample size, feature allow-list, identity-only checks
- **Independent verification**: Generator/verifier separation; deterministic checks first
- **Repair loop**: Max 3 iterations, targeted re-verification, never forces PASS
- **Change handling**: Dependency graph → selective replan → changelog
- **Mock/Replay mode**: Full pipeline runs without API keys
- **Structured outputs**: Creative brief + EDL (JSON) per trailer, validation report, decision log, cost ledger

## Quick Start

### Installation

```bash
cd submission
pip install -e .
# Or with dev dependencies:
pip install -e ".[dev]"
```

### Configuration

Edit `config/default_config.yaml` for:
- Audiences (add/remove/modify)
- Budget limits
- Model provider priority chain
- Trailer constraints (duration, segments, diversity)
- Spoiler/repair thresholds

### Running the Pipeline

```bash
# Full pipeline (mock mode - no API keys needed)
python -m src.cli run \
  --package ./episode_data/ \
  --config ./config/default_config.yaml \
  --output ./sample_run/ \
  --mock

# With live API keys (set ANTHROPIC_API_KEY or OPENAI_API_KEY)
python -m src.cli run \
  --package ./episode_data/ \
  --config ./config/default_config.yaml \
  --output ./sample_run/

# Individual commands
python -m src.cli ingest --package ./episode_data/ --config ./config/default_config.yaml
python -m src.cli plan --output ./sample_run/
python -m src.cli verify --plans ./sample_run/
python -m src.cli apply-change --event ./changes/music_expired.json --plans ./sample_run/
python -m src.cli replay --session ./replay_data/replay_session_01.jsonl
python -m src.cli report --plans ./sample_run/ --output ./sample_run/validation_report.md
```

### Expected Inputs

The pipeline accepts the 9 materials from §2 via file paths:

| Material | Flag | Formats |
|----------|------|---------|
| Episode Package | `--package` | MP4/MKV/MOV, clip directory, or JSON manifest |
| Scene Descriptions | `--scenes` | JSON, CSV, plain text, PDF |
| Dialogue & Subtitles | `--dialogue` | SRT, VTT, ASS, JSON, CSV |
| Rating Policies | `--policies` | JSON, YAML, PDF, text |
| Contracts | `--contracts` | JSON, YAML, PDF, text |
| Audience Profiles | `--audiences` | JSON, CSV, YAML |
| Historic Performance | `--history` | JSON, CSV |
| Cost Sheet | `--costs` | JSON, YAML, CSV |

Minimum viable: episode package (or manifest) + config. Missing materials → degraded mode with warnings.

### Outputs

All outputs written to `--output` directory:

```
sample_run/
├── story_map.json          # Canonical story map
├── spoiler_map.json        # Derived spoiler facts
├── constraint_map.json     # Compiled rules
├── family_trailer.json     # Creative brief + EDL + validation
├── young_adult_trailer.json
├── dialect_region_trailer.json
├── decision_log.json       # All decisions with evidence
├── cost_ledger.json        # Token usage and costs
├── validation_report.json  # Summary report
└── validation_report.md    # Human-readable report
```

## Testing

```bash
# Run all tests (mock mode)
pytest tests/ -v

# Run required §10 tests specifically
pytest tests/test_missing_scene.py tests/test_rights_restriction.py \
       tests/test_spoiler_detection.py tests/test_policy_failure.py \
       tests/test_changed_contract.py -v

# Run mutation tests
pytest tests/test_mutations.py -v

# Run property-based tests (requires hypothesis)
pytest tests/test_invariants.py -v

# Run generalisation test
pytest tests/test_generalisation.py -v -s
```

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for:
- Module diagram and data flow
- Algorithm details (spoiler detection, rule evaluation, arc selection)
- Configuration reference
- Scalability considerations

## AI Collaboration

See [AI_COLLABORATION.md](AI_COLLABORATION.md) for:
- Delegation patterns and verification practices
- "Plausible but wrong" log with 5 documented instances
- Human-in-the-loop decisions

## Known Limitations

See [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) for:
- Architectural, creative, safety limitations
- Human decision requirements
- Testing and performance gaps
- Schedule cut-list

## Repository Structure

```
submission/
├── README.md                 # This file
├── ARCHITECTURE.md           # System architecture
├── AI_COLLABORATION.md       # AI collaboration log
├── KNOWN_LIMITATIONS.md      # Limitations & human decisions
├── pyproject.toml            # Package config
├── config/
│   └── default_config.yaml   # Audiences, budgets, providers
├── src/
│   ├── cli.py                # CLI entry point
│   ├── pipeline.py           # Orchestrator
│   ├── config.py             # Config loader
│   ├── adapters/             # Input format parsers
│   ├── models/               # Pydantic schemas
│   ├── story_mapper/         # Story map construction
│   ├── spoiler_engine/       # Spoiler detection
│   ├── rule_compiler/        # Rule DSL + evaluator
│   ├── bias_auditor/         # Bias detection
│   ├── audience_strategist/  # Audience promise planning
│   ├── generator/            # Trailer generation
│   ├── verifier/             # Independent verification
│   ├── repair_engine/        # Repair loop
│   ├── change_handler/       # Change response
│   ├── edl_emitter/          # Output emission
│   ├── quarantine/           # Injection detection
│   ├── providers/            # Model abstraction + budget
│   ├── logging/              # Decision logging
│   └── human_registry/       # Approval tracking
├── tests/
│   ├── conftest.py           # Shared fixtures
│   ├── test_missing_scene.py      # §10 required
│   ├── test_rights_restriction.py # §10 required
│   ├── test_spoiler_detection.py  # §10 required
│   ├── test_policy_failure.py     # §10 required
│   ├── test_changed_contract.py   # §10 required
│   ├── test_injection.py
│   ├── test_bias.py
│   ├── test_model_unavailable.py
│   ├── test_budget_exceeded.py
│   ├── test_hallucinated_scene.py
│   ├── test_plan_diversity.py
│   ├── test_mutations.py
│   ├── test_invariants.py
│   ├── test_generalisation.py
│   └── generators/
│       └── package_generator.py
├── sample_run/               # Output directory (created at runtime)
└── replay_data/              # Recorded LLM responses
```

## Requirements

- Python 3.11+
- Dependencies: `pydantic>=2.8`, `click>=8.1`, `pyyaml>=6.0`, `python-dateutil>=2.8`
- Dev: `pytest>=7.4`, `hypothesis>=6.90`, `mypy>=1.8`, `ruff>=0.3`

## License

Assignment submission for OTT Dialect Platform evaluation.