# Understanding Study — Results

Scope decision (2026-06-10): no new regime. All three experiments are within the existing
scenario, on the routing-fixed (rung c) baseline. E1 is new simulation (gated: the new
allocation code path reproduces rung c bit-for-bit under the proportional rule, 60 columns ×
300 periods). E2/E3 are pure analysis of the routing study's per-period logs; E2 cross-checks
against routing_study summary.csv (PASS). Reporting seeds 11–30 throughout. The allocation
family has no tuned parameters (descriptive bound; no seed-split issue).

## E1 — The allocation bound: alive but second-order, with asymmetric risk

During+post system cost on the rung-c baseline (urgent0 / urgent20):

| Rule | urgent0 dp-cost | vs proportional | urgent20 lost patients |
|---|---:|---:|---:|
| **prio_hc1 / prio_hc2 (static strict priority)** | **1,060k** | **−12.4%** | **445** |
| proportional (= rung c) | 1,210k | — | 510 |
| equal | 1,209k | −0.0% | 509 |
| serve_captive | 1,517k | **+25%** | 603 |
| backlog_priority | 1,881k | **+56%** | 795 |

- **Channel value ≈ 10–12% at best** (~150k) — second-order against routing's 67–91%.
- **The best rule is trivial**: strict static priority, and it does not matter WHICH HC you
  prioritize (hc1 ≈ hc2 to within noise — the HCs are symmetric). Total units shipped are
  identical across rules; all differences are closed-loop trust-feedback effects, and what
  wins is *consistency* — always serving one customer fully keeps its trust/delivery loop
  clean rather than splitting failures across both.
- **"Smart" dynamic rules actively hurt**: backlog-priority (+56% cost, fill drops below 1.0,
  +56% lost patients) and serve-captive (+25%) both backfire. Chasing the bigger backlog
  alternates failures across both HCs and keeps both trust loops degraded. The downside of a
  bad allocation policy (~5×) is far larger than the upside of the best one.
- **Fairness caveat:** the 10–12% gain is bought with dispersion — the non-prioritized HC's
  during fill drops (0.957 vs 0.981 under urgent20). Proportional/equal are fairness-neutral.
  If HC fairness is a hard constraint, the honest reading is "the allocation channel has
  ~zero upside and large downside."
- **For the DRL question (dossier Mechanism 3):** the ceiling for learned allocation on this
  baseline is ~10–12% cost / ~13% lost patients — and a learner exploring this space risks
  the −56% region. A two-line static rule captures the entire upside.

## E2 — The rung-c residual (1.21M): mostly upstream bookkeeping + the transient + the glut

During+post decomposition by agent (urgent0, mean over seeds):

| Agent | Total | Dominant component |
|---|---:|---|
| MN_disrupted | 498k (41%) | during backlog 441k — orders queued at the dead factory persist up to 48 periods |
| DS_disrupted | 345k (29%) | during backlog 276k — early-disruption orders + the ~10-period redirection transient + the trust-floor share |
| DS_healthy | 122k | during backlog 88k — the absorption transient |
| HC_trust + HC_equal | 183k | during backlog ~105k (brief service dip) + post holding ~72k |
| MN_healthy | 61k | post holding 20k (carrying the surge) |

- **Nothing here is a during-disruption patient-service problem** — fill is 1.000. The
  residual is queue bookkeeping (MN backlog cost on undeliverable orders), the unavoidable
  ~10-period redirection transient, and recovery-side holding.
- **The glut is real, and rung (c) DOUBLES it vs baseline**: post-disruption system inventory
  peaks at 3,930 vs pre-mean 332 (baseline peak 2,051; oracle-reroute rung d only 1,006).
  Mechanism (visible in E3 panel 3/4): the write-off makes HC_equal re-order from the healthy
  chain while the written-off stale orders STILL deliver late → double supply at recovery.
  Cost: post holding 135k (c) vs 107k (a). It is the price of the write-off and it is ~20×
  smaller than the backlog cost the write-off saves — but a smarter rule (cancel-at-DS, or a
  recovery-aware re-order throttle) could keep the savings without the glut.
- **Modeling caveat worth raising with the advisor**: 41% of the residual is MN-backlog cost —
  whether undeliverable queued orders at a shut factory should accrue cost 10/unit/period is
  an accounting convention of the simulator, not a physical loss. Under a patient-facing
  cost lens the residual is much smaller than 1.21M.

## E3 — Dynamics anatomy (figures: results/figures/anatomy_{hc,ds}_layer.*)

The period-by-period story of the fixed-routing world, all visible in two figures:

1. **Trust** collapses against the dead chain to ~0.55 within ~10 periods (δ′=0.3, EMA floor
   visible — it never reaches 0 because the trickle keeps delivering something) and recovers
   within ~20 periods after the disruption ends.
2. **Order routing** follows trust: HC_equal's orders to the dead chain fall from ~60 to
   ~15/period in ~10 periods (baseline never moves — flat dotted line).
3. **Receipts** follow routing with the pipeline lag; at recovery there is a sharp spike of
   late deliveries from the dead chain — the glut arriving.
4. **The write-off in action**: raw on-order ledger climbs to ~800 while the ordering formula
   counts only ~450 — the gap is the stranded pipeline being ignored, which is what lets
   HC_equal keep ordering from the healthy chain.
5. **Up-to targets**: the HEALTHY chain's target balloons (~900) as its lead time stretches
   under the absorbed surge; the dead chain's target FALLS as demand routes away — the
   opposite of the naive expectation.
6. **Dead-factory queue**: DS_disrupted's during-disruption orders are modest (~20–40/period,
   its demand left with the routing), but they sit at the dead MN for the full window; the
   post-recovery catch-up spike (~400/period) is what feeds the glut.

## What we learned (one paragraph)

In this scenario, once routing is fixed, the system is essentially solved at the
patient-service level: fill is 1.000, and the remaining 1.21M is queue bookkeeping at the
dead factory (41%), the ~10-period redirection transient (~30%), and recovery-side
holding/glut (~20%) — with the glut being an artifact of our own write-off design that a
recovery-aware refinement could remove. The allocation channel — the one DS-level lever left,
and the place a DRL contribution could have hidden (Mechanism 3) — is bounded at ~10–12%
upside, captured entirely by a trivial static-priority rule that trades against fairness,
while plausible-looking dynamic rules (backlog-priority, serve-captive) make things up to 56%
WORSE. There is no meaningful room left for learned policies in this scenario; the remaining
improvements are two small deterministic refinements (recovery-aware write-off / re-order
throttle, and — if fairness permits — static priority allocation).

## Next steps

1. **Recovery-aware write-off refinement** — suppress re-ordering when written-off pipeline is
   about to deliver (or cancel-at-DS): removes the 3,930-peak glut and most of rung-c's post
   holding. Small, deterministic, closes E2's main self-inflicted cost.
2. **Recompute the buffer sweep / clairvoyant ceiling on the rung-c baseline** — still the
   gating step for any value-decomposition claim in a paper.
3. **Severity robustness of the routing result** (short/moderate disruptions, milder cuts) —
   only AFTER the simple scenario is fully written up; introduce it because the writing
   demands generality, not to give tools a job.
4. **For the eventual corrected DRL**: evaluate against rung (c) + static-priority allocation
   (the new compound simple baseline). The honest bar: beat 1.06M during+post (urgent0) /
   445 lost patients (urgent20) without losing fairness.
