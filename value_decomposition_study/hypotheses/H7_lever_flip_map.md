# H7 — The severity x duration lever-flip map

**Hypothesis.** There is a boundary where the dominant lever flips routing → buffering.

**Method.** Frozen grid: severity {sat70, sat50, sat30} x duration {5, 17, 48}; per cell:
ladder rungs a/c/d + buffer-at-healthy curve on the frozen per-cell B grid; reporting seeds,
urgent0. Buffer curves reported whole (no per-cell selection). Data:
`results/{regime}[_d{dur}]/urgent0/`.

**Result — TWO boundaries, not one:**

| | d=5 | d=17 | d=48 |
|---|---|---|---|
| **sat70** (no scarcity) | **no action** (a 110k < c 156k < d 323k) | routing (d 309k) | routing (d 333k, fill 1.0) |
| **sat50** (mild scarcity) | **no action** (a 110k) | mixed: buffer edges out (B510 484k ~ c 521k; d WORSE 536k) | **compound** (767k, fill 0.990; parts ≥1.9M) |
| **sat30** (severe) | **no action** (a 110k) | buffer modest (B850 641k; routing ~neutral: a 678k ≈ c 680k; d HARMFUL 1,170k) | **buffer only** (B4800 3,466k, fill 1.0); routing NEGATIVE (c 7,657k > a 5,133k) |

1. **The no-action zone (duration boundary).** For disruptions shorter than the system's
   stock-cover window (~6 periods: DS inventory + pipeline), EVERY response is pure churn —
   the oracle reroute is the worst overreaction (3x the cost of doing nothing). The same
   masking that blinds downstream detectors (H3) here PROTECTS the do-nothing policy.
2. **The severity boundary.** Routing dominates while the surviving chain has headroom
   (sat70). As headroom shrinks the compound takes over (sat50/d48). When the surviving
   chain is itself inadequate (sat30), routing flips NEGATIVE — sharp redirection overloads
   a 120/period chain with 240/period of demand and strands the dead chain's trickle —
   at d48 rung-c routing is the WORST policy measured (7,657k vs do-nothing 5,133k).
   Inventory becomes the only lever (B4800: fill 1.000, −32%).
3. Dual accounting does not change any verdict ordering in the map (ex-MN columns in
   `analyze_phase2 --what h7` output); it shrinks magnitudes only.

**Honest caveats.** The map is urgent0 (cost lens); the primary cell has both configs and
shows the patient story separately (H5/H6). Rung-c's sharpness (trust^4, δ'=0.3) was tuned
in the SLACK regime — a gentler redirect would presumably hurt less at sat30, so "routing
flips negative" is a statement about THIS routing rule, not all routing; the honest general
statement is "routing's value collapses and over-redirection actively harms."

**Verdict.** CONFIRMED with an extra boundary not in the hypothesis: the dominant lever is
**nothing → routing → routing+buffer → buffer-only** as duration crosses the stock-cover
window and severity crosses the surviving chain's headroom. This is the paper's central
figure. DON'T-TRY: responding to sub-stock-cover disruptions; sharp redirection under
severe scarcity. TRY going forward: a severity-aware redirect (cap rerouted volume at the
surviving chain's observed headroom) — the one new policy idea this map motivates; it is a
NEW POLICY CLASS, so per protocol it goes to NEXT_PLAN.md for user review, not executed now.
