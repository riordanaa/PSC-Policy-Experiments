# H3 / H3b — Detect-then-reroute: downstream signal vs shared upstream signal

**Hypothesis (H3).** Most of the c→d gap (~0.9M; oracle onset reroute) is deployable,
because onset should be detectable at near-zero lag from delivery shortfall.

**Method.** `DetectRerouteHC`: source flagged DOWN after w consecutive periods of on-time
delivery rate < 0.5; split steps to 0.1 while down. w∈{2,3} tuned on seeds 1–10 (w=2 won;
zero pre-onset false positives in both). Reporting seeds 11–30, both configs.
Same-stack oracle reference (`d_oracle`) run for clean attribution.
Data: `results/slack/*/h3_detect_reroute.csv`, `d_oracle*.csv`.

**Result (H3): REFUTED — and the failure is informative.**
- Same stack, reporting seeds urgent0: oracle window = 294,796; delivery-rate detector =
  1,238,875. The ~6-period detection latency carries ~944k — essentially the whole gap.
- Mechanism (verified in split-share traces): the disrupted DS serves from its own stock for
  the first ~5–6 periods, so its delivery rate stays healthy exactly while the pile-up
  begins. Any downstream delivery-statistics detector is structurally blind during the
  decisive window. The trust EMA is itself such a detector — which is why the explicit
  detector cannot beat plain rung-c trust dynamics (it is in fact WORSE: 1,239k vs 1,063k,
  because its hard 0.1 step also overrides the gentler trust-based split and reverts late).
- The detector did NOT oscillate (held DOWN through the window; clean trigger at ~116-117).
  The failure is latency, not stability.

**Hypothesis (H3b).** The masking is an information problem, not a detection problem: the
upstream MN's machine state changes AT onset and is exactly what the thesis's full
info-sharing scenario shares. A reroute triggered on that shared signal should approach the
oracle.

**Result (H3b): CONFIRMED — exactly.** `UpstreamSignalRerouteHC` (flag a source while its
feeding MN is below 50% of nominal lines; wiring injected post-build) reproduces the oracle
trajectory IDENTICALLY on reporting seeds (dp-cost 294,796 = oracle's 294,796; every panel
column equal; urgent20: 353,413 and lost patients 203 vs oracle's 203). The signal fires at
onset; latency zero.

**Verdicts.**
- DON'T-TRY: downstream delivery-statistics detection (any threshold/window) — structurally
  blind for ~6 periods; strictly dominated by the built-in trust mechanism.
- TRY (established, promote to the compound policy): upstream-signal reroute. **The value of
  upstream information sharing for routing = the entire ~750k gap between the best
  no-sharing policy (1,044k) and the oracle (295k), urgent0 — and 242 fewer lost patients
  (445→203) under urgent20.** This reframes the thesis's information-sharing narrative: the
  value of info sharing is realized by a two-line routing rule, no learner needed.
