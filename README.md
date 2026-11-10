# Quarterly performance pack agent

![tests](https://github.com/Tanmay-Kulk/quarterly-performance-pack-agent/actions/workflows/tests.yml/badge.svg)

A small, tested AI workflow: **public data → validation → calculations → AI-drafted commentary → automatic checks on the AI.**

It is a worked example built to show how I approach AI and automation work: pick the right size of solution, check the data before using it, check the AI's output before trusting it, and leave documentation and tests behind so someone else can support it.

Everything here uses **public market data** and an **invented pension plan**. It contains no employer or client data and is not investment advice.

> Read the section that matches your time: [In one minute](#in-one-minute-for-anyone) · [How it works](#how-it-works) · [Results](#results-of-the-pilot) · [Run it yourself](#run-it-yourself) · [For developers](#for-developers)

---

## In one minute (for anyone)

Each quarter, an analyst at an investment consulting firm typically gathers market numbers, checks them, works out how a client's investment plan did compared with its target mix, and writes a short summary for a committee.

This project automates that routine, and, more importantly, **checks its own work at both ends**:

1. **Bad data stops the run.** The program checks the numbers it downloads (gaps, duplicates, stale data, impossible values, wrong units) and refuses to continue if something is wrong.
2. **Every number the AI writes is checked.** An AI drafts the commentary, then ordinary code compares each figure in the text with the calculated table. A wrong or invented number fails the draft.

In a small test (ten AI drafts), a plain request produced drafts that all failed at least one check, and four of the five quoted a slightly wrong number. With clear rules in the request, four of the five drafts passed every check. The checker is useful, but it is not a judge of whether a sentence is fair, so a person still reads and approves the final text.

**What this shows about how I work:** build the smallest thing that does the job, test it by trying to break it, measure whether the AI part can be trusted, and write down how it runs.

---

## How it works

```
  FRED (public data)
        │  HTTPS, retries, local cache
        ▼
  ┌───────────┐   errors stop the run      ┌───────────┐
  │   FETCH   │ ─────────────────────────▶ │  VALIDATE │  7 checks per series
  └───────────┘                            └─────┬─────┘
                                                 │ clean data
                                                 ▼
                                          ┌─────────────┐
                                          │  TRANSFORM  │  quarterly returns, policy vs plan,
                                          └──────┬──────┘  allocation effect
                                                 │ validated table
                                                 ▼
                                          ┌─────────────┐
                              prompts ──▶ │    DRAFT    │  AI writes the commentary
                                          └──────┬──────┘  (from the table only)
                                                 ▼
                                          ┌─────────────┐
                                          │  EVALUATE   │  5 automatic checks per draft
                                          └──────┬──────┘
                                                 ▼
                                          ┌─────────────┐
                                          │    PACK     │  Excel file + run log
                                          └─────────────┘
```

| Stage | File | What it does |
|---|---|---|
| Fetch | `src/fetch.py` | Downloads four public series from FRED as CSV with retries and a local cache. |
| Validate | `src/validate.py` | Seven checks per series. Errors stop the run; warnings are logged. |
| Transform | `src/transform.py` | Quarter-end levels to quarterly returns; policy and actual portfolio returns; allocation effect. |
| Draft | `src/llm.py`, `prompts/` | Builds the prompt from the validated table only. A replay client reads saved drafts so results are repeatable; a live API client is included. |
| Evaluate | `src/evaluate.py` | Scores each draft: every number must match the table at the precision quoted, plus four rule checks. |
| Pack | `run.py` | Writes `outputs/performance_pack.xlsx` and `outputs/run_log.json`. |

### The example plan (invented)

| Asset class | Series used | Policy weight | Plan weight |
|---|---|---|---|
| US equity | S&P 500 **price** index (excludes dividends) | 60% | 63% |
| US investment grade bonds | ICE BofA US Corporate total return index | 25% | 22% |
| US high yield bonds | ICE BofA US High Yield total return index | 10% | 10% |
| Cash | 3-month US Treasury yield (quarterly = yield ÷ 4) | 5% | 5% |

The plan's difference from its policy mix is split into an **allocation effect** for each asset class: (plan weight − policy weight) × (asset return − policy portfolio return). Because the example uses index returns for both, there is no manager selection effect.

---

## Results of the pilot

### The quarter (2026 Q3, real index data)

| Asset class | Return |
|---|---|
| US equity (price index) | +2.0% |
| US investment grade corporates | −3.8% |
| US high yield | −1.8% |
| Cash (3-month Treasury) | +1.0% |
| **Policy portfolio** | **0.1%** |
| **Invented plan** | **0.3%** |
| Difference | 0.17 percentage points (equity overweight 0.06, investment grade underweight 0.12) |

### Pipeline run

- 3,145 rows from four series, fetched live, in about one second.
- Validation: 0 errors, 0 warnings.
- 19 unit tests, all passing, including five deliberately broken copies of the data (see [Tests](#tests)).

### Checking the AI's drafts (ten drafts, two prompts)

Five drafts per prompt. Prompt v1 is a plain request. Prompt v2 adds rules (use only figures from the table, quote to one decimal, name the quarter, say the equity index excludes dividends, do not forecast or advise). The drafts are in `outputs/commentary_v*_*.txt` and the scores in `outputs/eval_results.json`.

| Check | v1 (plain) | v2 (rules) |
|---|---|---|
| Every number matches the table | 1 of 5 | 5 of 5 |
| Says the equity index is a price index | 5 of 5 | 5 of 5 |
| No forecasts or recommendations | 5 of 5 | 5 of 5 |
| Names the quarter | 5 of 5 | 5 of 5 |
| Three or four sentences | 0 of 5 | 4 of 5 |
| **Passes every check** | **0 of 5** | **4 of 5** |

How to read it:

- The **sentence-count** check measures the prompt, not the model: v1 never asked for three or four sentences.
- The **number** check does not depend on the prompt. Four v1 drafts said the investment grade underweight added about 0.11 points; the table's own figure is 0.1169, which rounds to 0.12. One v1 draft quoted 0.29% and 0.12% for the plan and policy returns; the real figures are 0.32% and 0.15%, and the second number passed only because it coincidentally equals a different figure in the table.
- Five drafts per prompt is a **pilot, not a statistic**.

---

## Run it yourself

Requirements: Python 3.9 or later. The workflow uses only the standard library. `openpyxl` is needed only for the Excel pack.

```bash
git clone https://github.com/Tanmay-Kulk/quarterly-performance-pack-agent.git
cd quarterly-performance-pack-agent

python3 -m unittest discover -s tests -v   # 19 tests, no network needed

python3 run.py prepare     # fetch, validate, transform; writes the table and both prompts (needs internet)
python3 run.py evaluate    # score the saved drafts in outputs/commentary_v*_*.txt
pip install openpyxl && python3 run.py pack   # Excel pack and run log
```

For a new quarter, set `report_quarter` and `as_of` in `config.json` (the stale-data check measures age against `as_of`).

To score your own drafts, save a text file as `outputs/commentary_v3_1.txt` and run `python3 run.py evaluate`.

The drafts in this repository were produced by separate AI assistant runs and saved as files, so the evaluation is repeatable offline. `AnthropicClient` in `src/llm.py` shows the live integration (it needs `ANTHROPIC_API_KEY`); it is written but was **not run** for this pilot.

---

## For developers

### Project layout

```
config.json            series, weights, quarters, thresholds (change settings here, not in code)
run.py                 stages: prepare, evaluate, pack; logs to outputs/run_log.json
prompts/               v1.txt and v2.txt, version-controlled prompt text
src/fetch.py           FRED download with retries and cache
src/validate.py        data checks
src/transform.py       returns, portfolio and allocation maths
src/evaluate.py        scoring of AI drafts against the table
src/llm.py             ReplayClient (offline) and AnthropicClient (live)
tests/test_workflow.py 19 unit tests
outputs/               sample table, run log, drafts, scores, Excel pack
.github/workflows/     runs the tests on every push
```

### Validation checks (`src/validate.py`)

| Check | Catches | Severity |
|---|---|---|
| schema | no rows or unparseable dates | error |
| duplicate_date / order | damaged files | error |
| gap | no data for more than 7 days | error |
| stale | latest value older than 7 days before the as-of date | error |
| range | values outside plausible bounds for the series | error |
| units | a percent series that looks like decimals | error |
| outlier | a daily move above 10% | warning |

### Evaluation checks (`src/evaluate.py`)

| Check | Rule |
|---|---|
| numbers_supported | Every figure quoted (with %, "points", bps, or as a bare decimal) must equal a figure derivable from the table (returns, portfolio returns, contributions, allocation effects, weights, active weights) at the precision it is quoted. |
| price_only_caveat | The text must say the equity series is a price index that excludes dividends. |
| no_forecast_or_advice | No words such as recommend, should, expect, forecast, outlook, buy, sell. |
| names_period | The quarter is named. |
| three_or_four_sentences | Length matches the prompt's request. |

### Tests

`tests/test_workflow.py` uses `unittest` only:

- **Seeded defects:** a clean series passes; then five defects are injected one at a time (ten days deleted, a row duplicated, the latest 20 days removed, one value multiplied by ten, a percent series written as decimals) and each must be caught by name.
- **Transform:** quarter dates, index returns, yield returns, and that allocation effects add up exactly to the portfolio difference.
- **Evaluator:** a good draft passes; an invented number, a forecast, a missing caveat, unlabelled "points" and decimals are caught; derived active weights are allowed.

### Design decisions and trade-offs

- **Standard library only.** Fewer moving parts to install and review; the maths is simple enough not to need a dataframe library.
- **Validation stops the run.** A report built on bad data is worse than no report, so errors are not downgraded to warnings.
- **Replay client for the AI step.** Saved drafts make the evaluation repeatable and testable without keys or network; the live client sits behind the same `complete()` interface.
- **Numbers are checked by code, not by eye.** Wording can be good while a figure is quietly wrong; code checks it every time.
- **Prompts live in files with versions.** Changes to a prompt are reviewable like any other change.

### Runbook: what to do when it stops

| Message | Meaning | First step |
|---|---|---|
| `gap` | No data for more than 7 days | Check the source's calendar; refetch with the cache cleared |
| `stale` | Latest value is old | Confirm the source has published; do not reuse last quarter's file |
| `duplicate_date` or `order` | The file is damaged | Refetch; if it repeats, raise it with the data owner |
| `range` or `units` | Values look scaled or in the wrong unit | Compare to the source page before touching the data |
| `outlier` (warning) | Daily move above 10% | Check it is real before it goes in a report |
| Evaluation fails | The AI quoted a number not in the table, skipped the price-only note, or gave advice | Do not send; regenerate with the stricter prompt or write it by hand |

### Responsible use checklist (before any run)

- Only public data goes into a prompt. Client names, holdings, fees and manager documents never do.
- A person reads and signs off every commentary before it leaves the team, whatever the checker says.
- The checker catches wrong numbers and rule breaks. It cannot judge whether a sentence is fair or useful.
- Prompt version and model are recorded, and any change is listed in the change log.
- Outputs that fail the checks are kept for review and never silently retried until they pass.

### Right-sizing: three tools for three jobs

| Job | Right size | Why |
|---|---|---|
| Summarize a meeting or draft an email | A built-in assistant feature | No integration, no pipeline, nothing to maintain |
| File incoming emails into the right folder and notify the team | A low-code flow | Simple trigger and actions a business team can own |
| This workflow: validated data, calculations, AI draft, automatic evaluation, audit trail | A small script with tests | Needs validation logic, numeric checking and a version-controlled audit trail |

Only the third is built here; the first two rows are guidance.

### Limitations

- The equity series is a price index and excludes dividends. The Excel pack and every prompt say so.
- Cash return is the prior quarter-end 3-month yield divided by four, an approximation.
- The bond indexes on this public source cover only about three years.
- Weights are invented; manager selection and fees are not modelled.
- The evaluator cannot judge fairness, and a number can match a different allowed figure by coincidence (this happened once in the pilot).
- Ten drafts is a pilot. A real deployment would use the team's own cases and thresholds.

### Possible next steps

- Run the live client on a schedule and log model and prompt versions automatically.
- Add a currency-adjusted international equity series and a fixed income benchmark with a true total return series.
- Wrap the file-in, file-out steps in a low-code flow so a business team owns the trigger while the script keeps the checks.
- Add a second reviewer step that flags sentences whose tone or emphasis a person should look at.

### Change log

- **v1 prompt:** a plain request. **v2 prompt:** adds explicit rules (figures from the table only, quote to one decimal, name the quarter, say the equity index is a price index, no forecasts or advice).
- **Evaluator fixes**, each found by a test or by reading the first results, each now covered by a test:
  1. It accepted a number that was only close to an allowed one. Now an exact match at the precision quoted.
  2. It ignored figures written as "points" and bare decimals such as "0.11". Both are checked now.
  3. It flagged "3%" as invented. The active weights (plan minus policy) are derived from the table and are now allowed.

---

## Data sources and attribution

Data is downloaded at run time from FRED, Federal Reserve Bank of St. Louis (https://fred.stlouisfed.org). It is not stored in this repository.

- S&P 500 (`SP500`): S&P Dow Jones Indices LLC, via FRED.
- ICE BofA US Corporate Index Total Return Index Value (`BAMLCC0A0CMTRIV`) and ICE BofA US High Yield Index Total Return Index Value (`BAMLHYH0A0HYM2TRIV`): ICE Data Indices, LLC, via FRED.
- Market Yield on US Treasury Securities at 3-Month Constant Maturity (`DGS3MO`): Board of Governors of the Federal Reserve System, via FRED.

The quarterly returns in `outputs/` are derived values for the example, not a redistribution of the raw index data. Check each provider's terms before reusing the data.

## Disclaimer

This is an educational example using public data and an invented plan. It is not investment advice, and nothing in it describes any real plan, manager or firm.

## Author

Tanmay Kulkarni · [LinkedIn](https://www.linkedin.com/in/tanmaykulk/)

## License

MIT, see [LICENSE](LICENSE).
