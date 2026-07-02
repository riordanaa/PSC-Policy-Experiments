# value_decomposition_study — the main 2026 study folder

Deterministic policy studies on the thesis simulator (no RL). Four campaigns live here, newest
first. **Reports (ranked) are indexed in [`report/README.md`](report/README.md)** — the capacity
report (`report/robustness_report.pdf`) is the key output of this folder.

## Campaigns and their files

**3. Capacity / robustness (June 22 — the capacity report):**
`exp_robustness.py` (gated driver: capacity stress test, δ sweep, 2D grid),
`analyze_robustness.py` (per-phase metrics, channels, fills), `make_robustness_figures.py`
(fig1–fig9), `robustness_prereg.md` (pre-registration), `MEETING_NOTE.md` (markdown twin of the
report) → `report/robustness_report.pdf`.

**4. Lead time × severity (June 23):**
`exp_leadtime.py` (wraps exp_robustness.run_cell; injects PHYSICAL/AGENT_LEAD_TIME and MN1
decrease_factor at runtime), `analyze_leadtime.py`, `leadtime_prereg.md`
→ `report/lead_time_severity_report.pdf`.

**1–2. Value decomposition + DS-seat (June 10–11 — where shed/taper were found):**
`run_vds.py` (named policies + regimes; the study runner), `gates_vds.py` (verification gates),
`metrics_vds.py`, `policies_v2.py`, `analyze_phase1.py`, `analyze_phase2.py`, `analyze_ds_seat.py`,
`make_figures_vds.py`, `run_sat_ladder.py` → `report/value_decomposition_report_v2.pdf`.

## Audit trail (read before citing numbers)

- `hypotheses/H1–H10.md` — one card per claim: method, numbers, verdict.
- `LEDGER.md` — everything tried / kept / discarded, with reasons.
- `STATUS.md` — chronology, including discarded batches.
- `audit/` — independent audit scripts that re-derive headline numbers from raw CSVs.
- `PLAN.md`, `NEXT_PLAN.md` — planning documents (historical).

## Conventions (all campaigns)

Bit-exact reproduction gates before any reported number; tuning seeds 1–10 / reporting seeds
11–30, never mixed; dual cost accounting on cost claims. `results/` (per-period CSVs) is
local-only (gitignored) — every reported number traces to a CSV there. The runner infrastructure
reused here comes from `routing_study/run_ladder.py` and `routing_study/metrics.py` — do not move
those.
