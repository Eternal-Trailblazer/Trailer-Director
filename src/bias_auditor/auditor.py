"""Bias auditor for audience personalisation decisions."""

from __future__ import annotations

from typing import Any
from dataclasses import dataclass, field
from collections import Counter

from src.models.audience import AudienceDefinition


@dataclass
class BiasCheck:
    """Individual bias check result."""
    check_name: str
    flagged: bool
    details: str
    severity: str  # "warning", "error"
    evidence: list[str] = field(default_factory=list)


@dataclass
class BiasReport:
    """Full bias audit report."""
    checks: list[BiasCheck] = field(default_factory=list)
    
    @property
    def has_flags(self) -> bool:
        return any(c.flagged for c in self.checks)
    
    @property
    def has_errors(self) -> bool:
        return any(c.flagged and c.severity == "error" for c in self.checks)
    
    @property
    def flags_summary(self) -> list[str]:
        return [f"{c.check_name}: {c.details}" for c in self.checks if c.flagged]


class BiasAuditor:
    """Audits audience profiles and personalisation decisions for bias."""

    # Features that should NEVER be used alone for personalisation
    IDENTITY_FEATURES = {
        "dialect", "language", "region", "country", "ethnicity", "race", 
        "gender", "age", "religion", "nationality", "accent"
    }
    
    # Features that ARE acceptable for personalisation
    BEHAVIOURAL_FEATURES = {
        "preference", "preferences", "engagement_pattern", "engagement_patterns", "watch_history", "genre_preference",
        "content_affinity", "stated_interests", "feedback_scores", "engagement", "history"
    }

    def __init__(self, min_sample_size: int = 30, correlation_threshold: float = 0.8):
        self.min_sample_size = min_sample_size
        self.correlation_threshold = correlation_threshold

    def audit(
        self, 
        audience_profiles: list[AudienceDefinition],
        personalisation_decisions: list[dict]
    ) -> BiasReport:
        """Run all bias checks."""
        checks = [
            self._check_proxy_correlations(audience_profiles),
            self._check_small_sample(audience_profiles),
            self._check_feature_allowlist(personalisation_decisions),
            self._check_identity_only_justification(personalisation_decisions),
        ]
        return BiasReport(checks=checks)

    def _check_proxy_correlations(self, profiles: list[AudienceDefinition]) -> BiasCheck:
        """Detect if identity attributes correlate suspiciously with content preferences."""
        if len(profiles) < 2:
            return BiasCheck(
                check_name="proxy_correlations",
                flagged=False,
                details="Insufficient profiles for correlation analysis",
                severity="warning"
            )

        # Extract features from profiles
        identity_values = {}
        preference_values = {}
        
        for profile in profiles:
            # Identity features - check both model fields and extra fields
            for key in ["dialect", "language", "region", "country", "age_range"]:
                val = getattr(profile, key, None)
                # Also check model_extra for Pydantic v2
                if val is None and hasattr(profile, 'model_extra') and profile.model_extra:
                    val = profile.model_extra.get(key)
                if val:
                    identity_values.setdefault(key, []).append(str(val))
            
            # Preference features (from preferences dict)
            for pref_key, pref_val in profile.preferences.items():
                preference_values.setdefault(pref_key, []).append(str(pref_val))
            
            # Engagement patterns
            for eng_key, eng_val in profile.engagement_patterns.items():
                preference_values.setdefault(f"engagement_{eng_key}", []).append(str(eng_val))

        # Check for perfect/near-perfect correlations
        flagged_correlations = []
        for id_key, id_vals in identity_values.items():
            unique_id = len(set(id_vals))
            if unique_id <= 1:
                continue  # No variation
            
            for pref_key, pref_vals in preference_values.items():
                if len(id_vals) != len(pref_vals):
                    continue
                
                # Check if identity perfectly predicts preference
                correlation = self._compute_correlation(id_vals, pref_vals)
                if correlation >= self.correlation_threshold:
                    flagged_correlations.append(f"{id_key} -> {pref_key} (r={correlation:.2f})")

        if flagged_correlations:
            return BiasCheck(
                check_name="proxy_correlations",
                flagged=True,
                details=f"High correlations detected: {'; '.join(flagged_correlations)}",
                severity="error",
                evidence=flagged_correlations
            )
        
        return BiasCheck(
            check_name="proxy_correlations",
            flagged=False,
            details="No proxy correlations above threshold",
            severity="warning"
        )

    def _compute_correlation(self, x_vals: list[str], y_vals: list[str]) -> float:
        """Compute correlation between categorical variables using Cramér's V approximation."""
        # Simple approach: check if each x value maps to single y value
        mapping = {}
        for x, y in zip(x_vals, y_vals):
            if x not in mapping:
                mapping[x] = set()
            mapping[x].add(y)
        
        # If each x maps to exactly one y, perfect correlation
        deterministic = all(len(ys) == 1 for ys in mapping.values())
        if deterministic:
            return 1.0
        
        # Otherwise compute approximate correlation
        return 0.5  # Simplified

    def _check_small_sample(self, profiles: list[AudienceDefinition]) -> BiasCheck:
        """Flag audience segments with sample sizes below threshold."""
        small_segments = []
        
        for profile in profiles:
            # Check if profile has sample size info
            sample_size = profile.engagement_patterns.get("sample_size", 0)
            if sample_size and sample_size < self.min_sample_size:
                small_segments.append(f"{profile.audience_id} (n={sample_size})")
            
            # Also check preferences for sample size
            for key, val in profile.preferences.items():
                if isinstance(val, dict) and "sample_size" in val:
                    if val["sample_size"] < self.min_sample_size:
                        small_segments.append(f"{profile.audience_id}.{key} (n={val['sample_size']})")

        if small_segments:
            return BiasCheck(
                check_name="small_sample",
                flagged=True,
                details=f"Segments below minimum sample size ({self.min_sample_size}): {'; '.join(small_segments)}",
                severity="warning",
                evidence=small_segments
            )
        
        return BiasCheck(
            check_name="small_sample",
            flagged=False,
            details="All segments meet minimum sample size",
            severity="warning"
        )

    def _check_feature_allowlist(self, decisions: list[dict]) -> BiasCheck:
        """Ensure personalisation only uses approved features."""
        violations = []
        
        for decision in decisions:
            evidence = decision.get("evidence", [])
            features_used = set()
            
            for ev in evidence:
                # Extract feature names from evidence
                if ":" in ev:
                    feature = ev.split(":")[0].lower()
                    features_used.add(feature)
                else:
                    features_used.add(ev.lower())
            
            # Check if any identity features used without behavioural features
            identity_used = features_used & self.IDENTITY_FEATURES
            behavioural_used = features_used & self.BEHAVIOURAL_FEATURES
            
            if identity_used and not behavioural_used:
                violations.append(
                    f"Decision {decision.get('decision_id', 'unknown')}: "
                    f"uses identity features {identity_used} without behavioural evidence"
                )

        if violations:
            return BiasCheck(
                check_name="feature_allowlist",
                flagged=True,
                details=f"Feature allowlist violations: {'; '.join(violations)}",
                severity="error",
                evidence=violations
            )
        
        return BiasCheck(
            check_name="feature_allowlist",
            flagged=False,
            details="All decisions use approved features",
            severity="warning"
        )

    def _check_identity_only_justification(self, decisions: list[dict]) -> BiasCheck:
        """Flag decisions justified only by identity attributes."""
        violations = []
        
        for decision in decisions:
            evidence = decision.get("evidence", [])
            reason = decision.get("reason", "").lower()
            
            # Check if evidence only contains identity features
            identity_evidence = [e for e in evidence if any(id_feat in e.lower() for id_feat in self.IDENTITY_FEATURES)]
            behavioural_evidence = [e for e in evidence if any(b_feat in e.lower() for b_feat in self.BEHAVIOURAL_FEATURES)]
            
            # Also check reason text
            identity_in_reason = any(id_feat in reason for id_feat in self.IDENTITY_FEATURES)
            behavioural_in_reason = any(b_feat in reason for b_feat in self.BEHAVIOURAL_FEATURES)
            
            if (identity_evidence or identity_in_reason) and not (behavioural_evidence or behavioural_in_reason):
                violations.append(
                    f"Decision {decision.get('decision_id', 'unknown')}: "
                    f"justified only by identity (evidence: {identity_evidence}, reason mentions identity: {identity_in_reason})"
                )

        if violations:
            return BiasCheck(
                check_name="identity_only_justification",
                flagged=True,
                details=f"Identity-only justifications: {'; '.join(violations)}",
                severity="error",
                evidence=violations
            )
        
        return BiasCheck(
            check_name="identity_only_justification",
            flagged=False,
            details="All decisions have behavioural justification",
            severity="warning"
        )