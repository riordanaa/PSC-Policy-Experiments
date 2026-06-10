# H10 — Pre-publication robustness: recurrence, coverage-collapse, shed equity

All numbers reporting seeds 11–30; independent audit 18/18 PASS.

## Recurrence (the check that could have moved the map): THE MAP HOLDS

Two identical events per episode (windows 110–157 & 200–247; for blips 110–114 & 150–154;
capacity fully restores between events — verified two-dip sanity).

| Cell (×2 events) | Winner | vs single-event winner | Cost growth |
|---|---|---|---:|
| slack, long | compound (378,342) | unchanged | ×1.39 (sub-linear: gated rules premium-free) |
| moderate scarcity, long | compound B960 (1,032,864) | unchanged | ×1.35 (buffer REFILLS between events) |
| moderate scarcity, short blips | **no action (142,639)** < routing (203,544) | unchanged — the no-action zone survives | — |
| severe scarcity, long | buffer@disrupted (3,823,226); routing STILL worst (10,145,317 > no-action 8,889,030) | unchanged | — |

**Verdict: no cell changes winner; the compound amortizes BEST under recurrence** (its gated
components cost nothing between events and its buffer refills). The reviewers' concern —
that premium amortization could move buffer-cell boundaries — is resolved in favor of the
published map.

**Refinement to C2 (demand-aware sizing):** size B to the PER-EVENT shortfall, not the
cumulative one — B1920 (total-duration sizing) LOSES to B960 (per-event) at moderate
scarcity ×2 (1,209,728 vs 1,032,864) because the buffer refills between events.

## Coverage-collapse (no-disruption episodes): gated rules are inert; buffers pay in full

| Policy (no disruption, urgent0) | episode PSC profit | vs base stock |
|---|---:|---:|
| base stock (thesis world) | 794,889 | — |
| info-sharing compound (reroute+taper, no buffer) | 790,732 | **−0.5% (inert)** |
| buffer B480 @survivor | 656,848 | −17% |
| DS-seat compound (with standing B480) | 527,072 | **−34%** |

The signal-gated components never fire when nothing happens — zero premium (contrast: the
thesis RL lost 18% in its own no-disruption row). Standing buffers pay their full holding
premium. **Decision rule for the advisor:** the buffer-free compound gives up only 2.5
points of coverage (46.6% vs 49.1% of BS loss removed) and pays ~nothing in normal times —
the better insurance contract unless long disruptions are frequent (recurrence numbers
above quantify exactly when the buffer pays).

## Shed equity (the ethics framing): Pareto on totals, with a localized trough

urgent20, per HC: episode lost patients — trust-routed HC 804→713, captive HC 964→862
(BOTH better under the compound); during-disruption fill rises for both. The honest cost:
the deliberately starved HC's worst 5-period rolling fill deepens from 0.614 (base stock)
to ≈0.50 during the transition before rerouting completes. Framing for deployment: the rule
is Pareto-improving on episode totals with a measurably deeper short trough for the starved
customer; any real-world use should pair it with a service floor.

**Verdicts:** map robust — publish with the recurrence note; C2 formula amended to
per-event sizing; equity paragraph travels with the shed rule wherever it is recommended.
