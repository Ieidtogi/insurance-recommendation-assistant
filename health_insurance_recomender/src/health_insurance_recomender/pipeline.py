from __future__ import annotations

import argparse
import json
from pathlib import Path

from .guardrails import create_decision_record, render_recommendation
from .profiling import build_profile, load_json as load_user_json, save_json as save_profile_json
from .scoring import load_json as load_any_json, save_json as save_scoring_json, score_plans


def main() -> None:
    parser = argparse.ArgumentParser(description="Run end-to-end health insurance recommender workflow")
    parser.add_argument("--user", required=True)
    parser.add_argument("--plans", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    user_answers = load_user_json(args.user)
    plans = load_any_json(args.plans)

    profile = build_profile(user_answers)
    profile_path = out_dir / "profile.json"
    save_profile_json(profile_path, profile.to_dict())

    scoring = score_plans(user_answers, profile.to_dict(), plans)
    scoring_path = out_dir / "scoring.json"
    save_scoring_json(scoring_path, scoring.to_dict())

    record = create_decision_record(user_answers, profile.to_dict(), plans, scoring.to_dict(), args.user, args.plans, str(scoring_path))
    with (out_dir / "decision_record.json").open("w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2)
    with (out_dir / "rendered_recommendation.txt").open("w", encoding="utf-8") as handle:
        handle.write(render_recommendation(record))

    print(out_dir)


if __name__ == "__main__":
    main()
