# Reports in this folder (ranked by importance)

| # | Report | What it is |
|---|--------|------------|
| **1** | **`robustness_report.pdf`** | **THE capacity report** (June 2026, advisor-facing). Stress-tests the rerouting/shed findings against healthy-chain (MN2) capacity, trust-sensitivity δ, and precise metric definitions. Headline: shed is a *capacity-conditional misaligned incentive* — helps the disrupted distributor at any capacity, flips from system-win to system-disaster below MN2 ≈ 180–240; the rerouted load is amplified ~10× on the healthy chain, not relocated. Source `robustness_report.tex`; figures `figures/fig1–fig9_*.pdf`; markdown twin `../MEETING_NOTE.md`; pre-registration `../robustness_prereg.md`; harness `../exp_robustness.py` (+ `analyze_robustness.py`, `make_robustness_figures.py`). |
| **2** | **`lead_time_severity_report.pdf`** | Follow-up (June 2026): re-runs the capacity sweep across lead times and disruption severities. Longer lead time does NOT worsen cost (base stock auto-scales its buffer; the collapse mildens) but lost patients jump ~2.5× past lead time ~5; the shed/flip phenomenon is severity-gated (inert below ~65–80% cut). Source `.tex`; figures `figures/lt_fig*.pdf`; pre-reg `../leadtime_prereg.md`; harness `../exp_leadtime.py` (+ `analyze_leadtime.py`). |
| **3** | **`value_decomposition_report_v2.pdf`** | The **DS-seat report** (June 10–11) — *the report that led to the capacity report*: where shed was found to be a good distributor policy and taper was introduced. Simple distributor compound (shed × taper × standing order) removes 49–51% of base stock's disruption loss (thesis RL claimed 89%, unreplicated); demand-shaping confirmed real. v2 supersedes v1. |
| 4 | `value_decomposition_report.pdf` | Earlier v1 of the same study (value decomposition + lever-flip map, before the DS-seat phase). Kept for the record; cite v2 / the consolidated scorecard instead. |

`value_decomposition_report.tex` is the LaTeX source of the latest revision. `figures/` holds all
report figures: `fig1–fig9_*` belong to the capacity report, `lt_fig*` to the lead-time report.
`_build/` is local LaTeX output (gitignored). If a `*_latest.pdf` appears, it is a stale
lock-workaround copy (gitignored) — the canonical file is the plain name.

**Caveat for all numbers:** treat findings as evidence-backed claims, not settled facts — check
`consolidated_report/consolidated_findings.pdf` (status codes / do-not-cite list) for anything
from the June-10/11 reports, and re-verify load-bearing numbers against the raw CSVs
(`../results/`, local-only).
