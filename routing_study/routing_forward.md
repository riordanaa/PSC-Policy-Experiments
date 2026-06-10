# Routing Study — Implications (forward doc)

The pre-registered "large recovery" fork applies, decisively. Consequences, in order of
importance:

## 1. The earlier value decomposition is conditional and must be recomputed

The decomposition (base 1,332k → −468k "defend at all" → −654k "timing, unreachable by
detection" → ceiling 210k) was computed with the routing layer FROZEN in its hobbled state
(equal-split + no write-off + δ=0.1). This study shows the routing layer alone moves
during+post system cost by −26% to −91%. Both the buffer lever's value and the "value of
timing" must be re-measured ON TOP OF a routing-fixed baseline (rung c). Plausibly much of
what looked like "anticipation value" was actually "the routing layer is broken" value —
the clairvoyant pre-build partially compensated for routing, not just for the supply cap.

## 2. The detection claim narrows exactly as pre-registered

"Detection captures ~0" was measured with detect-then-BUFFER (buffering a supply-capped chain
post-onset is futile, so the result was real but response-specific). Detect-then-REROUTE
captures the difference between (c) and (d): ~0.88M of during+post cost (−24 points) and
~54% of rung-c's remaining lost patients (510 → 236). Detection has post-onset value when the
response is demand-side. The anticipation impossibility (nothing observable before onset;
build-time deadline before onset) stands untouched — but it now bounds a much smaller residual,
because most of the value never required anticipation in the first place.

## 3. The project framing: three-lever decomposition on a routing-fixed baseline

The constructive reframing is now empirically grounded: under sudden, precursor-free
disruptions, STRUCTURE captures nearly all achievable value —
- **routing flexibility** (deployable, no detection): −67% during+post cost, −71% lost patients,
- **detection + routing response** (deployable with an onset detector): −91% / −87%,
- **buffering**: to be re-measured on the rung-c baseline (its remaining headroom is the
  rung-c residual: ~1.21M during+post, of which rung d shows ~0.88M is timing-of-rerouting),
- **learning/RL**: bounded by whatever residual remains after the above. This is the bounding-
  paper structure: "the room available to RL is at most Y, and two-line rules occupy most of it."

## 4. Concrete next experiments (deterministic, all unblocked)

1. **Re-run the clairvoyant ceiling and buffer sweep on the rung-c baseline** — recompute the
   value decomposition with routing freed. This is the single most important follow-up; it
   replaces the −468k/−654k numbers in any paper draft.
2. **Real detector for rung (d)** — replace the oracle with the delivery-shortfall detector
   from the earlier detection study; measure how much of the c→d gap a few periods of
   detection latency costs. (Expected: small — the (c) trajectory already reaches the
   redirected state ~10 periods in.)
3. **Buffer × routing interaction** — small grid: {no buffer, always-defend buffer} ×
   {rung a, rung c}. Tests whether buffering is still worth anything once routing is fixed
   (hypothesis: much less — fill rate is already 1.000 under (c)).
4. **Severity/duration robustness** — rerun the ladder at short (110–115) and moderate
   (110–127) disruptions and at 50%/80% capacity cuts, so the frontier shape isn't a
   one-config artifact. Also: a severity where MN_healthy CANNOT absorb everything
   (e.g. both-HC demand > healthy capacity) — that is where buffering should re-emerge.
5. **Allocation channel (dossier Mechanism 3)** — with routing fixed, measure whether the
   disrupted DS's allocation split between HCs still matters (serve-captive hypothesis).

## 5. What this does and does not say about the DRL

Does not say: that the thesis DRL exploited the routing artifact (the DRL controls DS
ordering/allocation, not HC routing — HC rules were identical across DRL and base-stock
comparisons, so the thesis comparison was internally fair).
Does say: the ENVIRONMENT in which both were evaluated had most of its achievable value locked
behind rules neither policy controlled. Any "resilience" narrative for either policy is about
the small residual, not the big number. And the demand-side lever the DRL could in principle
reach (its HC allocation action) is exactly the channel worth probing when the corrected DRL
arrives.

## 6. Codebase flags raised by this study

- `NormalDistPatientModel.__init__` reseeds the global RNG (patient_model.py:28) — any
  multi-seed result using the normal demand model was a single demand path. Fix before any
  future stochastic experiments.
- `config.HC_TRUST_DELTA` is dead (agent.py:581 hard-codes δ=0.1).
- HC on-order has no aging/timeout; combined with on-order subtraction this is the
  stranded-order suppression mechanism. The accounting-only write-off (rung c) is a
  two-line deployable fix.
