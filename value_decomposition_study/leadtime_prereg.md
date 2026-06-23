# Pre-registration — lead-time × capacity sweep (written BEFORE running)

Locks expectations before results. Ergun's #1 ask: re-run the capacity sweep + per-phase cost
breakdown across lead times; she predicts larger, *nonlinear* effects (bigger during-disruption
backlog, worse recovery glut) as lead time grows.

**Grid:** PHYSICAL_LEAD_TIME = AGENT_LEAD_TIME ∈ {2,3,4,6,8} × MN2 capacity {400,240,180,140,120}
× {baseline, shed}, urgent0 (+ urgent20 at cap {400,180} for the lost-patient component).
Disruption fixed at 95% / 48 periods. Reporting seeds 11–30. Anchor LT=2 must reproduce the
existing cap_sweep bit-exactly.

## Predictions
1. **During-disruption backlog grows with lead time, plausibly nonlinearly.** A longer pipeline
   means more orders in flight that can't be filled while the factory is down → larger DS1 and
   system backlog during 110–157.
2. **Recovery glut grows with lead time.** When supply resumes, a longer pipeline delivers a
   bigger delayed refill spike → larger DS1 inventory overshoot in recovery (the metric we
   defined: inventory area over nominal in [disruption-end, end+20]).
3. **The capacity-flip threshold moves UP (shed turns harmful at higher MN2 capacity) as LT
   grows.** A longer pipeline makes the healthy chain slower to absorb the rerouted load, so it
   saturates at a higher nominal capacity — the ~180–240 flip (at LT=2) should shift toward
   higher capacity at LT=4,6,8.
4. **The qualitative misaligned-incentive story survives:** DS1 still gains from shed (it still
   sheds its own backlog penalty), system still flips negative below the threshold — only the
   threshold location moves.
5. **Floor risk:** longer lead time may breach the capacity floor earlier (MN2 can't serve even
   baseline when the pipeline is long), so the lowest-capacity cells at high LT may be confounded
   — flag via the no-disruption floor guard.

## Boring branches (must report if seen)
- Costs scale ~linearly (not nonlinearly) with lead time → Ergun's nonlinearity prediction not
  borne out; lead time is a smooth, second-order modifier.
- The flip threshold barely moves with lead time → capacity governs the flip largely independent
  of lead time, and Phase-2 severity can be tested at a single representative lead time.

## Decision rules
- Report the flip threshold and the during-backlog / glut as functions of lead time; state
  whether the growth is nonlinear (super-linear) or linear.
- After seeing results, CROP the lead-time and capacity ranges to the informative window
  (broad-then-crop) and decide the Phase-2 severity design (breadth; cross with LT or not).
- Every reported number traceable to a results/robustness/leadtime/** CSV; LT=2 gate first.
