# Routing Study — Plan

**Question.** What fraction of the disrupted distributor's ~3,800-unit backlog pile-up is an
artifact of the routing configuration (HC2's fixed equal-split + stranded on-order suppressing
re-ordering from the healthy chain), versus genuinely unavoidable given the ~20/period supply cap?

This is deterministic (no RL, no checkpoints). The answer gates the project framing: if routing
recovers a large fraction, the value decomposition (−468k buffer / −654k timing) is conditional on
a frozen routing layer and must be recomputed; the detection claim narrows to "detect-then-buffer."

## Verified premises (read from this repo's code before planning — 2026-06-09)

| Claim | Status | Where |
|---|---|---|
| HC1 splits by trust, HC2 splits equally (fixed rule) | ✅ confirmed | `config.py:30` `HC_ORDER_SPLIT = ['bytrust','equally']` |
| Trust EMA with δ = 0.1 on on-time delivery rate | ✅ confirmed | `config.py:31`; update at `decision_maker.py:129-131` |
| HC order formula subtracts on-order → stranded pipeline suppresses re-ordering | ✅ confirmed | `decision_maker.py:153-154` |
| Suppression hits BOTH channels (split applied to total orderAmount) | ✅ confirmed | `decision_maker.py:158-174` |
| HC order cap: `max(2×demand, 120)` per period | ✅ confirmed (not in original plan — bounds the arithmetic) | `decision_maker.py:155-156` |
| Trust-split never fully redirects: trust converges to EMA of delivery rate (~trickle), so even 'bytrust' keeps sending ~15-20% to the dead chain | ✅ confirmed from formula (verify empirically) | `decision_maker.py:166-174` |
| Disruption: MN index 0 → disrupted DS, periods 110–157, factor 0.95 | ✅ confirmed | `config.py` DISRUPTIONS |
| On-order lifecycle (do stranded orders deliver late post-recovery → glut?) | ⬜ document in design doc before coding | `simulator/agent.py` / `network.py` |

**Naming convention (avoid cross-chat confusion):** this repo uses 0-based indices. Disrupted
chain = MN index 0 → DS index 0 (plots label it "DS1"); healthy chain = MN 1 → DS 1 ("DS2").
The collaborator dossier calls these ds_2 (disrupted) and ds_3 (healthy). All study docs use
**DS_disrupted / DS_healthy** to be unambiguous.

## Known gap vs the plan as written

The plan says "reuse the existing harness" (paired-seed, 20 fixed seeds, phase-stratified panel,
clairvoyant ceiling). **That harness is not in this repository** — it was built in the partner
analysis environment. What exists here: the simulator, all-rule-based runs (proven in
`r5_test_results_basestock_ds1_disrupted/`), and a profit/backlog scoring script from the
reward-fix work. Resolution, in order of preference:
1. Drop the partner harness code into `routing_study/external_harness/` if available; or
2. Build a minimal paired-seed scoring harness here (~200 lines; deterministic; this folder).
The headline question (baseline vs ladder) does NOT need the clairvoyant ceiling — ceiling
comparison figures are produced only if (1) happens or the ceiling is re-derived later.

## The ladder (all DS agents on plain base stock; routing rule is the only change per rung)

- **(a) Baseline** — config exactly as-is. Must reproduce the known pile-up (sanity gate).
- **(b) HC2 → trust-split** — flip `HC_ORDER_SPLIT` to `['bytrust','bytrust']`. The core test.
- **(c) (b) + faster rerouting + stale-order write-off** —
  - sharper redirection: raise δ and/or a sharper split response (e.g. trust^p normalization);
    parameters chosen on TUNING seeds, reported on HELD-OUT seeds (see Methodology);
  - write-off: HC stops counting on-order older than k× expected lead time when computing
    orderAmount. **Implementation choice: accounting-only at the HC** (the stale order is not
    cancelled at the DS; if it later ships, the inventory glut shows up honestly as holding cost).
    This avoids editing core delivery logic and avoids conservation bugs from cancelling in-flight
    orders at both ends. Document k (default 3×).
- **(d) Detect-at-onset reroute (optional)** — at onset, step HC split sharply toward the healthy
  DS. No buffering. This is detect-then-REROUTE — explicitly distinct from the earlier
  detect-then-buffer result ("detection captures ~0"), which it does not contradict or inherit.
  Expectation: ≈ an upper bound on how fast (b)/(c) trust dynamics could possibly act.

## Scoring (non-negotiable)

- **System-level cost** (DS_disrupted + DS_healthy + both HCs; holding vs backlog decomposed).
  Never a disrupted-DS-only ledger — rerouting sheds demand to the healthy DS by construction.
- Phase-stratified: pre 60–109 / during 110–157 / post 158–end. Plus whole-episode.
- Panel: system cost (decomposed), fill rate per HC and aggregate, peak backlog (DS_disrupted,
  DS_healthy, system), time-to-recovery AND area-under-backlog (threshold-free), HC-dispersion
  diagnostic (HC1 vs HC2 fill-rate/backlog gap).
- Paired fixed seeds; means ± SE; paired differences vs rung (a).
- Demand configs run separately, never pooled: PRIMARY urgent=0; SECONDARY urgent=20
  (check specifically whether reactive rerouting reduces lost patients).

## Methodology guards

- **Seed discipline:** e.g. seeds 1–10 for tuning rung (c) parameters, seeds 11–30 held out for
  all reported numbers. No parameter chosen on reporting seeds.
- **Verification before trusting results (single seed):** (b) actually changes HC2's split shares
  over the disruption; (c) actually reduces counted stranded on-order; conservation
  demand = served + backlogged (+ lost under urgent=20) holds each period system-wide; rung (a)
  reproduces the known baseline within tolerance; determinism (same seed → same trajectory).
- **No core simulator edits** except: routing-rule selection (already config-driven via
  `HC_ORDER_SPLIT`) and the new split/write-off variants, implemented as a subclass of
  `SimpleHCDecisionMaker` in this folder and registered per-agent. Any unavoidable core change is
  flagged in the design doc as a finding.

## Back-of-envelope to beat (goes in routing_hypothesis.md, refined)

HC2's stuck stream ≈ half its orders × 48 periods ≈ 2,600 units held on the dead chain at backlog
cost ~10/unit/period while they persist → potentially 800k–1,300k, i.e. the same order as the
always-defend buffer lever (−468k). Refinements from the code read: the per-period order cap
(`max(2×demand,120)`) bounds how hard HC2 can catch up; trust-split's incomplete redirection means
rung (b) recovers less than the naive arithmetic; the indirect trust/demand-shift effect is live in
closed loop. The hypothesis doc must state both directions: the effect could rival the buffer
lever, or could be small if backlog mostly reflects the supply cap arithmetic.

## Deliverables (all inside `routing_study/`)

```
routing_study/
├── PLAN.md                    # this file
├── routing_study_design.md    # step 1: documented routing mechanics + on-order lifecycle
├── routing_hypothesis.md      # prior + arithmetic to beat (written BEFORE results)
├── routing_results.md         # per-rung system-level results, both configs, headline fraction
├── routing_forward.md         # implications for the value decomposition + detection claim
├── policies.py                # HC decision-maker variants (rungs b, c, d)
├── run_ladder.py              # rungs × configs × seeds, paired
├── metrics.py                 # phase-stratified system-level panel
├── verify.py                  # sanity + conservation checks
├── make_figures.py            # comparison figures
└── results/
    ├── urgent0/
    └── urgent20/
```

## Order of work

1. `routing_study_design.md` — document mechanics incl. the on-order lifecycle question (read-only).
2. `routing_hypothesis.md` — lock the prior before any results exist.
3. Harness + rung (a); gate: reproduces baseline.
4. `verify.py` checks pass on single seed for (b) and (c).
5. Full ladder, urgent=0 (primary), then urgent=20.
6. Results + forward docs + figures.
