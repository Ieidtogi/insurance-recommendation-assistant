from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any


def load_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: str | Path, payload: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def save_text(path: str | Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(text)


def _days_old(import_date: str | None) -> int | None:
    if not import_date:
        return None
    return (date.today() - date.fromisoformat(import_date)).days


def _confidence(scoring: dict[str, Any], top_plan: dict[str, Any], assumptions: list[str], gaps: list[dict[str, Any]]) -> str:
    top_date_age = _days_old(top_plan["evidence"].get("import_date"))
    gap_pct = scoring.get("stability", {}).get("top_two_gap_percent")
    if top_plan.get("premium") is None or top_plan.get("deductible") is None or top_plan.get("moop") is None:
        return "low"
    if len(assumptions) >= 3:
        return "low"
    if gap_pct is not None and gap_pct <= 2:
        return "low"
    if top_date_age is not None and top_date_age > 60:
        return "low"
    if not gaps and not assumptions and gap_pct is not None and gap_pct >= 10 and top_date_age is not None and top_date_age <= 30 and scoring.get("stability", {}).get("status") == "stable":
        return "high"
    return "medium"


def create_decision_record(user_answers: dict[str, Any], profile: dict[str, Any], plans: list[dict[str, Any]], scoring: dict[str, Any], user_path: str, plans_path: str, scoring_path: str) -> dict[str, Any]:
    essentials_missing = []
    if user_answers.get("age") is None:
        essentials_missing.append("age")
    if not (user_answers.get("county") or user_answers.get("zip_code")):
        essentials_missing.append("location")
    if user_answers.get("household_size") is None:
        essentials_missing.append("household_size")
    if user_answers.get("income") is None:
        essentials_missing.append("income")

    if essentials_missing:
        return {
            "status": "insufficient_data",
            "summary": f"Need {', '.join(essentials_missing)} before making a health-plan recommendation.",
            "sources": {
                "S1": {"path": user_path, "kind": "user_answers"},
            },
            "evidence": {},
            "ranking": {"direction": "higher_is_better", "considered": []},
            "recommendations": [],
            "stability": {"status": "not_tested", "evidence": []},
            "assumptions": [],
            "gaps": [{"about": "user", "fact": item, "why": "missing from intake answers"} for item in essentials_missing],
            "uncertainty": [
                {
                    "topic": item,
                    "unknown": f"{item} was not provided.",
                    "impact": "Final plan matching and ranking could change materially.",
                    "resolve": f"Ask the user for {item}.",
                }
                for item in essentials_missing
            ],
            "confidence": {"level": "low"},
        }

    top_plan = scoring["scored_plans"][0]
    runner_up = scoring["scored_plans"][1] if len(scoring["scored_plans"]) > 1 else None
    plan_lookup = {plan["plan_id"]: plan for plan in plans}
    top_plan_source = plan_lookup[top_plan["plan_id"]]
    assumptions = profile.get("assumptions_used", [])
    gaps = scoring.get("gaps", [])
    confidence = _confidence(scoring, top_plan, assumptions, gaps)

    record = {
        "status": "recommendation",
        "summary": f"Recommend {top_plan['plan_name']} because it had the strongest overall score for this user's cost, access, and fit profile.",
        "sources": {
            "S1": {"path": user_path, "kind": "user_answers"},
            "S2": {"path": plans_path, "kind": "plan_data"},
            "S3": {"path": scoring_path, "kind": "scoring_output"},
        },
        "evidence": {
            "u1": {"type": "source", "source": "S1", "about": "user", "fact": "age", "value": user_answers["age"], "quote": json.dumps({"age": user_answers["age"]})},
            "u2": {"type": "source", "source": "S1", "about": "user", "fact": "income", "value": user_answers["income"], "quote": json.dumps({"income": user_answers["income"]})},
            "p1": {"type": "source", "source": "S2", "about": top_plan["plan_name"], "fact": "premium", "value": top_plan["premium"], "json_path": "[top_plan_by_id].premium"},
            "p2": {"type": "source", "source": "S2", "about": top_plan["plan_name"], "fact": "deductible", "value": top_plan["deductible"], "json_path": "[top_plan_by_id].deductible"},
            "p3": {"type": "source", "source": "S2", "about": top_plan["plan_name"], "fact": "moop", "value": top_plan["moop"], "json_path": "[top_plan_by_id].moop"},
            "s1": {"type": "source", "source": "S3", "about": top_plan["plan_name"], "fact": "composite_score", "value": top_plan["composite_score"], "json_path": "scored_plans[0].composite_score"},
            "s2": {"type": "source", "source": "S3", "about": top_plan["plan_name"], "fact": "expected_yearly_cost", "value": top_plan["expected_yearly_cost"], "json_path": "scored_plans[0].expected_yearly_cost"},
        },
        "ranking": {
            "direction": "higher_is_better",
            "considered": [
                {"plan": plan["plan_name"], "basis": f"rank={idx}"}
                for idx, plan in enumerate(scoring["scored_plans"], start=1)
            ],
        },
        "recommendations": [
            {
                "rank": 1,
                "plan": top_plan["plan_name"],
                "headline": "Best overall fit",
                "reasons": [
                    {"text": f"Composite score is {top_plan['composite_score']}, the highest among matched plans.", "label": "fact", "evidence": ["s1"]},
                    {"text": f"Expected yearly cost is ${top_plan['expected_yearly_cost']:,.0f}.", "label": "fact", "evidence": ["s2"]},
                    {"text": f"Premium is ${top_plan['premium']:,.0f} per month with a ${top_plan['moop']:,.0f} MOOP.", "label": "fact", "evidence": ["p1", "p3"]},
                ],
                "tradeoffs": [
                    {"text": f"Deductible is ${top_plan['deductible']:,.0f}.", "label": "fact", "evidence": ["p2"]},
                    {"text": f"Network type is {top_plan['network_type']}.", "label": "judgment", "evidence": ["s1"]},
                ],
            }
        ],
        "stability": {"status": scoring.get("stability", {}).get("status", "not_tested"), "evidence": ["s1"]},
        "assumptions": [{"fact": item, "assumed_value": None, "why": "carried from profile stage"} for item in assumptions],
        "gaps": gaps,
        "uncertainty": [],
        "confidence": {"level": confidence},
    }

    if runner_up:
        record["uncertainty"].append(
            {
                "topic": "ranking stability",
                "unknown": f"Runner-up {runner_up['plan_name']} scored {runner_up['composite_score']} versus {top_plan['composite_score']} for the top plan.",
                "impact": "A small gap means the recommendation could change if preferences or missing details change.",
                "resolve": "Clarify must-keep providers, exact medications, and budget tolerance.",
            }
        )
    if _days_old(top_plan_source.get("import_date")) is None:
        record["uncertainty"].append(
            {
                "topic": "data freshness",
                "unknown": "Import date was not recorded for the top plan.",
                "impact": "Plan attributes could be stale.",
                "resolve": "Refresh the plan dataset from the latest public source.",
            }
        )
    return record


def render_recommendation(record: dict[str, Any]) -> str:
    if record["status"] == "insufficient_data":
        return record["summary"]
    rec = record["recommendations"][0]
    lines = [record["summary"], f"Confidence: {record['confidence']['level'].upper()}.", f"1. {rec['plan']} — {rec['headline']}"]
    for reason in rec["reasons"]:
        lines.append(f"- {reason['text']}")
    for tradeoff in rec["tradeoffs"]:
        lines.append(f"- Tradeoff: {tradeoff['text']}")
    if record["uncertainty"]:
        lines.append("What I'm not sure about:")
        for item in record["uncertainty"][:4]:
            lines.append(f"- {item['topic']}: {item['unknown']}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply recommendation guardrails")
    parser.add_argument("--user", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--plans", required=True)
    parser.add_argument("--scoring", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    user_answers = load_json(args.user)
    profile = load_json(args.profile)
    plans = load_json(args.plans)
    scoring = load_json(args.scoring)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    record = create_decision_record(user_answers, profile, plans, scoring, args.user, args.plans, args.scoring)
    rendered = render_recommendation(record)
    save_json(out_dir / "decision_record.json", record)
    save_text(out_dir / "rendered_recommendation.txt", rendered)
    print(out_dir / "decision_record.json")


if __name__ == "__main__":
    main()
