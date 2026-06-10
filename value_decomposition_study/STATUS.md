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

## 2026-06-11 — Part A verification results + Part B incident log

- **A1 REFUTES "foresight adds nothing":** superset oracle (compound + JIT buffer at the
  HEALTHY DS) = 180,137 tuning vs deployable 270,759. Decomposed: zero-lead (deployable)
  buffer captures ~36k; true pre-onset foresight adds ~54k (~5% of baseline). The old
  ceiling's buffer sat at the worthless (disrupted) location. Reporting runs done
  (a1_superset_B240_lead10 / _zerolead, seeds 11–30).
- **A3: slack buffer negative was location-specific:** healthy-located standing buffers buy
  +38–75k even in slack (B480 reporting run done). H2 restated.
- **INCIDENT (Part B first screen, all results DISCARDED):** three wiring bugs contaminated
  the first DS-seat screen — CLI default --throttle-c=1.2 silently activated the throttle in
  every run (gates passed because gate-args had it off: gate-args/CLI-defaults divergence);
  ordering families ran with default prio_hc1 allocation instead of proportional; watch_mn
  was only wired when the taper knob was set, so elevated/prebook/shed never saw the MN
  signal (exposed by bit-identical rows). Fixes: throttle default 0, needs_mn_watch flag,
  explicit flags on every run, and a NEW CLI-PATH GATE (dsseat via the actual CLI must
  reproduce rung-a bit-for-bit — PASS). Clean screen re-launched; no conclusions were drawn
  from the contaminated batch.

## 2026-06-11 — Part B COMPLETE (H8); HARD DECISION POINT reached

- **The user's hypothesis test, answered (reporting seeds, thesis world, thesis metric):**
  best simple DS-seat compound (shed x taper x standing-B480) removes **49.1%** (urgent0) /
  ~50% (urgent20) of base stock's PSC-profit loss, with better fill (0.858 vs 0.808) and
  fewer lost patients (1,575 vs 1,768). vs thesis RL claim of ~89% (Table 3.9, unreplicated).
- Mechanisms: demand-shaping REAL (shed +21.8%, both HCs better, control shed_inverse
  −14.3%); taper +24.9% but bookkeeping-driven and +9% lost patients ALONE (shed offsets it);
  state-elevated DEAD by supply physics (elevated-climb check: during-inv 4 units); standing
  buffer +5%. Checked outputs all executed (climb / sign-flip / per-HC).
- Part A corrections applied to cards: foresight ≈ +54k when buffer correctly located
  (H4 corrected); slack buffer negative is location-specific (H2 qualified); bounded "room"
  phrasing in place (A2).
- Independent Part A+B audit agent running. **Part C NOT started — awaiting user review of
  Part B per the plan's hard decision point.**
