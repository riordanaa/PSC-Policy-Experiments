# HA — Phase-1 addenda (amendments A1 + A3): order taper and fairness-neutral allocation

## A1 — Order-taper-toward-failed-source (upstream-signal triggered, discrete rule)

**Hypothesis.** The DS tapering its orders to a failed MN (cap at observed delivery rate
while the MN is below 50% nominal — a discrete pre-registered rule on the shared signal)
removes the dead-factory queue cost that dominated the rung-c residual.

**Method.** `ShapedDS.mn_taper_m`, wired post-build; m ∈ {1.0, 1.5} tuned on seeds 1–10
(m=1.0 won). Reporting seeds 11–30, both configs, both accounting conventions.
Data: `results/slack/*/h5_compound_full.csv`, `h4b_ceiling_taper.csv`.

**Result (reporting seeds, urgent0 dp-cost / ex-MN-backlog):**

| Policy | Convention (i) full | Convention (ii) ex-MN | Lost (urgent20) |
|---|---:|---:|---:|
| h3b reroute (no taper) | 294,796 | 212,636 | 203 |
| **h5 = reroute + taper (deployable)** | **273,088** | 220,648 | 204 |
| h4 ceiling (oracle + JIT, no taper) | 284,120 | 234,485 | 207 |
| h4b ceiling + taper | 284,626 | 236,130 | 208 |

- **The deployable compound now beats the oracle-assisted ceilings** under convention (i):
  oracle foresight (JIT pre-build, exact window) adds nothing measurable beyond the shared
  upstream signal — its premium outweighs its benefit.
- **The taper's gain is accounting-sensitive** (the dual-convention amendment caught this):
  full convention −22k; ex-MN convention ≈ +8k (neutral-to-slightly-worse). It reduces the
  dead-factory queue (bookkeeping), not patient outcomes (lost unchanged) or physical flow.
- New best measured policy in the slack regime = h5, fully deployable. The measured "room
  for learning" above it is ZERO against every oracle composition we built.

**Verdict.** KEPT in the compound for convention-(i) reporting, explicitly flagged as
accounting-sensitive; under a patient-facing lens the taper is optional. The detection
constraint held: the signal gates one discrete rule; no continuous optimizer involved.

## A3 — Fairness-neutral allocation variants (rotating-priority, priority-with-floor)

**Hypothesis.** A fairness-neutral variant of static priority might capture its 12% gain
without the dispersion cost.

**Result (slack, reporting seeds):** REFUTED, decisively.

| Rule | dp urgent0 | lost urgent20 | dispersion |
|---|---:|---:|---:|
| proportional (neutral baseline) | 1,209,659 | 510 | 0.000 |
| static priority (costed baseline) | 1,062,538 | 445 | +0.023 |
| rotating-priority | 1,630,090 | 740 | +0.002 |
| priority-with-floor 0.25 | 1,203,215 | 470 | +0.031 |

Rotating priority is catastrophic (+53% vs static priority; worst lost-patients number
measured in the slack regime) — alternating the priority HC alternates failures and degrades
BOTH trust loops, the same failure mode as backlog-priority. The floor variant collapses to
proportional on cost while WORSENING dispersion. **The priority gain is inseparable from
sustained asymmetry: there is no fairness-free lunch in this allocation channel.** The two
baselines carried through all tables (proportional / static-priority) are the honest
endpoints of the trade-off.

**Verdict.** DON'T-TRY further fairness-engineered allocation rules; report the trade-off as
a two-point choice. Mechanism note for the paper: this is the third independent confirmation
(after backlog-priority and serve-captive) that allocation CONSISTENCY is what the trust
feedback rewards.
