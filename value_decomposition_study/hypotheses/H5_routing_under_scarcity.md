# H5 — Routing under scarcity (sat50, d48)

**Hypothesis.** In the saturated regime (MN_healthy also cut to 50%; supply 220/period vs
demand 240/period; gates G5/G6 passed — during-fill 0.875 under rung-c routing), routing
still captures a large share of value but no longer ~all; a residual opens that only
inventory can serve.

**Method.** Routing ladder (a, b, c, d) re-run at (sat50, d48), reporting seeds 11–30, both
configs. Data: `results/sat50/{urgent0,urgent20}/ladder_*.csv`.

**Result (urgent0, dp-cost full / ex-MN-backlog):**

| Rung | dp-cost | ex-MN | vs (a) | peak DS_disrupted / DS_healthy |
|---|---:|---:|---:|---|
| (a) baseline | 3,702,034 | 2,264,927 | — | 4,067 / 139 |
| (b) trust-split | 2,954,643 | 1,773,937 | −20% | 2,907 / 507 |
| (c) sharp + write-off | 2,737,448 | 1,582,143 | −26% | 1,178 / 2,122 |
| (d) oracle reroute | 1,861,007 | 1,124,062 | −50% | 231 / 1,837 |

**urgent20 — the patient-facing lever flip:** lost patients barely move across the entire
ladder — (a) 1,768 → (c) 1,591 → (d) 1,647. Compare slack, where the same ladder cut lost
patients 1,768 → 203. Under genuine scarcity, routing reshuffles WHO waits (the queue
relocates from DS_disrupted to DS_healthy, visible in the peak columns) but cannot create
product. Fill is pinned at ~0.9 (urgent0) / ~0.8 (urgent20) at every rung.

**Verdict.** CONFIRMED. Routing remains the largest single deployable lever on cost (−26%
deployable, −50% with onset knowledge) but its PATIENT value collapses to ≈0 under scarcity.
The residual (1.86M even under oracle routing) is the inventory lever's domain — H6.
This completes the regime boundary: routing dominates when the surviving chain has headroom;
inventory becomes necessary exactly when it doesn't.
