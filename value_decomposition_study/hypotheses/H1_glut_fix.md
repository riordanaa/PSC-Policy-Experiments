# H1 — Recovery-aware write-off kills the glut

**Hypothesis.** The post-recovery inventory glut (the write-off's known side effect: stale
orders still deliver late while the HC re-orders) can be removed by counting a dead source's
stale pipeline again as soon as that source's delivery rate revives (θ=0.5), keeping the
write-off's backlog savings without the double supply.

**Method.** `RecoveryAwareWriteoffHC` (policies_v2.py) on the compound baseline
(rung-c routing + static-priority allocation). Reporting seeds 11–30, urgent0 + urgent20.
Variant H1b: count dead-source stale pipeline at discount γ=0.5 instead of 0
(`DiscountWriteoffHC`), tuned then reported on seeds 11–30 (urgent0).
Data: `results/slack/*/h1_recovery_writeoff.csv`, `h1b_gamma.csv`. Gates G3/G4 passed.

**Result.**
- H1 (revive-at-recovery): glut UNCHANGED (system post-peak excess 3,033 vs compound's
  2,967; glut area 82.2k vs 80.3k; post holding 121.7k vs 122.0k) and during+post cost
  slightly WORSE (1,082k vs 1,060k, +2%).
- Why it fails (mechanism, visible in the on-order traces): the duplicate orders are placed
  DURING the disruption window, while the source still looks dead. Reviving the pipeline
  count at recovery is too late by construction — the double supply is already committed.
- H1b (γ=0.5 standing discount): 1,044k vs 1,060k on reporting seeds (−1.5%); glut reduced
  only marginally. The accounting dial trades backlog suppression against glut almost
  one-for-one; the entire channel is worth ≈ the glut's holding cost (~25–30k), consistent
  with the earlier residual decomposition.

**Verdict: DON'T-TRY further accounting-side fixes.** The glut is structurally a
double-ordering problem committed mid-window; fixing it properly requires cancelling the
stale order at the DS (a core delivery-logic change — `receive_delivery` raises if a
delivery exceeds the ledger) or an explicit cancellation message, which is a simulator
extension, not a policy. Channel value is small (~25–30k); park it. Going forward: if the
simulator ever gains order cancellation, revisit; otherwise accept the glut as the measured
price of the write-off (which buys ~20× more than it costs).
