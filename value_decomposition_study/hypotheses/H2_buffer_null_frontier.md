# H2 — The buffer null frontier in the slack regime

**Hypothesis.** Per prior evidence, a standing DS buffer buys almost nothing once routing is
fixed (fill already 1.000); at most it shaves part of the ~10-period redirection transient,
at a standing premium.

**Method.** `ShapedDS(buffer_b=B)` on the compound baseline; B ∈ {60,120,240,360,480,600}
at DS_disrupted; B ∈ {120,240} at both DSs. urgent0, reporting seeds 11–30.
Premium = pre-phase system-cost increase vs compound; coverage = during+post reduction.
Data: `results/slack/urgent0/h2_buffer_*.csv`.

**Result — stronger than hypothesized: coverage is NEGATIVE almost everywhere.**

| Variant | Premium | Coverage |
|---|---:|---:|
| B120 both DSs | +11,628 | +797 (≈0) |
| B60 disrupted | +3,324 | −10,193 |
| B120 disrupted | +6,344 | −31,172 |
| B240 disrupted | +12,658 | −83,994 |
| B600 disrupted | +31,207 | −240,740 |

A buffered DS_disrupted orders more from its dead factory (growing the MN queue cost) and
gluts harder at recovery; buffers at both DSs are cost-neutral at best. The null frontier is
DEGENERATE in the slack regime: there is nothing for composed ordering heuristics to beat,
because the buffer itself is strictly dominated by doing nothing.

**Supersession note (important for the paper).** The earlier finding "permanent insurance
captures ~42% of DS-cost" was measured in the BROKEN-routing world. With routing fixed, the
standing buffer's value is zero-to-negative at this severity: the buffer was compensating
for the routing failure, not providing irreplaceable insurance. This is the second major
number (after −468k/−654k) revealed as conditional on the hobbled routing layer.

**Verdict: DON'T-TRY standing buffers (or buffer-anchored compositions) in the slack
regime.** TRY again only under genuine supply scarcity (Phase 2), where stock is the only
source of product and the frontier can be non-degenerate.
