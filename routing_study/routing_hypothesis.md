# Routing Study — Hypothesis (locked before any results)

Written and locked 2026-06-09, BEFORE any ladder run. The numbers below are the prior to beat,
not predictions fitted to outcomes.

## The question

What fraction of DS_disrupted's disruption-period pile-up (~3,800 peak backlog; 1,983 mean
during-phase backlog in the constant-demand baseline) — and of the corresponding system-level
cost — is recoverable by fixing the order-routing rules alone, with no buffering, no
anticipation, and no learning?

## The mechanism we are measuring

Two compounding artifacts, both verified in code (see routing_study_design.md):

1. **Equal-split lock-in:** HC_equal sends 50% of every order to DS_disrupted by rule,
   throughout the disruption, regardless of delivery failure (decision_maker.py:158-165).
2. **Stranded-order suppression:** undelivered orders sit in HC on-order indefinitely
   (no timeout), and on-order is subtracted from the total order before splitting
   (decision_maker.py:153) — so pipeline stuck at the dead chain also suppresses ordering
   from the healthy chain.

## Back-of-envelope — A CEILING, NOT A PREDICTION

Naive arithmetic: HC_equal routes ~55/period to DS_disrupted × 48 periods ≈ 2,600 units held on
the dead chain; persisting 30–50 periods at backlog cost 10/unit/period → roughly 0.8M–1.3M of
backlog cost attributable to the routing rule. That would rival the always-defend buffer lever
(−468k) from the earlier value decomposition.

Reasons the realized number is likely SMALLER (verified in code, stated up front):

- **Order cap:** per-period HC orders are capped at `max(2×demand, 120)` ≈ 240
  (decision_maker.py:155-156) — HC_equal cannot express its whole backlog as orders at once.
- **Incomplete trust redirection:** trust converges to the EMA of the delivery rate, and the
  dead chain still trickles ~20/period, so rung (b) keeps sending ~15–20% of orders there.
  Full redirection requires the sharper rule of rung (c).
- **Half of HC_equal's orders already go to DS_healthy**, which mostly fills them — the
  shortfall is the half stuck on the dead chain net of what the healthy chain absorbs through
  the backlog term in the order formula.
- **DS_healthy must also serve HC_trust's redirected demand** — its own up-to dynamics and its
  MN's capacity (400/period, normally loaded ~120) leave headroom, but pipeline latency
  (~4–5 periods) delays absorption.

Prior evidence the direction is not even guaranteed: Doroudi et al. (2020) — same group, same
topology — found non-monotone effects: trust-sensitive buyers can be disadvantaged in certain
disruption regimes due to supplier preference for stable demand; this is prior evidence that
flipping HC2 to trust-split may not simply help.

## Pre-registered readings of the outcome

- **Large recovery** (rungs b–d recover a substantial fraction of the baseline system-cost gap,
  comparable to the buffer lever): the project reframes to a three-lever decomposition
  (buffering + routing flexibility + detection); the earlier −468k/−654k decomposition is
  conditional on a frozen routing layer and must be recomputed with routing freed; the earlier
  detection-null claim narrows to "detect-then-buffer captures ~0" (detect-then-reroute is
  rung (d), measured here).
- **Small recovery** (a few percent): the "pile-up is genuinely unavoidable; structure (a static
  buffer) captures the achievable value" framing stands, now with the routing-artifact
  objection measured and closed rather than assumed away.
- Either way the result is informative; "did not recover within horizon" is reported honestly
  where it occurs.

## Pre-registered protocol (locked)

- **Seeds — FIXED before any run:** tuning seeds = 1–10 (ONLY for choosing rung-c parameters
  δ′ ∈ {0.3, 0.5}, sharpness p ∈ {2, 4}, write-off k ∈ {2, 3, 5}); reporting seeds = 11–30
  (20 seeds; every reported number). No parameter is chosen using reporting seeds.
- **Scoring:** system-level cost (all six agents, holding vs backlog decomposed), never a
  DS_disrupted-only ledger. Phase-stratified: pre 60–109 / during 110–157 / post 158–299,
  plus whole-episode. Paired differences vs rung (a), mean ± SE over reporting seeds.
- **Panel:** system cost (decomposed), fill rate (per HC and aggregate), peak backlog
  (DS_disrupted, DS_healthy, system), time-to-recovery (110% of pre-disruption mean) AND
  area-under-backlog (threshold-free), HC dispersion (HC_trust vs HC_equal fill/backlog gap),
  lost urgent patients (urgent=20 config only).
- **Demand configs, never pooled:** PRIMARY non-urgent N(120,5), urgent 0. SECONDARY same
  non-urgent, urgent = 20 (constant). The thesis-comparable config is urgent=0.
- **The single pre-registered confirmatory comparison:** rung (b) vs rung (a) on
  during+post system cost (urgent=0, reporting seeds, paired). Everything else is descriptive.
