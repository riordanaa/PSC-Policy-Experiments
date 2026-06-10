# STATUS — value-decomposition study (heartbeat)

## 2026-06-10 — Step 0 + Phase 1 complete

- Gates G1–G5 (slack) PASS; sat50 design check (G5,G6) PASS (during-fill 0.875 = genuinely scarce).
- Phase 1 cards written: H1 (glut fix — REFUTED, don't-try), H2 (buffers in slack —
  zero-to-negative, null frontier degenerate; supersedes the 42%-insurance number),
  H3 (delivery-rate detection — REFUTED, ~6-period stock-cover masking costs ~944k),
  H3b (upstream-signal reroute — CONFIRMED, equals oracle exactly: 294,796 urgent0 /
  203 lost urgent20), H4 (ceiling 284,120; room above info-sharing compound ≈1%).
- Step-0 reconciliation done; amendments A1–A4 + frozen grids written into PLAN.md.
- IN FLIGHT: Phase-1 addenda (A1 MN-down order taper; A3 rotating/floor allocation;
  dual accounting in analysis) + independent Phase-1 audit agent.
- Next: Phase 2 (sat ladder, screen, frontier at (sat50,48), severity x duration map).
- No gate failures. No kill conditions tripped.

## 2026-06-10 — Phase-1 audit + addenda progress

- **Independent audit: 12/12 PASS** (separate agent, self-contained pandas, no metrics-module
  import; script at jobs tmp/audit_claims.py). h3b == d_oracle bit-identical confirmed
  independently (max diff 0.0 across 60 columns). All reporting files contain exactly
  seeds 11–30.
- A1 taper tuning (seeds 1–10): m=1.0 wins (dp 270,759 vs no-taper 294,240). Dual accounting
  shows the gain is almost entirely dead-factory bookkeeping (ex-MN-backlog: 218k vs 211k —
  taper ~neutral under convention ii). Reporting runs in flight.
- A3 allocation variants (rotating-priority, priority-with-floor) in flight on reporting seeds.
