from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .models import ProfileResult


CRITICAL_FIELDS = ["state", "county", "zip_code", "age", "household_size", "income"]


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: str | Path, payload: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def _band(value: float | int | None, low_cut: float, high_cut: float) -> str:
    if value is None:
        return "moderate"
    if value <= low_cut:
        return "low"
    if value >= high_cut:
        return "high"
    return "moderate"


def _normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    total = sum(weights.values()) or 1.0
    return {key: round(value / total, 4) for key, value in weights.items()}


def build_profile(user_answers: dict[str, Any]) -> ProfileResult:
    demographics = {
        "age": user_answers.get("age"),
        "sex_assigned_at_birth": user_answers.get("sex_assigned_at_birth"),
    }
    household = {
        "household_size": user_answers.get("household_size"),
        "spouse_partner_status": user_answers.get("spouse_partner_status"),
        "dependents": user_answers.get("dependents", []),
    }
    geography = {
        "state": user_answers.get("state"),
        "county": user_answers.get("county"),
        "zip_code": user_answers.get("zip_code"),
        "market": user_answers.get("market", "ACA_INDIVIDUAL"),
        "public_transport_dependency": user_answers.get("public_transport_dependency", False),
        "travel_limit_miles": user_answers.get("travel_limit_miles"),
    }
    financial_constraints = {
        "income": user_answers.get("income"),
        "monthly_premium_budget": user_answers.get("monthly_premium_budget"),
        "deductible_preference": user_answers.get("deductible_preference", "balanced"),
        "copay_predictability_preference": user_answers.get("copay_predictability_preference", "balanced"),
    }
    employment_and_occupation = {
        "employment_status": user_answers.get("employment_status"),
        "occupation": user_answers.get("occupation"),
        "shift_work": user_answers.get("shift_work", False),
        "travel_frequency": user_answers.get("travel_frequency", "low"),
    }
    health_status = {
        "chronic_conditions": user_answers.get("chronic_conditions", []),
        "planned_care_next_12_months": user_answers.get("planned_care_next_12_months", []),
        "pregnancy_family_planning": user_answers.get("pregnancy_family_planning", False),
    }
    care_utilization = {
        "expected_care_usage": user_answers.get("expected_care_usage"),
        "primary_care_visits_per_year": user_answers.get("primary_care_visits_per_year"),
        "specialist_visits_per_year": user_answers.get("specialist_visits_per_year"),
        "therapy_visits_per_year": user_answers.get("therapy_visits_per_year"),
    }
    medications = {
        "current_medications": user_answers.get("current_medications", []),
        "preferred_pharmacy": user_answers.get("preferred_pharmacy"),
        "specialty_drug_dependency": user_answers.get("specialty_drug_dependency", False),
    }
    mental_behavioral_health = {
        "therapy_priority": user_answers.get("therapy_priority", False),
        "psychiatry_priority": user_answers.get("psychiatry_priority", False),
        "telehealth_preference": user_answers.get("telehealth_preference", False),
    }
    lifestyle = {
        "tobacco_use": user_answers.get("tobacco_use", False),
    }
    provider_preferences = {
        "preferred_doctors": user_answers.get("preferred_doctors", []),
        "preferred_hospitals": user_answers.get("preferred_hospitals", []),
        "must_keep_providers": user_answers.get("must_keep_providers", False),
    }
    insurance_preferences = {
        "network_preference": user_answers.get("network_preference", "broad"),
        "low_premium_priority": user_answers.get("low_premium_priority", False),
        "low_total_cost_priority": user_answers.get("low_total_cost_priority", True),
        "unacceptable_tradeoffs": user_answers.get("unacceptable_tradeoffs", []),
    }
    eligibility_context = {
        "employer_offer": user_answers.get("employer_offer"),
        "cobra_available": user_answers.get("cobra_available"),
        "medicare_eligible": user_answers.get("medicare_eligible", False),
        "medicaid_possible": user_answers.get("medicaid_possible", False),
    }

    client_profile = {
        "demographics": demographics,
        "household": household,
        "geography": geography,
        "financial_constraints": financial_constraints,
        "employment_and_occupation": employment_and_occupation,
        "health_status": health_status,
        "care_utilization": care_utilization,
        "medications": medications,
        "mental_behavioral_health": mental_behavioral_health,
        "lifestyle": lifestyle,
        "provider_preferences": provider_preferences,
        "insurance_preferences": insurance_preferences,
        "eligibility_context": eligibility_context,
    }

    chronic_count = len(health_status["chronic_conditions"])
    medication_count = len(medications["current_medications"])
    specialist_visits = care_utilization["specialist_visits_per_year"] or 0
    therapy_visits = care_utilization["therapy_visits_per_year"] or 0
    expected_usage = care_utilization["expected_care_usage"]
    if expected_usage in {"low", "moderate", "high"}:
        care_intensity = expected_usage
    else:
        raw_load = chronic_count + medication_count + (specialist_visits >= 4) + (therapy_visits >= 6)
        care_intensity = "low" if raw_load == 0 else "moderate" if raw_load <= 2 else "high"

    derived_features = {
        "estimated_care_intensity": care_intensity,
        "medication_dependency": _band(medication_count + int(medications["specialty_drug_dependency"]), 0, 3),
        "network_dependency": "high" if provider_preferences["must_keep_providers"] else _band(len(provider_preferences["preferred_doctors"]) + len(provider_preferences["preferred_hospitals"]), 0, 2),
        "mental_health_service_dependency": _band(therapy_visits + int(mental_behavioral_health["psychiatry_priority"]), 0, 10),
        "financial_fragility": "high" if (financial_constraints["monthly_premium_budget"] or 10_000) < 350 else "moderate" if (financial_constraints["monthly_premium_budget"] or 10_000) < 550 else "low",
        "catastrophic_cost_sensitivity": "high" if user_answers.get("max_annual_out_of_pocket_budget", 20_000) < 5_000 else "moderate",
        "preference_for_low_fixed_cost": "high" if insurance_preferences["low_premium_priority"] else "moderate",
        "preference_for_cost_predictability": "high" if financial_constraints["copay_predictability_preference"] == "high" else "moderate",
        "occupational_health_stress": "high" if employment_and_occupation["shift_work"] else "moderate",
        "environmental_access_risk": "high" if geography["public_transport_dependency"] else "moderate",
        "family_coverage_complexity": "high" if (household["household_size"] or 1) >= 4 else "moderate" if (household["household_size"] or 1) > 1 else "low",
    }

    weights = {
        "affordability_weight": 1.0,
        "expected_total_cost_weight": 1.0,
        "catastrophic_protection_weight": 1.0,
        "provider_network_weight": 1.0,
        "formulary_drug_fit_weight": 1.0,
        "mental_health_access_weight": 0.6,
        "flexibility_weight": 0.6,
        "administrative_simplicity_weight": 0.5,
        "preventive_ongoing_care_fit_weight": 0.8,
    }
    if derived_features["financial_fragility"] == "high":
        weights["affordability_weight"] += 0.9
        weights["catastrophic_protection_weight"] += 0.7
    if derived_features["medication_dependency"] in {"moderate", "high"}:
        weights["formulary_drug_fit_weight"] += 1.0
        weights["expected_total_cost_weight"] += 0.6
    if derived_features["network_dependency"] in {"moderate", "high"}:
        weights["provider_network_weight"] += 1.0
    if derived_features["mental_health_service_dependency"] in {"moderate", "high"}:
        weights["mental_health_access_weight"] += 0.9
    if geography["public_transport_dependency"]:
        weights["provider_network_weight"] += 0.4
        weights["flexibility_weight"] += 0.3
    if insurance_preferences["low_premium_priority"]:
        weights["affordability_weight"] += 0.7
    if insurance_preferences["low_total_cost_priority"]:
        weights["expected_total_cost_weight"] += 0.7

    missing_critical_info: list[str] = []
    if not geography["state"]:
        missing_critical_info.append("state")
    if not geography["county"] and not geography["zip_code"]:
        missing_critical_info.append("county_or_zip")
    if demographics["age"] is None:
        missing_critical_info.append("age")
    if household["household_size"] is None:
        missing_critical_info.append("household_size")
    if financial_constraints["income"] is None:
        missing_critical_info.append("income")
    if financial_constraints["monthly_premium_budget"] is None:
        missing_critical_info.append("monthly_premium_budget")
    if care_utilization["expected_care_usage"] is None and chronic_count == 0 and medication_count == 0:
        missing_critical_info.append("expected_care_usage")

    known_constraints = []
    if geography["public_transport_dependency"]:
        known_constraints.append("must consider care access without relying on a car")
    if provider_preferences["must_keep_providers"]:
        known_constraints.append("provider continuity is required")
    if medications["current_medications"]:
        known_constraints.append("medications need formulary review")

    followup_questions_still_recommended = []
    if "county_or_zip" in missing_critical_info:
        followup_questions_still_recommended.append("What county or ZIP code should plans be matched to?")
    if "monthly_premium_budget" in missing_critical_info:
        followup_questions_still_recommended.append("What monthly premium range feels affordable?")
    if provider_preferences["preferred_doctors"] and not provider_preferences["must_keep_providers"]:
        followup_questions_still_recommended.append("Are your preferred doctors essential to keep, or just preferred?")

    uncertainty_notes = []
    if "income" in missing_critical_info:
        uncertainty_notes.append("Affordability and subsidy-sensitive ranking may change materially once income is known.")
    if "county_or_zip" in missing_critical_info:
        uncertainty_notes.append("Plan availability cannot be stabilized until county or ZIP is known.")

    confidence = "high"
    if missing_critical_info:
        confidence = "low" if len(missing_critical_info) >= 3 else "medium"

    return ProfileResult(
        client_profile=client_profile,
        derived_features=derived_features,
        stated_priorities=user_answers.get("top_priorities", []),
        known_constraints=known_constraints,
        missing_critical_info=missing_critical_info,
        assumptions_used=[],
        followup_questions_asked=user_answers.get("followup_questions_asked", []),
        followup_questions_still_recommended=followup_questions_still_recommended,
        preference_weight_seed=_normalize_weights(weights),
        profile_confidence=confidence,
        uncertainty_notes=uncertainty_notes,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build normalized health insurance intake profile")
    parser.add_argument("--user", required=True, help="Path to raw user answers JSON")
    parser.add_argument("--out", required=True, help="Path to output profile JSON")
    args = parser.parse_args()

    user_answers = load_json(args.user)
    result = build_profile(user_answers)
    save_json(args.out, result.to_dict())
    print(args.out)


if __name__ == "__main__":
    main()
