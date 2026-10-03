# Health Insurance Recomender

This project is a runnable starter workflow for an evidence-grounded health insurance advisor.

It implements the four stages described in the combined health-insurance-advisor workflow:

1. intake and profile building
2. dataset-grounded plan lookup and normalization
3. ranking / scoring
4. final recommendation guardrails

The implementation here is intentionally lightweight and deterministic so you can run it locally, inspect every intermediate file, and extend it later with richer CMS/SBE/SERFF/provider-directory ingestion.

## Project layout

- `src/health_insurance_recomender/models.py` - core schemas
- `src/health_insurance_recomender/profiling.py` - intake transformation and derived features
- `src/health_insurance_recomender/scoring.py` - plan filtering and transparent scoring
- `src/health_insurance_recomender/guardrails.py` - decision-record generation and final rendered output
- `src/health_insurance_recomender/pipeline.py` - end-to-end orchestrator
- `data/sample_plan_catalog.json` - sample normalized plan data
- `examples/user_answers_complete.json` - complete intake example
- `examples/user_answers_missing.json` - insufficient-data example
- `tests/test_pipeline.py` - regression tests

## What this code does

### 1. Intake / feature engineering

The profile builder converts raw user answers into:

- normalized client profile sections
- derived risk / need features
- explicit missing critical information
- assumptions used
- preference-weight seed for downstream scoring

### 2. Dataset-grounded plan analysis

The scoring layer reads structured plan facts from a plan catalog and compares only plans that match the user geography.

Current sample fields include:

- premium
- deductible
- MOOP
- PCP / specialist / generic drug copays
- network type and network score
- formulary score
- hospital access score
- mental health access score
- administrative simplicity score
- import date

### 3. Ranking / scoring

The scorer computes:

- expected yearly cost estimate
- weighted composite score using the profile weight seed
- ranked shortlist
- gap reporting for unscorable plans

### 4. Recommendation guardrails

The guardrail layer:

- blocks final recommendation if age, location, household size, or income are missing
- generates a decision record grounded only in input files
- assigns rule-based confidence
- renders a short final recommendation

## Run the full workflow

From this project folder:

```bash
PYTHONPATH=src python3 -m health_insurance_recomender.pipeline \
  --user examples/user_answers_complete.json \
  --plans data/sample_plan_catalog.json \
  --out examples/output_complete
```

This writes:

- `examples/output_complete/profile.json`
- `examples/output_complete/scoring.json`
- `examples/output_complete/decision_record.json`
- `examples/output_complete/rendered_recommendation.txt`

## Run each stage separately

### Step 1: build profile

```bash
PYTHONPATH=src python3 -m health_insurance_recomender.profiling \
  --user examples/user_answers_complete.json \
  --out examples/output_complete/profile.json
```

### Step 2: score plans

```bash
PYTHONPATH=src python3 -m health_insurance_recomender.scoring \
  --user examples/user_answers_complete.json \
  --profile examples/output_complete/profile.json \
  --plans data/sample_plan_catalog.json \
  --out examples/output_complete/scoring.json
```

### Step 3: apply guardrails and render final answer

```bash
PYTHONPATH=src python3 -m health_insurance_recomender.guardrails \
  --user examples/user_answers_complete.json \
  --profile examples/output_complete/profile.json \
  --plans data/sample_plan_catalog.json \
  --scoring examples/output_complete/scoring.json \
  --out-dir examples/output_complete
```

## Test

```bash
PYTHONPATH=src pytest -q
```

## Extend this project

To make this production-grade, replace `data/sample_plan_catalog.json` with normalized outputs from real sources such as:

- CMS Exchange PUFs
- CMS State-based Exchange PUFs
- QHP Landscape files
- Service Area PUF
- Network PUF
- Machine-readable URL PUF
- Medicare Advantage / Part D public files
- Medicaid / CHIP / BHP threshold datasets
- TRICARE compare-plans data
- VA income-limit sources
- SERFF filings for ambiguous benefit/exclusion checks

## Notes

- This starter implementation is for decision support, not licensed insurance advice.
- It is deterministic and auditable by design.
- It is meant to plug into a richer UI that asks adaptive questions and stores the resulting intake JSON.
