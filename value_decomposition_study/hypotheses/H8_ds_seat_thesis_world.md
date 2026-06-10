# H8 — The DS-seat hypothesis test in the thesis world (rung-a routing)

**Hypothesis (the user's original):** simple distributor-seat rules (ordering + allocation —
the levers the thesis DRL actually controls) roughly match the RL and beat base stock.
Thesis claim to compare against (Table 3.9, long disruption): GRU-A2C removed ~89% of base
stock's cumulative-PSC-profit loss (−3,738 → −397).

**Method.** Full-grid ladder over the DS's complete decision space (ordering: standing /
state-elevated / taper / prebook / smooth / oo-discount; allocation: shed pair /
smoothed-backlog / fill-equalize / smoothed-captive-gated / static priority), rung-a world
(as-shipped HC layer, δ=0.1), headline = whole-episode cumulative PSC profit with
share-of-BS-loss-removed. Screen seeds 1–10, reporting 11–30, both demand configs. Gates:
dsseat-knobs-off ≡ rung-a bit-exact (library AND CLI paths); refactor-inertness (G8).
**Incident:** the first screen was contaminated by CLI-default knobs (throttle silently on,
default prio allocation, unwired MN signal) — caught via bit-identical rows, all results
discarded, CLI-path gate added, clean rerun. See STATUS 2026-06-11.

## Results (reporting seeds 11–30)

| Policy (thesis world) | PSC profit u0 | share of BS loss removed | fill | lost (u20) |
|---|---:|---:|---:|---:|
| **shed × taper × standing-B480** | **−1,464,012** | **49.1%** (50.7% u20: shed×taper) | 0.858 | 1,575 (−11%) |
| shed × taper | −1,537,240 | 46.6% | 0.852 | 1,710 (−3%) |
| taper alone | −2,161,038* | 24.9% | 0.807 | **1,934 (+9% — WORSE)** |
| shed alone | −2,247,795* | 21.8% | 0.851 | 1,632 (−8%) |
| standing B480 alone | −2,727,886* | 5.2% | 0.833 | — |
| BASE STOCK (rung-a) | −2,876,208 | 0 | 0.808 | 1,768 |

\* screen values (seeds 1–10); finalists confirmed on 11–30 (differences < 1%).

**Mechanism findings:**
- **Demand-shaping is REAL (Mechanism 3 confirmed where it was born):** shed (serve the
  captive HC while your MN is down) improves BOTH HCs (fill 0.923/0.780 vs 0.898/0.717 —
  HC1 leaves faster and is better served by the healthy chain; HC2 gets the trickle), wins
  under BOTH accounting conventions, and does NOT lose patients (u20: −8%). The control
  proves direction matters: shed_inverse = −14.3% (worse than doing nothing). No
  demand-dumping (per-HC guard passed).
- **Taper is accounting-sensitive and patient-negative alone:** +24.9% on the thesis profit
  metric but WORSE ex-MN-backlog, and +9% lost patients under urgent20. Its thesis-metric
  gain is dead-factory bookkeeping; in the compound, shed offsets its patient cost.
- **State-elevated base stock is DEAD, with the mechanism read off the trajectories
  (elevated-climb check):** during the disruption inventory cannot climb (4 units vs BS's 3
  — the factory is dead); elevation operates only in the post-recovery dwell window and its
  during-window effect is pure queue cost. Only the STANDING buffer pre-positions
  (pre-inventory 546 → drawn to 67 during = real coverage, +5%). The thesis-pattern
  candidate ("the RL is doing state-dependent base stock") is excluded for the DURING
  window by supply physics; only its standing form has value.
- Prebook, oo-discount, smoothing: zero-to-strongly-negative. Smoothed allocation variants
  dilute shed rather than improving it (sharp-but-GATED beats smoothed here — gating, not
  smoothing, is what keeps the trust loop happy in this world).

## Verdict on the hypothesis

**Simple DS-seat rules beat base stock decisively (≈49–51% of its loss removed, better fill,
fewer lost patients) — but reach only ~HALF of the thesis RL's claimed 89%.** Pre-registered
branches for the gap: (ii) the RL exploits something beyond this family (it would have to be
finer-grained dynamic allocation/ordering — no candidate mechanism identified in our
enumeration), and/or (iii) baseline non-comparability — the thesis Table 3.9 baseline/
evaluation may differ from ours (UNRESOLVED; user is requesting the exact config from the
thesis author; recall also that our own corrected-pipeline DRL run LOST to base stock, so
Table 3.9 itself is unreplicated). A 49% capture with a 3-parameter rule, against an
89% claim from an unreplicated table, is consistent with the user's hypothesis in spirit;
the remaining factor-of-two is attributable to either branch and cannot be split without
the author's config.

**TRY going forward:** shed×taper×standing as the named DS-seat compound ("serve the
captive, stop ordering from the dead, keep a standing buffer"); resolve branch (iii).
**DON'T-TRY:** state-elevated ordering (supply physics), prebook, oo-discount, smoothed
allocation in this world, taper WITHOUT shed under urgent demand (patient cost).
