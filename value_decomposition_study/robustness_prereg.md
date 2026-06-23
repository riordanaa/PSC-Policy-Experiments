# Pre-registration — robustness sweeps (capacity × δ), written BEFORE running

Purpose: lock expected outcomes (including the boring branches) before seeing results, so we
report what we find rather than what we hoped. Sweeps stress two findings: **(A)** rerouting
fixes most of the disruption; **(B)** the disrupted distributor DS1 benefits from shed.

Anchor: MN2 capacity = 400/period (40 lines), δ=0.1, slack regime — must reproduce the existing
`a.csv` (baseline) and `dsseat_alloc_shed_timed_rep.csv` (shed) bit-exactly. Reporting seeds 11–30.

## Capacity sweep (MN2 lines {40, 24, 18, 14, 12} = {400, 240, 180, 140, 120}/period), δ=0.1

- **Rerouting-fix (A):** expected to DEGRADE as MN2 capacity falls. At 400, reroute restores
  near-full fill (current finding). As MN2 drops toward ~180 (can't absorb HC1's reroute surge
  on top of its own ~120), the healthy chain congests, system fill during/post drops, and the
  lever should flip — inventory/buffer becomes the better lever than routing. Predict a flip
  somewhere in {240, 180, 140}.
- **Shed-helps-DS1 (B):** expected to SHRINK as MN2 congests. Shed's benefit is DS1 avoiding
  backlog by pushing HC1 to DS2; if DS2/MN2 can't serve HC1, HC1's orders bounce back or it
  oscillates, eroding the clean backlog saving. Predict the +262k DS1 gain shrinks monotonically;
  possible sign flip at the lowest capacity (12 lines) if HC1 can't be offloaded at all.
- **HC1 return:** expected to still return at high capacity; at low capacity HC1 may fail to
  settle (the healthy chain can't satisfy it either → Doroudi-style oscillation even at δ=0.1).
- **Boring branch (must report if seen):** rerouting-fix and shed-benefit barely move across the
  whole sweep → MN2 capacity is NOT load-bearing in this simulator, and Ergun's external-validity
  concern doesn't bite here (would itself be an important, honest result — capacity isn't the
  knob, contrary to the real-world intuition).
- **Floor:** at 12 lines (120/period) MN2 just covers its own nominal; if the `none`-regime
  pre-phase fill < 0.99, that cell is a floor breach (MN2 can't serve baseline) → excluded.

## δ sweep (δ {0.05, 0.1, 0.2, 0.35, 0.5}), MN2 capacity = 400

- **HC1 oscillation:** expected to INCREASE with δ (Doroudi S2/S3: higher δ → sharper trust
  swings). At δ=0.5 expect the largest order-share oscillation and the slowest/least-clean return.
- **HC1 return:** at low δ (0.05, 0.1) clean return to 0.500. At high δ (0.35, 0.5) HC1 may
  oscillate and not settle cleanly, or settle slower (Doroudi's "trust HC ends up second priority"
  — though with abundant MN2 capacity here, the collapse may be muted vs Doroudi).
- **Shed-helps-DS1 (B):** uncertain direction. Higher δ makes HC1 flee faster/harder during the
  disruption → DS1 sheds more backlog sooner → shed benefit could GROW; but more oscillation could
  add churn cost. Predict shed benefit roughly stable-to-growing in δ, but watch for churn.
- **Boring branch (must report if seen):** the picture is δ-invariant across 0.05–0.5 → our
  δ=0.1 results are robust and NOT a low-δ artifact (a clean robustness statement; would mean the
  Doroudi instability needs more than high δ — e.g., ToM or constrained capacity — to appear).
- **Cross-check with capacity:** the Doroudi collapse most likely needs BOTH high δ AND low MN2
  capacity (oscillation + a healthy chain that can't absorb). Neither sweep alone may trigger it.

## rung-b (both HCs bytrust — natural 2-trust dynamics, existing data)

- **Dispersion (fill_hc1 − fill_hc2):** expected to SHRINK vs rung-a (no captive HC2 getting
  preferential leftover; both HCs flee symmetrically).
- **DS1 outcome:** with no captive anchor, DS1 (disrupted) may lose BOTH customers during the
  disruption → expect DS1 during-phase worse than rung-a, but also less backlog (both fled).
- **Boring branch:** rung-b ≈ rung-a → the captive/equal HC doesn't materially change the
  disrupted distributor's story (the second customer being trust-based vs equal is second-order).

## 2D interaction grid (delta x MN2-capacity) — pre-registered before running

Grid: MN2 lines {40,24,18,14} = {400,240,180,140} x delta {0.10,0.20,0.35,0.50}, baseline+shed,
urgent0. Question: does the §1 capacity flip boundary move with delta, and does the Doroudi
switching-collapse appear in the high-delta x low-capacity corner that neither 1D sweep reached?
- **Boundary movement (predicted):** higher delta -> HC1 flees harder/sooner -> more dumped on
  the healthy chain -> shed turns system-harmful at HIGHER capacity. So the system-Delta=0
  contour should shift up (toward 240/400) as delta rises. Compounding of the two stresses.
- **Doroudi collapse (predicted, bounded NEGATIVE likely):** HC1 may oscillate more in the
  corner, but the FULL collapse (HC1 fails to return / permanent second-priority) probably will
  NOT appear, because our allocation rules are fixed — the disrupted DS cannot strategically
  deprioritize the oscillating customer the way Doroudi's ToM agent does. If HC1 still returns
  to ~0.5 everywhere, that BOUNDS the claim: the collapse needs ToM, not just sharp-trust +
  scarce-capacity. If HC1 fails to return in the corner, the instability is structural (no ToM
  needed) — the stronger, more surprising result.
- **Boring branch:** the boundary is delta-invariant (flip stays at ~180-240 for all delta) ->
  capacity alone governs, trust sensitivity is second-order even in combination.

## Decision rules
- Report the flip point (capacity and/or δ) where A or B reverses, with bracketing cells.
- If a boring branch holds, state it plainly — it is a result, not a failure.
- Every reported number traceable to a `results/robustness/**` CSV; anchor gate must pass first.
