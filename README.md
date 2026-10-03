# insurance-recommendation-assistant

An evidence-grounded health insurance advisor. It collects a user's answers, compares plans from a plan catalog, and gives a short recommendation that uses only the data it was given.

## TO RUN

Add the `health_insurance_recomender/README.md` as a skill for your agent of choice (in our case we used GPT 5.4), run the skill, and complete the questionnaire.

## What's in this repo

| Path | What it is |
| --- | --- |
| `RecommendationGuardrailsSkill.md` | Skill that gates every recommendation: it must be grounded only in collected data, kept short, and stated with a rule-based confidence level. |
| `health_insurance_recomender/` | Runnable Python pipeline (profile, score, guardrails). See its [README](health_insurance_recomender/README.md) for the full details. |
| `health_insurance_recomender.zip` | Zipped copy of the `health_insurance_recomender/` project. |

## Run the Python pipeline locally

The pipeline uses only the Python standard library, so there is nothing to install. From the repo root:

```powershell
cd health_insurance_recomender
$env:PYTHONPATH = "src"
python -m health_insurance_recomender.pipeline `
  --user examples/user_answers_complete.json `
  --plans data/sample_plan_catalog.json `
  --out examples/output_complete
```

On macOS or Linux:

```bash
cd health_insurance_recomender
PYTHONPATH=src python3 -m health_insurance_recomender.pipeline \
  --user examples/user_answers_complete.json \
  --plans data/sample_plan_catalog.json \
  --out examples/output_complete
```

The output folder gets `profile.json`, `scoring.json`, `decision_record.json` and `rendered_recommendation.txt`. The last one is the final recommendation.

## Notes

- This is decision support, not licensed insurance advice.
- The sample plan catalog is made-up data. Replace it with real normalized plan data for real use.
