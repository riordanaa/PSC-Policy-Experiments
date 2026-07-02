# routing_study — is the disruption pile-up physics or a routing artifact? (June 9, 2026)

**Headline (audited):** 67–91% of the "unavoidable" disruption cost is removable by hospital
routing rules alone (HC2 equal-split + stranded on-order were the artifact). Also found the
`NormalDistPatientModel` RNG-reseed bug that made historical "multi-seed" normal-demand runs a
single demand path.

- Report: `report/routing_report.pdf`. Design/results notes: `routing_study_design.md`,
  `routing_results.md`, `routing_hypothesis.md`, `routing_forward.md`, `PLAN.md`.
- Code: `run_ladder.py` (build/run/log runner), `policies.py`, `metrics.py` (per-phase metrics),
  `verify.py` (gates), `tune_c.py`, `make_figures.py`.
- `results/` is local-only (gitignored).

**⚠️ Load-bearing infrastructure:** `run_ladder.run_one` (with `hc_factory`/`ds_factory`/
`post_build` injection) and `metrics.seed_phase_metrics` are imported and reused by every later
study (`value_decomposition_study/*`), and the robustness/lead-time gates compare bit-exactly
against `results/` CSVs produced here. Do not move or edit this folder's code.

**Status caveat:** some headline numbers were later refined — check
`consolidated_report/consolidated_findings.pdf` before citing.
