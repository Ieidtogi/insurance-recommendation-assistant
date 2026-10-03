---
name: recommendation-guardrails
description: Final gate for every health-plan recommendation. Makes sure the answer is built only from the data the app actually collected (scraped plan data, the user's answers, any scoring output) with no outside knowledge, keeps the reasoning short, and states uncertainty with a rule-based confidence level. Works with whatever format that data is in. Use this skill whenever you are about to tell a user which health insurance plan fits them, rank or compare plans, explain why a plan was picked, or say how sure you are, even for a quick "which one should I get?".
---

# Recommendation guardrails

This skill is the last step before a plan recommendation reaches the user. It exists
because three failures make an insurance recommendation untrustworthy:

1. **Outside knowledge leaks in.** A model "knows" an insurer's reputation or a typical
   copay and blends it with the collected data. The user can't tell which numbers are real.
2. **The reasoning sprawls.** Long explanations bury the deciding factor and invite
   unsupported claims.
3. **Confidence is unearned.** The answer sounds equally sure whether the data was
   complete or half of it was guessed.

The fix is structural: you write a small decision record (JSON) in which every fact
points to the exact place it came from, a script looks each one up in the real file, and
only a record that passes is shown to the user.

## Workflow

1. **Look at the data as it actually is.** Nothing about file names, formats, columns or
   keys is fixed; the scraper, the question flow and the scoring step can produce
   anything. Find three kinds of input and open them before deciding anything:
   - **plan data**: whatever the scraper produced (tables, JSON, saved pages, notes)
   - **user answers**: whatever the question flow recorded
   - **scoring output**: a ranking or scores, if a scoring step exists

   If something you'll cite exists only in the conversation or a tool result, save it
   verbatim to a text file first so it can be checked. If a file is binary (PDF, Excel,
   Word), convert it to text once and cite the text copy.
2. **Register each file as a source** with its path and kind (`plan_data`,
   `user_answers`, `scoring_output` or `other`).
3. **Check the user's essentials:** age, location (ZIP or county), household size, and
   income. Premiums and subsidies depend on them. If any is missing from the user's
   answers, set `status` to `insufficient_data`, say what's needed, and stop. These four
   can never be assumed.
4. **Rank by data, never by impression.** If a scoring output exists, rank by its score
   (or cost) for each plan. If there is none, compute one comparable number per plan
   from the data, such as expected yearly cost, as `computed` evidence, and rank by that.
   List every plan you compared under `ranking.considered`. A plan you couldn't score
   goes under `gaps` with the reason, not silently left out.
5. **Write the decision record** (format below, full example in
   `examples/good_record.json`). Copy numbers from the files rather than re-deriving
   them; re-deriving is where long reasoning and arithmetic slips come from.
6. **Run the validator** from this skill's folder:
   ```bash
   python scripts/check_output.py <your_record.json> --render
   ```
   Relative source paths resolve against the record's folder and the current folder; add
   `--base <dir>` if the data lives elsewhere.
7. **Fix every error and re-run.** Each error names the item and the rule. Stop after 3
   attempts; if errors remain, delete the failing statements rather than keep them.
8. **Show the user exactly the text after `---RENDERED---`.** Don't add a preamble or a
   closing paragraph; anything you add bypasses the checks.

Warnings don't block, but read them: they flag hedge words and phrases that sound like
outside knowledge.

## Rule 1: Only the data

Every fact is an evidence item that points into a registered source. Pick the locator
that fits the file you're looking at:

| The file looks like | Locator | The validator checks |
|---|---|---|
| A table (CSV, TSV, any delimited text) | `column`: the header text exactly as written, plus `about`: the plan name that identifies the row | the cell in that row and column holds the value |
| JSON | `json_path`: e.g. `results[0].score` or `plans.northwoods.premium` | the value at that path; the surrounding record mentions `about` |
| Anything else (text, Markdown, HTML, notes) | `quote`: the shortest exact span (300 characters max) that contains the value | the quote is in the file, the value is in the quote, and the nearest plan name to the quote is `about` |

`about` is the plan's name exactly as the data writes it, or `user` for the user's
answers. The plan-name check catches the most common grounding error: a correct number
copied from the neighbouring plan's row or record.

Two more evidence types: `computed` (arithmetic over other evidence ids, e.g.
`"m3 - m1"`, which the validator re-runs) and `assumption` (a value you had to assume,
declared in `assumptions`).

Out of bounds, even if you're confident it's true: insurer reputation or service
quality, "typical" copays or premiums, plan facts not in the data, and general
statistics. If the data doesn't state something, it's a gap. List it under `gaps` and
explain it in uncertainty; never fill it in.

Every dollar amount and percentage in the text must match evidence that the statement
cites. Small bare counts ("3 visits") and digits inside plan names are exempt. Include a
URL only if it appears in a source file, and fill a source's `retrieved` date only if the
file itself records that date, copied as written.

## Rule 2: Short reasoning

| Element | Limit |
|---|---|
| Summary | 30 words |
| Plans shown | 3 |
| Headline per plan | 12 words |
| Reasons per plan | 3, each 25 words |
| Tradeoffs per plan | 2, each 25 words |
| Uncertainty items | 4, each part 25 words |
| Whole answer (excluding the evidence table) | 250 words |

Write the deciding factors, not the process. One fact per reason, with the comparison
that makes it matter.

- Good: "Expected yearly cost is $5,814, versus $6,006 for the next plan."
- Bad: "After carefully analyzing all of the plans available in your area and weighing
  your stated preferences, I found that this plan offers a good balance of value..."

Don't restate the user's answers back to them, don't define insurance terms here, and
don't repeat disclaimers; the renderer adds one line.

Label each reason or tradeoff:
- `fact`: cites source evidence only.
- `calculated`: cites a computed item.
- `assumption`: required whenever the statement leans on an assumed value, directly or
  through a formula.
- `judgment`: an interpretation; it still cites the evidence it interprets.

## Rule 3: Say what you don't know

The validator computes the confidence level from a fixed rubric and rejects the record
if your stated level differs. Work it out the same way:

| Level | When |
|---|---|
| **Low** | any of: the #1 plan's premium, deductible or out-of-pocket maximum is a gap; 3+ assumptions; top two plans within 2% on the ranking basis; plan data over 60 days old |
| **High** | all of: no gaps; no assumptions; top two plans at least 10% apart; ranking shown to be stable by cited evidence; plan data's own retrieval date within 30 days |
| **Medium** | everything else, including when the data doesn't record when it was collected |

For the #1 plan, cite its premium, deductible and out-of-pocket maximum, or declare each
missing one as a gap. Those three decide most of what a plan costs.

Every uncertainty item has a `topic` and three parts: what is unknown, why it matters for
this user's choice, and what would resolve it (a question to ask or a document to check).
Specific beats vague: "Prairie Silver Value lists no deductible, so it could not be
ranked" is useful; "some information may be incomplete" is not.

The validator requires an uncertainty item whose topic matches:
- each assumption (topic = the assumed fact)
- each gap (topic = the missing fact)
- an unstable ranking (topic = `ranking stability`)

Set `stability.status` to `stable` only when you can cite evidence, such as a
sensitivity result in the scoring output. Otherwise use `unstable` or `not_tested`.

Keep hedge words (may, might, likely, probably) inside the uncertainty section. In
reasons and tradeoffs, state facts plainly; doubt belongs where the user can see what
it's about.

## Decision record format

```json
{
  "status": "recommendation",
  "summary": "One sentence naming the pick and the deciding reason.",
  "sources": {
    "S1": {"path": "<whatever the scraper wrote>", "kind": "plan_data", "retrieved": "<only if the file says>"},
    "S2": {"path": "<whatever the questions step wrote>", "kind": "user_answers"},
    "S3": {"path": "<scoring output, if any>", "kind": "scoring_output"}
  },
  "evidence": {
    "u4": {"type": "source", "source": "S2", "about": "user", "fact": "income", "value": 41000, "quote": "A4. About $41,000"},
    "d2": {"type": "source", "source": "S1", "about": "Northwoods Silver 3000", "fact": "deductible", "value": 3000, "column": "Deductible"},
    "s1": {"type": "source", "source": "S3", "about": "Northwoods Silver 3000", "fact": "score", "value": 0.78, "json_path": "results[0].score"},
    "c1": {"type": "computed", "about": "Badger Gold 1000", "fact": "extra yearly cost vs #1", "formula": "m3 - m1", "value": 1212},
    "a1": {"type": "assumption", "fact": "specialist visits", "value": 6}
  },
  "ranking": {"direction": "higher_is_better", "considered": [{"plan": "Northwoods Silver 3000", "basis": "s1"}]},
  "recommendations": [
    {"rank": 1, "plan": "Northwoods Silver 3000", "headline": "...",
     "reasons": [{"text": "...", "label": "fact", "evidence": ["m1", "m2"]}],
     "tradeoffs": [{"text": "...", "label": "calculated", "evidence": ["c1"]}]}
  ],
  "stability": {"status": "stable", "evidence": ["st1"]},
  "assumptions": [{"fact": "specialist visits", "assumed_value": 6, "why": "you skipped this question"}],
  "gaps": [{"about": "Prairie Silver Value", "fact": "deductible", "why": "blank in the scraped table"}],
  "uncertainty": [{"topic": "specialist visits", "unknown": "...", "impact": "...", "resolve": "..."}],
  "confidence": {"level": "medium"}
}
```

The paths and plan names above come from the bundled example only. Use whatever your
data actually contains. For `insufficient_data`, leave `recommendations` empty and use
`summary` plus `uncertainty` to say what's needed (see
`examples/insufficient_record.json`).

## If the script can't run

Some setups load only this file. If `scripts/check_output.py` isn't available or Python
can't run, apply the same checks yourself before answering:
- Open each source and confirm every cited value sits at its locator and belongs to the
  plan named in `about`.
- Recompute every formula.
- Count words against Rule 2's limits.
- Work out the confidence level with Rule 3's rubric.

Then answer in this layout:
1. **Recommendation:** the summary.
2. **Confidence: LEVEL** (drivers).
3. For each plan:
   - a `### <rank>. <plan>` heading
   - the headline
   - the reasons, then the tradeoffs, as bullets that each end with their label in
     brackets
4. "What I'm not sure about".
5. "Assumptions used".
6. An evidence table: ID | Kind | About | Fact | Value | Where it comes from.
7. One closing line: "Decision support based only on the data above; not licensed
   insurance advice. Checked manually; the automatic validator did not run."

## What the validator can't see

It confirms each value is where you say it is, but not that a column means what your
`fact` label claims. Name facts honestly after the header or key they come from. It
also can't see plans you leave out of `ranking.considered`, so list every plan in the
data there, or in `gaps` if it couldn't be scored.

## Examples and tuning

`examples/` contains source files in four formats (a CSV table, a saved HTML page, a
plain-text Q&A log, a JSON ranker output) and three records citing them:
- `good_record.json` passes.
- `bad_record.json` fails with 27 errors covering every rule.
- `insufficient_record.json` correctly refuses to rank.

Limits, rubric thresholds, number tolerances, the phrase lists, and the words that
identify the essential facts (e.g. "income", "deductible", "out-of-pocket") live in
`scripts/guardrails_config.json`. Change them there so this file and the validator stay
in sync.
