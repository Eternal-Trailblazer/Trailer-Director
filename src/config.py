"""Config module."""

from __future__ import annotations

from pathlib import Path


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