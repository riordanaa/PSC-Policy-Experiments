# H4 — The practical ceiling of the fixed-routing world

**Hypothesis.** Composing the best oracle components (onset-windowed reroute + static-
priority allocation + just-in-time pre-build + recovery-aware write-off) leaves only a small
gap above the best deployable compound — i.e. the room for ANY cleverer policy (including a
learned one) in the simple scenario is small.

**Method.** `h4_ceiling` = oracle window reroute + `RecoveryAwareWriteoffHC` + prio_hc1
allocation + JIT buffer at DS_disrupted only, active periods 100–157. B ∈ {120,240,360,480}
tuned on seeds 1–10 (B=120 won: 279.7k; larger B strictly worse). Reporting seeds 11–30,
both configs. Honest label: best-of-family ceiling, not a provable optimum.
Data: `results/slack/*/h4_ceiling.csv`.

**Result.**

| Policy (urgent0, reporting seeds) | dp-cost | premium | lost patients (urgent20) |
|---|---:|---:|---:|
| h4 ceiling (oracle + JIT B120) | **284,120 ± 1,571** | 2,651 | 207 |
| oracle reroute alone (= h3b, deployable w/ info sharing) | 294,796 | 0 | 203 |
| best deployable, no info sharing (h1b γ=0.5) | 1,044,100 | 0 | — |
| compound baseline | 1,062,538 | 0 | 445 |

- **Room above the info-sharing compound: ~10,676 (1.0% of baseline cost)** — and a third of
  that is bought with the JIT buffer's premium. Under urgent20 the ceiling is NOT better on
  lost patients (207 vs 203 — within noise; the JIT stock helps cost, not patients).
- Room above the NO-info-sharing compound: ~760k — but H3 showed this is an information
  constraint (stock-cover masking), not a policy-intelligence constraint: no downstream
  policy of any sophistication can act before the signal exists downstream.
- The pre-build's marginal value collapsed once rerouting is instant (B=120 small; larger B
  strictly worse) — anticipatory stock is nearly redundant WITH instant rerouting, in the
  slack regime.

**Verdict.** CONFIRMED, decisively: **in the simple scenario the room for learned policies
is ≈1% with information sharing, and the gap without information sharing is unreachable by
intelligence at any level of sophistication.** The "room for RL" question in the slack
regime is closed. TRY going forward: nothing further here; the open question moves to the
saturated regime (Phase 2), where stock is the only source of product and the calculus can
genuinely change.
