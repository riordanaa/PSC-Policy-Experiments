# H9 — Severity-aware redirect (Part C1): REFUTED, with two instructive failure modes

**Hypothesis.** A reroute whose redirected volume is capped at the surviving chain's
observed headroom makes routing safe at every severity — one robust policy across the
lever-flip map, removing the sat30 routing penalty.

**Method.** Two natural implementations, margins tuned at sat50/d48 + sat30/d48 (seeds 1–10):
1. `HeadroomCappedRerouteHC` — cap at margin × observed recent DELIVERIES per source.
2. `CapacityAwareRerouteHC` — cap at margin × the source's SHARED CAPACITY signal
   (live MN active_lines × line_capacity — the same info-sharing channel as h3b).
Both with the surge-only floor (cap never binds below the source's equal share).

**Results (tuning seeds, urgent0; references: rung-c 2,737k / rung-d 1,861k at sat50;
no-action 5,133k / rung-c 7,657k / disrupted-B4800 buffer 2,417k at sat30):**

| Variant | sat50 best | sat30 best |
|---|---:|---:|
| delivery-cap (m=1.5) | 4,094,416 (+50% vs rung-c) | 7,628,577 (≈ rung-c) |
| capacity-cap (m=1.2) | 3,412,017 (+25% vs rung-c) | 8,975,510 (worse than everything) |

Plus one discarded bug iteration (v1 bootstrap deadlock: cold-start rate 0 → cap 1 unit →
the simulator drops orders ≤1 → zero flow forever; flagged by a margin-invariant 94M cost).

**Why it fails (the useful part):**
1. **Orders are the production signal.** The surviving MN produces in response to queued
   orders (verified: `prod = up_to + backlog − inv − in_production`, capped at capacity).
   Capping orders at observed deliveries throttles the very signal that makes the supplier
   ramp — self-fulfilling under-supply. The capacity-signal variant avoids that trap but
   still under-orders: in this simulator, over-ordering a constrained supplier costs the
   ORDERER nothing (the queue cost lands upstream as MN backlog), so suppressing orders
   forfeits queue position and production stimulus while saving nothing real.
2. **The sat30 routing penalty is a delivery-mix problem, not an order-volume problem.**
   Sharp rerouting under-uses the dead chain's remaining trickle; capping healthy-chain
   ORDERS doesn't re-engage the dead chain's CAPACITY. The lever that actually fixes sat30
   is inventory in the right place (C3: disrupted-located B4800 = 2,417k, −30% vs the
   healthy-located buffer; confirmed reporting seeds).

**Verdict: DON'T-TRY redirect caps (either signal).** "One robust routing policy across the
map" does not exist within this class; the severity-dependence of the routing lever is
irreducible at the demand side. **Robustness lives on the buffer side instead:** C2's
demand-aware sizing (B* = (measured demand − surviving deliverable) × duration) is the
robust knob — at sat50/urgent20 it cuts lost patients to **41 vs 505** at the frozen-grid
optimum (reporting seeds), and its other endpoint (sat30/d48 → B*=4,800) was independently
the measured frozen-grid optimum. Per kill conditions, the 9-cell reporting sweep for the
refuted redirect was NOT run.
