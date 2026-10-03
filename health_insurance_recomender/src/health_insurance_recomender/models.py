from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ProfileResult:
    client_profile: dict[str, Any]
    derived_features: dict[str, Any]
    stated_priorities: list[str] = field(default_factory=list)
    known_constraints: list[str] = field(default_factory=list)
    missing_critical_info: list[str] = field(default_factory=list)
    assumptions_used: list[str] = field(default_factory=list)
    followup_questions_asked: list[str] = field(default_factory=list)
    followup_questions_still_recommended: list[str] = field(default_factory=list)
    preference_weight_seed: dict[str, float] = field(default_factory=dict)
    profile_confidence: str = "low"
    uncertainty_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ScoredPlan:
    rank: int
    plan_id: str
    plan_name: str
    issuer_name: str
    state: str
    county: str
    premium: float
    deductible: float
    moop: float
    expected_yearly_cost: float
    composite_score: float
    network_type: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ScoringResult:
    status: str
    ranking_basis: str
    plans_considered: list[str]
    scored_plans: list[ScoredPlan] = field(default_factory=list)
    gaps: list[dict[str, Any]] = field(default_factory=list)
    stability: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["scored_plans"] = [plan.to_dict() for plan in self.scored_plans]
        return payload
