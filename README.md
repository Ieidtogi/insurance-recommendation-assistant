# insurance-recommendation-assistant

A skill that turns an agentic LLM chatbot into a health insurance advisor. You call the skill in chat, the chatbot interviews you about your situation, and once it knows enough it recommends a plan, using only the data it collected from you and the plan catalog.

## TO RUN

Add `health_insurance_recomender/README.md` as a skill for your agent of choice (in our case we used GPT 5.4), run the skill, and complete the questionnaire.

## How it works

The repo has two parts:

- **The skill:** [`health_insurance_recomender/README.md`](health_insurance_recomender/README.md). This is what you load into the chatbot. It tells the agent the workflow and how to call the tools.
- **The tools:** the Python modules in [`health_insurance_recomender/src/health_insurance_recomender/`](health_insurance_recomender/src/health_insurance_recomender/). The agent runs them to turn your answers into a scored, grounded recommendation.

A session goes like this:

1. You call the skill explicitly in the chat.
2. The agent asks you questions about where you live, your household, your income, your health and your preferences.
3. The agent writes your answers to an intake JSON file, in the same shape as [`examples/user_answers_complete.json`](health_insurance_recomender/examples/user_answers_complete.json).
4. The agent runs the pipeline tool on that file and the plan catalog.
5. The agent gives you the recommendation from `rendered_recommendation.txt`. If something essential is missing, the pipeline refuses to recommend and the agent asks follow-up questions, then runs it again.

## Quick start

1. **Add the skill.** Add `health_insurance_recomender/README.md` as a skill in your agentic chatbot (Claude, ApexClaw, GPT 5.4, or similar). Give the agent the whole `health_insurance_recomender/` folder so it can reach the tools and the plan data.
2. **Make sure the agent can run code.** It needs Python 3 and permission to read and write files. The tools use only the Python standard library, so there is nothing to install.
3. **Call the skill in chat.** For example: *"Use the health insurance recommender skill to help me pick a plan."*
4. **Answer the questions** until the agent gives you a recommendation.

## What the agent asks about

The questions map to the fields that [`profiling.py`](health_insurance_recomender/src/health_insurance_recomender/profiling.py) reads.

| Importance | Fields |
| --- | --- |
| **Required.** No recommendation without these. | age, state, county or ZIP code, household size, income |
| **Strongly recommended.** Confidence drops without them. | monthly premium budget, expected care usage (only needed if you report no chronic conditions or medications) |
| **Shapes the ranking** | chronic conditions; primary care, specialist and therapy visits per year; current medications; preferred doctors and hospitals, and whether you must keep them; reliance on public transport; whether you care more about a low premium or a low total yearly cost; maximum out-of-pocket budget |
| **Recorded in the profile** | employment, occupation, shift work, travel, tobacco use, pregnancy or family planning, telehealth preference, employer or COBRA offers, Medicare or Medicaid eligibility, top priorities |

Plans are matched on **state and county**, so the agent needs your county even if you give a ZIP code.

## The tools

All tools run from inside `health_insurance_recomender/` with `src` on the Python path.

| Module | What it does |
| --- | --- |
| [`pipeline.py`](health_insurance_recomender/src/health_insurance_recomender/pipeline.py) | Runs the three stages below in order. This is the one the agent normally calls. |
| [`profiling.py`](health_insurance_recomender/src/health_insurance_recomender/profiling.py) | Turns raw answers into a structured profile. It derives features such as care intensity, medication dependency and financial fragility, lists missing critical information, and sets the scoring weights. |
| [`scoring.py`](health_insurance_recomender/src/health_insurance_recomender/scoring.py) | Keeps only plans in the user's state and county. It estimates each plan's yearly cost from premium, deductible, copays and care intensity, computes a weighted composite score, ranks the plans, and checks whether the top two are far enough apart (a gap of 10% or more counts as stable). |
| [`guardrails.py`](health_insurance_recomender/src/health_insurance_recomender/guardrails.py) | Blocks the recommendation if age, location, household size or income is missing. It builds a decision record in which every claim cites the source file it came from, assigns a confidence level, and renders the short answer. |
| [`models.py`](health_insurance_recomender/src/health_insurance_recomender/models.py) | Data classes for the profile and scoring results. |

**Run the full pipeline (PowerShell):**

```powershell
cd health_insurance_recomender
$env:PYTHONPATH = "src"
python -m health_insurance_recomender.pipeline `
  --user examples/user_answers_complete.json `
  --plans data/sample_plan_catalog.json `
  --out output
```

**macOS or Linux:**

```bash
cd health_insurance_recomender
PYTHONPATH=src python3 -m health_insurance_recomender.pipeline \
  --user examples/user_answers_complete.json \
  --plans data/sample_plan_catalog.json \
  --out output
```

The output folder gets four files:

| File | Contents |
| --- | --- |
| `profile.json` | The structured profile and scoring weights. |
| `scoring.json` | Every matched plan, ranked, with its estimated yearly cost. |
| `decision_record.json` | The recommendation, the evidence behind it, gaps, uncertainty and confidence. |
| `rendered_recommendation.txt` | The short answer the agent shows you. |

Each stage can also run on its own (`profiling`, `scoring`, `guardrails`). The skill README has the commands.

## Confidence levels

`guardrails.py` sets confidence by fixed rules, not by the model's judgment:

- **Low** if any of these is true:
  - the top plan is missing its premium, deductible or out-of-pocket maximum
  - three or more assumptions were made
  - the top two plans are within 2% of each other
  - the plan data is more than 60 days old
- **High** only if all of these are true:
  - there are no gaps or assumptions
  - the top two plans are at least 10% apart and the ranking is stable
  - the plan data is no more than 30 days old
- **Medium** otherwise.

## Example

With [`examples/user_answers_complete.json`](health_insurance_recomender/examples/user_answers_complete.json), a 34-year-old self-employed person in Hennepin County, MN, with asthma and anxiety, the pipeline produces:

```text
Recommend Transit Silver Value because it had the strongest overall score for this user's cost, access, and fit profile.
Confidence: MEDIUM.
1. Transit Silver Value — Best overall fit
- Composite score is 0.815, the highest among matched plans.
- Expected yearly cost is $6,215.
- Premium is $395 per month with a $7,200 MOOP.
- Tradeoff: Deductible is $3,100.
- Tradeoff: Network type is EPO.
What I'm not sure about:
- ranking stability: Runner-up North Metro Silver Access scored 0.792 versus 0.815 for the top plan.
```

With [`examples/user_answers_missing.json`](health_insurance_recomender/examples/user_answers_missing.json), which has no county or income, the guardrails block the recommendation:

```text
Need location, income before making a health-plan recommendation.
```

## Plan data

[`data/sample_plan_catalog.json`](health_insurance_recomender/data/sample_plan_catalog.json) is **made-up sample data**. It has three plans in Hennepin County, MN and one in Travis County, TX. Users anywhere else will get no matching plans until you add real plans in the same format.

Each plan has these fields:
- **Identity:** `plan_id`, `plan_name`, `issuer_name`
- **Location:** `state`, `county`
- **Costs:** `premium` (monthly), `deductible`, `moop` (maximum out-of-pocket), `pcp_copay`, `specialist_copay`, `generic_rx_copay`
- **Network type:** `network_type` (PPO, EPO or HMO)
- **Quality scores, each from 0 to 1:** `network_score`, `formulary_score`, `hospital_access_score`, `mental_health_access_score`, `administrative_simplicity_score`
- **Freshness:** `import_date` (YYYY-MM-DD; this drives the data-freshness confidence rules)

The skill README lists public sources, such as the CMS Exchange public use files, for building a real catalog.

## Repo layout

```text
health_insurance_recomender/
├── README.md                     # the skill
├── src/health_insurance_recomender/
│   ├── pipeline.py               # end-to-end tool
│   ├── profiling.py              # stage 1: intake -> profile
│   ├── scoring.py                # stage 2: rank matching plans
│   ├── guardrails.py             # stage 3: gate, cite, render
│   └── models.py
├── data/sample_plan_catalog.json # sample plan data
├── examples/                     # sample intake files and outputs
└── tests/test_pipeline.py
```

## Tests

```powershell
cd health_insurance_recomender
pip install pytest
$env:PYTHONPATH = "src"
pytest -q
```

The tests cover two cases: a complete intake produces a recommendation, and missing income blocks it.

## Disclaimer

This is decision support, not licensed insurance advice. Check any plan against the official marketplace or the insurer before enrolling.
