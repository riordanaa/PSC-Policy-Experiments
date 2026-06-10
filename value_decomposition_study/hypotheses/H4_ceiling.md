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

**Verdict.** CONFIRMED at the time — **CORRECTED by the A1 verification (2026-06-11):**
this ceiling was NOT a true superset: its JIT buffer sat at the DISRUPTED DS (the location
later shown worthless). The properly-constructed superset (deployable compound + JIT buffer
at the HEALTHY DS) reaches **180,137** (tuning) — foresight DOES add value when the buffer
is correctly located: ~36k is deployable at zero lead (signal-triggered onset buffer),
~54k (~5% of baseline cost) is true pre-onset foresight. Reporting runs:
`a1_superset_B240_lead10` / `_zerolead` (seeds 11–30).
**Bounded restatement (A2):** "room for learned policies ≈ 0" means: no rule in the
enumerated family {buffer (size × location × timing), taper, throttle, SS-freeze,
reroute (trigger × share), allocation (12 rules)} leaves measurable residual room above the
best composition; a learned policy would need a mechanism none of these expresses, and we
identify no such candidate. This bounds the FAMILY, not all possible policies — and A1
itself demonstrates why the distinction matters (one mis-located lever hid ~90k).
