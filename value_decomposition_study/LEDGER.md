# LEDGER — tried / kept / discarded

| Item | Status | Reason (one line, traceable) |
|---|---|---|
| Recovery-aware write-off (H1) | DISCARDED | Glut unchanged (excess 3,033 vs 2,967), cost +2%; double-order committed mid-window — revival at recovery too late by construction. |
| γ-discount write-off (H1b, γ=0.5) | DISCARDED (marginal) | −1.5% (1,044k vs 1,063k); whole accounting channel ≈ glut holding ~25–30k; rerouting fixes the glut better as a side effect. |
| Standing DS buffers in slack (H2) | DISCARDED | Coverage ≤ 0 at every B (B600: −241k at +31k premium); buffer feeds the dead-factory queue + glut. Supersedes broken-routing "42% insurance". |
| Delivery-rate detect-then-reroute (H3) | DISCARDED | Strictly worse than built-in trust EMA (1,239k vs 1,063k); ~6-period stock-cover masking is structural for ANY downstream delivery-statistics detector. |
| Upstream-signal reroute (H3b) | **KEPT — promoted to compound** | Equals oracle exactly (294,796 urgent0; 203 lost urgent20). Two-line rule; quantifies info-sharing value (~750k + 242 patients). |
| JIT pre-build B=120 (H4 component) | KEPT (ceiling only) | +11k value at 2.7k premium WITH oracle window; collapses for B>120; no patient benefit. Not worth deploying without oracle timing. |
| Static-priority allocation | KEPT (fairness-costed baseline) | −12.4% vs proportional; dispersion cost ±0.023 fill. Both baselines carried per A3. |
| backlog-priority / serve-captive allocation | DISCARDED (prior study) | +56% / +25% — alternating failures degrade both trust loops. |
| rotating-priority allocation (A3) | DISCARDED | Catastrophic: dp 1,630k urgent0 (+53% vs static priority), lost 740 urgent20 — parity alternation = alternating failures, same failure mode as backlog-priority. No fairness-free priority exists. |
| priority-with-floor 0.25 (A3) | DISCARDED | ≈ proportional on cost (1,203k vs 1,210k), dispersion WORSE than static priority (+0.031 vs +0.023) — dilutes priority without buying fairness. |
| MN-down order taper m=1.0 (A1) | KEPT (with caveat) | Tuning: dp 270,759 vs 294,240 no-taper — but dual accounting shows gain is ~all dead-factory bookkeeping (ex-MN: 218k vs 211k, ~neutral). Kept for convention-(i) reporting; flagged as accounting-sensitive. |
| "Foresight adds nothing" claim | **CORRECTED (A1 verification)** | Superset oracle with HEALTHY-located JIT buffer: 180k vs deployable 271k. ~36k deployable (zero-lead), ~54k true foresight (~5% of baseline). Old ceiling's buffer was at the worthless location. |
| Slack buffer blanket-negative (H2) | **CORRECTED (A3)** | Location-specific: disrupted/split locations negative; HEALTHY-located standing buffer +38–75k even in slack. |
| First DS-seat screen (Part B) | DISCARDED (contaminated) | CLI default throttle active everywhere + default prio alloc on ordering runs + watch_mn unwired for non-taper knobs. Lesson: gate the ACTUAL CLI path, not just the library path; never trust defaults in run commands. |
| C1 headroom cap v1 | DISCARDED (bug) | Bootstrap deadlock: cold-start delivery rate 0 → cap 1 unit → simulator drops orders ≤1 (simulation_runner.py:141) → zero flow forever (margin-invariant 94M cost flagged it). Fix: cap binds only on the surge — floored at the source's equal share. |
| C1 severity-aware redirect (both signals) | **REFUTED (H9)** | Delivery-cap +25–50% worse than rung-c (orders are the production signal — capping them throttles the supplier's ramp); capacity-cap also worse (over-ordering costs the orderer nothing here; suppression forfeits queue position for no saving). sat30 penalty is delivery-mix, not order-volume. 9-cell sweep killed per protocol. |
| C2 demand-aware buffer sizing | **KEPT — the robust knob** | B* = (demand − surviving deliverable) × duration. sat50/urgent20 reporting: lost 41 vs 505 at frozen optimum (dp 1,726k vs 1,865k). Other endpoint (sat30 → 4,800) independently = measured frozen optimum. |
| C3 buffer location at sat30 | **CORRECTED map cell** | At severe scarcity healthy-located is NOT optimal: disrupted-B4800 = 2,417k (reporting; −30% vs healthy 3,466k); split-B2400 = 2,563k. Location optimum flips with severity — buffer goes where the unservable demand is. |
| DS-seat compound (H8) | KEPT — named policy | shed × taper × standing: 49.1%/50.7% of BS loss removed in the thesis world; taper's patient-cost caveat attached. |
