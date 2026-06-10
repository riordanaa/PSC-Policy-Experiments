# Value-Decomposition Study — Plan (written before any run, 2026-06-10)

> **AMENDED (Step 0 reconciliation, same day, after Phase 1 closed and before Phase 2).**
> Reconciled against the routing study and fixed-routing (understanding) study reports.
> Status: Phase 1 COMPLETE (cards H1–H4 in `hypotheses/`); amendments A1–A4 below are
> Phase-1 addenda + Phase-2 design freezes. STATUS.md is the heartbeat; LEDGER.md tracks
> tried/kept/discarded.

## Step-0 reconciled baselines (carried through every comparison from here on)

| Baseline | dp-cost urgent0 | lost urgent20 | Fairness |
|---|---:|---:|---|
| **fairness-neutral**: rung-c routing + proportional allocation | 1,209,659 | 510 | neutral |
| **fairness-costed**: rung-c routing + static-priority allocation | 1,062,538 | 445 | dispersion ±0.023 |

Phase-1 reconciled facts both reports + this study agree on: routing −67% to −91%;
allocation ≤12% (static priority, fairness-costed); write-off glut is real but cheap
(~25–30k) and is removed as a SIDE EFFECT of instant rerouting (H3b/H4: glut excess
478 vs 2,967); buffers in slack are zero-to-negative (H2 — supersedes the broken-routing
"insurance captures 42%" number); info-sharing reroute = oracle exactly (H3b);
room above it ≈1% (H4).

## Amendments (user, 2026-06-10)

- **A1 (taper lever + detection wording + dual accounting):** an order-taper-toward-
  failed-source lever joins the deployable compound and the ceiling: the DS, on the SHARED
  UPSTREAM signal (its MN below 50% nominal lines), caps orders to that source at the
  observed delivery rate (discrete pre-registered rule). Detection constraint reworded:
  *detection may trigger discrete pre-registered response rules including order-taper,
  never feed a continuous ordering optimizer.* All residual decompositions reported under
  BOTH dead-factory accounting conventions: (i) full system cost; (ii) excluding
  MN-backlog cost (undeliverable queue bookkeeping).
- **A2 (duration axis):** Phase-2 severity slice is crossed with duration {5, 17, 48}
  (thesis short/moderate/long), giving the severity x duration map for the lever flip.
- **A3 (fairness-neutral allocation variants):** rotating-priority (priority HC alternates
  by period parity) and priority-with-floor (non-priority HC guaranteed floor=0.25 of
  inventory first) join the allocation screen — tested in slack (Phase-1 addendum) and in
  the Phase-2 screen. Both baselines (A3 table above) carried through every table.
- **A4 (frozen grids — no parameter chosen outside these; selection on tuning seeds 1–10
  only, reported curves on 11–30):**
  - Severity (MN_healthy factor during 110–157): {0.7, 0.5, 0.3} (sat70 expected unsaturated
    — kept as the slack-side anchor of the flip map).
  - Duration: {5, 17, 48} (windows 110–115, 110–127, 110–157).
  - Buffer grid per (severity, duration) cell, scaled to computed shortfall
    S = max(0, 240 − 20 − 400×factor) × duration:
    B ∈ {0.25, 0.5, 1.0, 1.5} × S (rounded to 10), locations {disrupted, healthy, both}
    screened at the primary cell only, best location carried to other cells.
  - Taper: thresh 0.5 frozen, m ∈ {1.0, 1.5}; trigger ∈ {fill-statistic, upstream-signal}.
  - Throttle: c ∈ {1.2, 1.5}. SS-freeze: {on, off}.
  - Allocation: {proportional, prio_hc1, rotating_priority, prio_floor(0.25)}.
  - Detection reroute: down_share 0.1 frozen (H3b); upstream threshold 0.5 frozen.
  - Primary Phase-2 cell for the full frontier: (sat50, 48). Other cells: ladder +
    buffer sweep only (the flip map).

## Execution protocol (user, 2026-06-10)

Parallelize independent runs within a phase; serialize across phases. Kill conditions are
hard stops. Each phase audited by a separate agent that re-derives headline numbers from
raw CSVs WITHOUT importing the study's metrics module. Gate failure: retry once, then stop
that branch and log to STATUS.md. Correctness-gate failure (determinism/conservation):
halt everything and report. STATUS.md heartbeat maintained; commit per hypothesis card.
When simple + saturated scenarios are complete and audited: write NEXT_PLAN.md; execute
freely only within approved scope (the documented MN_healthy expansion); PAUSE for user
review before any new regime or policy class beyond it.

## Objective

Complete and stress-test the value decomposition under unforecastable disruption:
**routing flexibility captures most value; distributor policy has bounded room that opens
only under supply scarcity; learning has little room at either echelon.** The job is to
complete and stress-test that thesis, not invent a new one. Honest expected outcome, stated
up front: *little room for learned policies in the simple scenario; distributor policy
matters only under supply scarcity.* If a finding contradicts this, it is documented, not
smoothed over. If a phase's result kills the next phase, stop and report that.

## Standing constraints (non-negotiable)

- Stay close to the thesis simulation setup. No web, nothing outside this folder.
- **Baseline for all comparisons: the routing-fixed compound** (rung-c routing +
  static-priority allocation; 1.06M during+post urgent0 / 445 lost patients urgent20).
  Never broken-routing base stock alone.
- The old −468k/−654k decomposition numbers are SUPERSEDED (measured on broken routing) and
  appear nowhere except as superseded.
- Established prior findings (challengeable only with evidence): allocation channel ≤12%,
  captured by a trivial static rule, smart rules backfire up to +56%; detection's measured
  value is detect-then-REROUTE, not detect-then-buffer (≈0).
- **RNG-reseed fix stays** (re-seed after sim construction; gate 6 guards it). All gates
  (determinism, conservation, cross-seed variance, baseline reproduction) re-run and reported
  for every new code path and for the new regime.
- Seeds: tuning 1–10 (any parameter choice), reporting 11–30 (every reported number), paired.
- Metrics panel (fixed): premium (pre-phase cost Δ vs the compound baseline) vs coverage
  (during+post damage reduction); fill rate (cumulative served/demand per phase); lost
  patients (urgent20 only, never pooled); peak backlog (DS_disrupted / DS_healthy / system);
  **area-under-backlog** (TTR appendix-only); cost decomposed holding-vs-backlog per phase;
  glut (post-disruption excess inventory); HC-dispersion; **bullwhip (var(orders)/var(demand)
  per echelon per phase — new)**. System-level scoring always.
- Every number traceable to a CSV produced by a run. "Did not measure" stated honestly.
- VNS: tool of last resort; default screen-and-compose; if the space is simple, say so and skip.
- Detection: a trigger for routing/rationing responses only — never an input to an ordering
  optimizer.

## Phase 1 — Complete the simple scenario (slack regime, rung-c world)

Four hypothesis cards, each in `hypotheses/H*.md` with Hypothesis / Method / Result / Verdict.

| Card | Hypothesis | Method |
|---|---|---|
| **H1 write-off glut fix** | The post-recovery glut (peak 3,930 vs 332 pre-mean; write-off DOUBLES baseline glut) is removable by a recovery-aware write-off: count a source's stale pipeline again once that source's delivery rate recovers (θ=0.5 on `ontime_deliv_rate`). | New `RecoveryAwareWriteoffHC`; run vs rung c; glut metrics + dp-cost. Gate: with refinement off, bit-identical to rung c. |
| **H2 buffer null frontier (slack)** | Per prior evidence, a standing DS buffer buys almost nothing in the slack regime (fill already 1.000); at most it shaves part of the ~10-period redirection transient at premium cost. | `BufferDS` (order up to up_to+B), B swept {60..600}, at DS_disrupted and at both DSs; premium-coverage curve on reporting seeds (urgent0; spot-check best B on urgent20). |
| **H3 deployable detect-then-reroute** | Most of the c→d gap (~0.88M, oracle onset reroute) is deployable, because the onset is detectable at ~zero lag from delivery shortfall (prior finding: every signal has negative lead for ANTICIPATION but detection AT onset is nearly free). | `DetectRerouteHC`: step-split triggered when a source's delivery rate < θ for w consecutive periods, reverting on recovery; θ, w from tuning seeds. Compare to rungs c and d. |
| **H4 ceiling on the fixed-routing world** | The practical ceiling (best-of-oracle-family, honestly labeled — not a provable optimum) leaves only a small gap above the best DEPLOYABLE compound, and most of the gap is bookkeeping (dead-factory queue cost). | Compose: oracle onset reroute (rung d) + static-priority allocation + JIT pre-build at DS_disrupted (up-to+B only periods 100–110, B swept on tuning seeds) + H1 refinement. Report ceiling vs best deployable. |

**Phase-1 verdict to produce:** room remaining between best deployable simple compound and
the ceiling in the simple scenario — the headline "room for learning" number. Expected: small.

## Phase 2 — The saturated regime (only after Phase 1 is complete and written)

**The one scope expansion, deliberately chosen and documented:** during the same window
(110–157), MN_healthy is also cut to **50% capacity** (second `DISRUPTIONS` entry,
`manufacturer_index=1`, factor 0.5). Rationale for this over a demand surge: demand stays
thesis-comparable; it reads as "a wider disruption". Healthy-chain deliverable ≈ 200/period
< total demand ≈ 240/period → genuine scarcity; rerouting alone cannot reach fill 1.000.
**This is a new world: gates re-run there** (determinism, conservation, cross-seed variance,
saturation sanity: aggregate during-fill < 1 under rung-c routing).

| Card | Hypothesis | Method |
|---|---|---|
| **H5 routing under scarcity** | Routing still captures a large share but no longer ~all; a residual opens that only inventory can serve. | Re-run routing ladder (a, b, c, d) in the saturated regime, both demand configs. |
| **H6 the real frontier** | Under scarcity a genuine premium-coverage frontier exists: buffers buy coverage; taper/throttle/SS-freeze shape its cost; allocation (rationing) matters for lost patients/fairness. | Buffer sweep = null frontier. Screen taper / throttle / SS-freeze / allocation rules individually on tuning seeds vs saturated rung-c compound; compose survivors; reporting seeds. Confirmatory test: at matched premium, does any composition dominate the buffer-only curve? |
| **H7 lever flip** | There is a severity boundary where the dominant lever flips routing→buffering. | Within the SAME saturated definition, vary MN_healthy factor over {0.7, 0.5, 0.3} (3-point severity slice, tuning-seed scale first, reporting seeds for the kept points); plot routing-share vs buffer-share of recovered value. |

## Phase 3 — Composition search (ONLY if H6 shows a rich space + visible gap to ceiling)

Screen-and-compose first. VNS only if simple composition leaves a measured gap — if the
space is simple, say so and skip (expected per prior evidence). Detection only as trigger
for reroute/rationing (H3-style), never inside an ordering optimizer.

## Organization & multi-agent protocol

- Folder: `value_decomposition_study/` — `policies_v2.py`, `run_vds.py`, `gates_vds.py`,
  `metrics_vds.py`, `hypotheses/H1..H7.md`, `results/`, `report/`.
- Each hypothesis card is written when its runs land: Hypothesis / Method (exact commands) /
  Result (numbers traceable to CSVs) / **Verdict: TRY / DON'T-TRY going forward**.
- An independent **audit agent** re-derives every headline number in the final report from
  the raw CSVs before the report is finalized; discrepancies are reconciled or reported.
  Contradictions between cards are flagged in the report, not averaged away.
- Reuse, don't rewrite: `routing_study/run_ladder.py` (build/run/log; extended with an
  optional `hc_factory`), `routing_study/metrics.py` (panel), `understanding_study/
  alloc_policies.py` (AllocFlexibleDS + static priority).
- Commit + push after each phase. Final deliverable: `report/value_decomposition_report.tex`
  → PDF (concise; summary at top; next steps at end).

## Kill conditions

- H1 fails (glut not removable without losing write-off savings) → report; ceiling (H4) runs
  without the refinement.
- H4 shows large room in the simple scenario → contradicts prior evidence; STOP phase
  progression, double-check gates, report the contradiction prominently.
- Phase-2 saturation sanity fails (fill = 1.0 even at 50%) → regime mis-specified; fix factor
  or stop, do not silently escalate severity beyond the documented choice.
- H6 frontier degenerate (buffer-only curve undominated everywhere) → Phase 3 skipped with
  that as the finding.
