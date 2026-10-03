from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .models import ScoredPlan, ScoringResult


def load_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: str | Path, payload: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def _normalize_inverse(value: float, min_value: float, max_value: float) -> float:
    if max_value == min_value:
        return 1.0
    return (max_value - value) / (max_value - min_value)


def _normalize(value: float, min_value: float, max_value: float) -> float:
    if max_value == min_value:
        return 1.0
    return (value - min_value) / (max_value - min_value)


def _expected_yearly_cost(plan: dict[str, Any], profile: dict[str, Any]) -> float:
    intensity = profile["derived_features"]["estimated_care_intensity"]
    meds = len(profile["client_profile"]["medications"].get("current_medications", []))
    pcp_copay = plan.get("pcp_copay", 0)
    specialist_copay = plan.get("specialist_copay", 0)
    generic_rx_copay = plan.get("generic_rx_copay", 0)
    premium = float(plan["premium"]) * 12
    deductible = float(plan["deductible"])
    moop = float(plan["moop"])

    if intensity == "low":
        utilization_cost = 0.10 * deductible + 2 * pcp_copay + meds * 6 * generic_rx_copay
    elif intensity == "moderate":
        utilization_cost = 0.35 * deductible + 4 * pcp_copay + 2 * specialist_copay + meds * 10 * generic_rx_copay
    else:
        utilization_cost = 0.75 * deductible + 6 * pcp_copay + 5 * specialist_copay + meds * 12 * generic_rx_copay

    return round(min(premium + utilization_cost, premium + moop), 2)


def score_plans(user_answers: dict[str, Any], profile: dict[str, Any], plans: list[dict[str, Any]]) -> ScoringResult:
    state = user_answers.get("state")
    county = user_answers.get("county")
    if not state or not county:
        return ScoringResult(
            status="insufficient_data",
            ranking_basis="composite_score",
            plans_considered=[],
            scored_plans=[],
            gaps=[],
            stability={"status": "not_tested", "reason": "missing geography"},
        )

    candidate_plans = [
        plan for plan in plans if plan.get("state") == state and plan.get("county") == county
    ]

    if not candidate_plans:
        return ScoringResult(
            status="no_matching_plans",
            ranking_basis="composite_score",
            plans_considered=[],
            scored_plans=[],
            gaps=[{"fact": "matching_plans", "why": f"No plans matched {state}/{county}"}],
            stability={"status": "not_tested", "reason": "no candidates"},
        )

    for plan in candidate_plans:
        plan["expected_yearly_cost"] = _expected_yearly_cost(plan, profile)

    premiums = [float(plan["premium"]) for plan in candidate_plans]
    deductibles = [float(plan["deductible"]) for plan in candidate_plans]
    moops = [float(plan["moop"]) for plan in candidate_plans]
    yearly_costs = [float(plan["expected_yearly_cost"]) for plan in candidate_plans]
    network_scores = [float(plan.get("network_score", 0.5)) for plan in candidate_plans]
    formulary_scores = [float(plan.get("formulary_score", 0.5)) for plan in candidate_plans]
    mental_health_scores = [float(plan.get("mental_health_access_score", 0.5)) for plan in candidate_plans]
    access_scores = [float(plan.get("hospital_access_score", 0.5)) for plan in candidate_plans]
    admin_scores = [float(plan.get("administrative_simplicity_score", 0.5)) for plan in candidate_plans]

    weights = profile["preference_weight_seed"]
    public_transport_dependency = profile["client_profile"]["geography"].get("public_transport_dependency", False)

    scored: list[ScoredPlan] = []
    for plan in candidate_plans:
        premium_score = _normalize_inverse(float(plan["premium"]), min(premiums), max(premiums))
        expected_cost_score = _normalize_inverse(float(plan["expected_yearly_cost"]), min(yearly_costs), max(yearly_costs))
        moop_score = _normalize_inverse(float(plan["moop"]), min(moops), max(moops))
        network_score = _normalize(float(plan.get("network_score", 0.5)), min(network_scores), max(network_scores))
        formulary_score = _normalize(float(plan.get("formulary_score", 0.5)), min(formulary_scores), max(formulary_scores))
        mental_health_score = _normalize(float(plan.get("mental_health_access_score", 0.5)), min(mental_health_scores), max(mental_health_scores))
        access_score = _normalize(float(plan.get("hospital_access_score", 0.5)), min(access_scores), max(access_scores))
        admin_score = _normalize(float(plan.get("administrative_simplicity_score", 0.5)), min(admin_scores), max(admin_scores))
        ongoing_fit = 1 - _normalize(float(plan["deductible"]), min(deductibles), max(deductibles)) * 0.5

        provider_component = (network_score + access_score) / 2 if public_transport_dependency else network_score
        composite = (
            weights["affordability_weight"] * premium_score
            + weights["expected_total_cost_weight"] * expected_cost_score
            + weights["catastrophic_protection_weight"] * moop_score
            + weights["provider_network_weight"] * provider_component
            + weights["formulary_drug_fit_weight"] * formulary_score
            + weights["mental_health_access_weight"] * mental_health_score
            + weights["flexibility_weight"] * (1.0 if plan.get("network_type") == "PPO" else 0.7 if plan.get("network_type") == "EPO" else 0.55)
            + weights["administrative_simplicity_weight"] * admin_score
            + weights["preventive_ongoing_care_fit_weight"] * ongoing_fit
        )

        scored.append(
            ScoredPlan(
                rank=0,
                plan_id=plan["plan_id"],
                plan_name=plan["plan_name"],
                issuer_name=plan["issuer_name"],
                state=plan["state"],
                county=plan["county"],
                premium=float(plan["premium"]),
                deductible=float(plan["deductible"]),
                moop=float(plan["moop"]),
                expected_yearly_cost=float(plan["expected_yearly_cost"]),
                composite_score=round(composite, 4),
                network_type=plan["network_type"],
                evidence={
                    "import_date": plan.get("import_date"),
                    "network_score": plan.get("network_score"),
                    "formulary_score": plan.get("formulary_score"),
                    "hospital_access_score": plan.get("hospital_access_score"),
                },
            )
        )

    scored.sort(key=lambda item: item.composite_score, reverse=True)
    for rank, plan in enumerate(scored, start=1):
        plan.rank = rank

    stability = {"status": "not_tested"}
    if len(scored) >= 2:
        top = scored[0].composite_score
        second = scored[1].composite_score
        pct_gap = 0.0 if top == 0 else round(((top - second) / top) * 100, 2)
        stability = {"status": "stable" if pct_gap >= 10 else "unstable", "top_two_gap_percent": pct_gap}

    return ScoringResult(
        status="ok",
        ranking_basis="composite_score",
        plans_considered=[plan["plan_name"] for plan in candidate_plans],
        scored_plans=scored,
        gaps=[],
        stability=stability,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Score normalized health insurance plans")
    parser.add_argument("--user", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--plans", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    user_answers = load_json(args.user)
    profile = load_json(args.profile)
    plans = load_json(args.plans)
    result = score_plans(user_answers, profile, plans)
    save_json(args.out, result.to_dict())
    print(args.out)


if __name__ == "__main__":
    main()
