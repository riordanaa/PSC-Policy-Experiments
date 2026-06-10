# H6 — The premium-coverage frontier at the primary cell (sat50, d48)

**Hypothesis.** Under genuine scarcity a real frontier exists: buffers buy coverage,
ordering shapers shape its cost, allocation matters. Confirmatory test: at matched premium,
does any composition dominate the buffer-only curve?

**Method.** Screen on tuning seeds 1–10 (frozen grids); survivors composed; curves on
reporting seeds 11–30. Both baselines carried. Data: `results/sat50/*/`.

**Screen verdicts (tuning seeds, urgent0):**
- KEPT: standing buffer AT DS_HEALTHY (location ordering healthy >> both >> disrupted —
  disrupted-located buffers feed the dead chain and are near-worthless);
  upstream-signal reroute; MN-down taper (as part of the compound).
- KILLED: taper/throttle/SS-freeze alone (3.34–3.37M ≈ do-nothing; ordering policy cannot
  create supply); ALL allocation variants — including static priority, which FLIPS HARMFUL
  under scarcity (3,362k vs proportional 2,737k): starving one HC at the queue-bound healthy
  DS collapses its trust in the healthy chain and routes its orders toward the dead one.
  (Third independent regime-dependence of the allocation channel; the dual-baseline
  amendment exists for exactly this.)

**Frontier (reporting seeds, urgent0; premium = pre-cost − 17.0k baseline):**

| Policy | Premium | dp-cost | vs baseline (3,702k) | fill (exact) |
|---|---:|---:|---:|---:|
| **compound: buffer-healthy B960 + reroute + taper** | **49k** | **766,830** | **−79%** | **0.990** |
| compound B1440 | 74k | 831,733 | −78% | 1.000 (0.9999) |
| oracle reroute alone (rung d) | 0 | 1,861,007 | −50% | ~0.90 |
| buffer-healthy B1440 alone | 74k | 1,957,174 | −47% | 0.989 |
| reroute + taper (no buffer) | 0 | 2,136,738 | −42% | ~0.90 |
| trust routing alone (rung c) | 0 | 2,737,448 | −26% | ~0.88 |

**Confirmatory test: PASS.** At matched premium (~74k), the composition (831,733 at B1440)
dominates the buffer-only curve (1,957,174) by a factor of ~2.4 — and the cheaper B960
compound dominates everything measured at ANY premium. Strong super-additivity: the buffer
covers the physical shortfall while the reroute aims demand at the buffered chain from
period one; the parts alone sit at ~0.88–0.99 fill, the B1440 compound reaches 1.000.

**Audit correction (2026-06-11):** an earlier draft of this card claimed fill 1.000 for the
B960 compound and the B1440 buffer — a display-rounding transcription error (tables rounded
to 1 decimal) caught by the independent Phase-2 audit (claim 4). Exact values above; cost
and premium claims verified unchanged (11/12 PASS, the 12th being this fill figure).

**urgent20 (reporting seeds) — the patient axis and a severity nuance:**

| Policy | dp-cost | lost patients | vs neutral baseline (1,591) |
|---|---:|---:|---:|
| compound B1440 | 1,865,391 | **505** | **−68%** |
| compound B960 | 2,321,123 | 704 | −56% |
| buffer-only B1440 | 3,374,578 | 776 | −51% |
| neutral baseline (ladder c) | 3,288,186 | 1,591 | — |
| reroute+taper, NO buffer | 5,119,037 | 1,063 | cost +56% (!) |

Two honest nuances: (i) under urgent20 total demand is 280/period vs supply 220 — deeper
effective scarcity — so the LARGER buffer wins (B1440 > B960; the frozen grid was scaled to
urgent0 demand; noted, not re-tuned); (ii) reroute WITHOUT a buffer flips cost-negative here
(5.1M vs 3.3M baseline) — the same overload mechanism as sat30 — while still reducing lost
patients (1,063 vs 1,591). The composition is dominant on BOTH axes in BOTH configs.

**Verdict.** CONFIRMED. The frontier is real and is owned by one composition: routing
flexibility + correctly-LOCATED insurance + (convention-i) taper. Buffer LOCATION is a
first-order decision — wrong location forfeits nearly all value. The reroute component's
SIGN depends on effective scarcity depth (helpful at mild, harmful alone at deep — the
compound's buffer is what keeps it safe). The space is SIMPLE: screen-and-compose closed the
gap; per the plan's VNS rule (tool of last resort, only if a visible gap remains), VNS IS
NOT JUSTIFIED — there is no residual gap for it to search.
