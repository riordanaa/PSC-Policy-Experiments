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

## 2026-06-10 — Phase 2 underway (sat regimes; documented scope, gates G5/G6 passed)

- H5 ladder (sat50,d48, reporting seeds): routing helps but no longer solves — a 3,702k →
  c 2,737k (−26%) → d 1,861k (−50%); fill stuck ~0.9; queue relocates to DS_healthy.
  urgent20: lost patients barely move across the ladder (1,768 → ~1,600) — the patient-facing
  lever flip is visible: routing reshuffles who waits, can't create product.
- H6 screen (tuning seeds): the frontier is REAL. Best single lever = standing buffer AT
  DS_HEALTHY (B1440: dp 1,968k at 74k premium, fill 1.0). Location ordering:
  healthy >> both >> disrupted. Ordering shapers alone ≈ nothing (supply-bound).
  **Regime flip discovered: static-priority allocation HARMFUL under scarcity**
  (3,362k vs proportional 2,737k) — starving one HC at the queue-bound healthy DS collapses
  its trust in the healthy chain and pushes its orders toward the dead one.
- IN FLIGHT: full-compound tuning (buffer-healthy + reroute + taper, B∈{960,1440});
  H7 severity x duration map (sat70/50/30 x d5/17/48, ladder a,c,d + per-cell frozen
  buffer grids, reporting seeds, urgent0).
- Next: frontier reporting runs at primary cell (both configs), Phase-2 audit, cards
  H5–H7, report.

## 2026-06-11 — Phase 2 complete, audited; study DONE

- Frontier (reporting seeds): compound (buffer-healthy + reroute + taper) dominates —
  766,830 at B960 (−79%, fill 0.990) / 831,733 at B1440 (fill 1.000) urgent0;
  lost patients 505 vs 1,591 baseline (−68%) urgent20. Confirmatory matched-premium
  test PASS (~2.4× over buffer-only). VNS not justified (no residual gap) — skipped per plan.
- Lever-flip map complete (figures in results/figures/): no action (d≤stock-cover ~6p)
  → routing (no scarcity) → compound (mild) → buffer-only (severe; sharp rerouting is the
  WORST measured policy at sat30/d48: 7,657k vs do-nothing 5,133k).
- **Phase-2 audit: 11/12 PASS.** The exception: my tables' 1-decimal display rounding led me
  to claim fill 1.000 for the B960 compound (true: 0.990) and B1440 buffer-only (0.989).
  CORRECTED in H6/H7 cards and the report; cost/premium/lost claims all verified exact.
  Audit scripts preserved in `audit/`.
- NEXT_PLAN.md written: severity-aware redirect + demand-aware buffer sizing (new policy
  class — awaiting user review), recurring/ramped regimes (new regime — user call),
  deferred in-scope items listed. Nothing beyond approved scope was executed.
- Final report: `report/value_decomposition_report.pdf` (5 pages, summary top,
  next steps end). No gate failures all night; no kill conditions tripped.
