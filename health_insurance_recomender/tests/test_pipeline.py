from pathlib import Path

from health_insurance_recomender.guardrails import create_decision_record
from health_insurance_recomender.profiling import build_profile, load_json
from health_insurance_recomender.scoring import score_plans


ROOT = Path(__file__).resolve().parents[1]


def test_complete_profile_scores_and_recommends():
    user = load_json(ROOT / "examples" / "user_answers_complete.json")
    plans = load_json(ROOT / "data" / "sample_plan_catalog.json")
    profile = build_profile(user).to_dict()
    scoring = score_plans(user, profile, plans).to_dict()

    assert profile["profile_confidence"] in {"high", "medium"}
    assert scoring["status"] == "ok"
    assert len(scoring["scored_plans"]) >= 2

    record = create_decision_record(user, profile, plans, scoring, "user.json", "plans.json", "scoring.json")
    assert record["status"] == "recommendation"
    assert record["recommendations"][0]["plan"] == scoring["scored_plans"][0]["plan_name"]


def test_missing_income_blocks_final_recommendation():
    user = load_json(ROOT / "examples" / "user_answers_missing.json")
    plans = load_json(ROOT / "data" / "sample_plan_catalog.json")
    profile = build_profile(user).to_dict()
    scoring = score_plans(user, profile, plans).to_dict()
    record = create_decision_record(user, profile, plans, scoring, "user.json", "plans.json", "scoring.json")

    assert record["status"] == "insufficient_data"
    assert any(gap["fact"] == "income" for gap in record["gaps"])
