# Routing Study — Design & Mechanics Documentation

Written BEFORE any experiment code, per protocol. All claims verified by reading code on
2026-06-09; file:line references are to this repository.

## Naming convention

This repo is 0-indexed; agent names are 1-indexed; earlier collaborator documents used ds_2/ds_3.
To avoid ambiguity, this study uses:

| Study name | Repo index | Agent name | Role |
|---|---|---|---|
| MN_disrupted | MN index 0 | `MN1` / `mn_1` | loses 95% capacity, periods 110–157 |
| DS_disrupted | DS index 0 | `DS1` / `ds_1` | fed only by MN_disrupted (`MN_DS_LINKS=[(0,0),(1,1)]`) |
| DS_healthy | DS index 1 | `DS2` / `ds_2` | fed only by MN_healthy |
| HC_trust | HC index 0 | `HC1` / `hc_1` | splits orders by trust |
| HC_equal | HC index 1 | `HC2` / `hc_2` | splits orders equally (fixed rule) |

Both HCs are connected to both DSs (`DS_HC_LINKS = [(0,0),(0,1),(1,0),(1,1)]`, config.py:24-27).

## 1. How each HC splits its orders

`SimpleHCDecisionMaker.make_decision` (simulator/decision_maker.py:93-176), every period:

1. Compute total order: `orderAmount = max(up_to_level − totalOnOrder − res_inventory + totalBacklog_non_urgent, 0)`
   (line 153-154), then capped: `orderAmount = min(orderAmount, max(2.0 × demand, 120))` (line 155-156).
2. Split it:
   - `'equally'` (HC_equal): `amount = orderAmount / n_upstream` to each DS (lines 158-165).
   - `'bytrust'` (HC_trust): `amount = orderAmount × trust[ds] / Σtrust` (lines 166-174).

Which HC uses which recipe: `config.HC_ORDER_SPLIT = ['bytrust', 'equally']` (config.py:30),
consumed in `Test/sim_test_config.py:50-55` when decision makers are built.

**Consequence (the artifact under test):** the split applies to the TOTAL order, and
`totalOnOrder` is subtracted before splitting. Orders stranded at DS_disrupted therefore
suppress what HC_equal orders from DS_healthy too — the suppression leaks across channels.

Note: order decisions with `amount ≤ 1` are silently dropped (simulation_runner.py:141-142).

## 2. Trust dynamics

- Update (decision_maker.py:125-131): under `'bytrust'`,
  `trust[ds] ← (1−δ)·trust[ds] + δ·ontime_deliv_rate[ds]`; under `'equally'`, trust is pinned
  to 1 and never used.
- On-time delivery rate (decision_maker.py:107-118): deliveries received this period ÷ average
  orders placed over the last 3 periods (clipped to ≤ 1).
- **δ is hard-coded** at `self.delta = 0.1` in `HealthCenter.reset()` (agent.py:581).
  **`config.HC_TRUST_DELTA` (config.py:31) is dead config — it is never read anywhere.**
  (Finding. Rung (c) must set `hc.delta` directly on the agent object.)
- **Trust never fully redirects:** trust converges to the EMA of the delivery rate, and
  DS_disrupted keeps trickling ~20/period, so its delivery rate stays > 0. Even under
  `'bytrust'` the dead chain keeps receiving a share roughly proportional to
  trickle-rate/(trickle-rate + 1).
- Initial trust ≈ 1 (pinned to 1 for `now < 2`, decision_maker.py:125-127).

## 3. On-order lifecycle (the stranded-order mechanism)

- Order placed: `make_order` sets `order.place_time = now` and appends a copy to `self.on_order`
  (agent.py:272-279).
- Delivery: `receive_delivery` matches by source and decrements amounts; zero-amount entries are
  removed (agent.py:181-204).
- **No timeout, no cancellation.** An order the DS cannot fill sits in the DS's backlog
  (agent.py:254) and the HC's `on_order` **indefinitely**, until the DS eventually ships it.
- **Late-delivery glut path:** when MN_disrupted recovers (period 158+), DS_disrupted works
  through its backlog and ships the stranded orders late. The HC then receives them on top of
  whatever it re-ordered from DS_healthy — the over-supply appears as HC holding cost.
- **Hard constraint on any write-off design:** `receive_delivery` RAISES
  `ValueError("Delivered amount more than on_order amount")` (agent.py:201-202) if a delivery
  arrives for quantity not in the ledger. Therefore stale orders must NOT be removed from
  `hc.on_order`. The write-off in rung (c) is **accounting-only**: the decision maker computes
  `totalOnOrder` excluding entries with `now − place_time > k × lead_time_dict[ds]`, but the
  ledger itself is untouched and late deliveries still land (honestly costed as holding).
- Age is computable: `now − order.place_time`; per-source expected lead time is
  `hc.lead_time_dict[ds]` (= `PHYSICAL_LEAD_TIME` = 2, set in
  drl_simulation_profile_config.py:113-115).

## 4. Demand, treatment, and what "lost" means

- Patient model selected by `config.PATIENT_MODEL_TYPE` (drl_simulation_profile_config.py:134-148):
  `'constant'` (urgent=0, non-urgent=120 — the repo default) or `'normal'`
  (N(mean, std) per period, numpy-seeded).
- Treatment (simulation_runner.py:110-125): unmet NON-URGENT demand moves to
  `backlog_non_urgent` — it is deferred, never lost. Unmet URGENT demand stays in `hc.urgent`
  and is overwritten at the next `receive_patient`, which logs it to
  `history['patient_lost']` (agent.py:597-614).
- **Metric semantics:** lost patients = `patient_lost[0]` (urgent component) ONLY.
  `patient_lost[1]` is misleading bookkeeping — that quantity was already added to backlog and
  is not lost.
- Fill rate per HC per period = `(satisfied_urgent + satisfied_non_urgent) / (urgent + non_urgent)`.
- Conservation (verify.py gate): non-urgent: `patient_nu(t) + backlog(t−1) = treated_nu(t) + backlog(t)`;
  urgent: `patient_u(t) = treated_u(t) + lost_u(recorded at t+1)`.

## 5. Disruption and supply cap

`config.DISRUPTIONS` (config.py:106-118): LineShutDown at manufacturer_index 0, periods 110–157,
decrease_factor 0.95. MN capacity = 40 lines × 10 = 400/period normally, 5% ≈ 20/period during.
Applied via `LineShutDownDisruption` (drl_simulation_profile_config.py:150-161).

## 6. Profit / cost accounting (system-level scoring source)

Per agent per period via `agent.collect_data(now)` (`'profit'` rows):
`P = PROFIT_PER_UNIT × AD − (INVENTORY_HOLDING_COST × inventory + BACKLOG_COST × backlog)`
with f=10, c=1, h=10 (config.py:81-83); AD = allocations shipped (MN/DS, agent.py:467-473,
544-548) or patients treated (HC, agent.py:626-631). DS `collect_data` also exposes
`delivered-to-hc{n}` rows (agent.py:533-543) — used for the HC-allocation diagnostic.
Holding and backlog components are recomputed separately in metrics.py from logged inventory
and backlog levels (same formula inputs), so cost can be decomposed.

## 7. Determinism and the demand-noise decision

**Finding (discovered during gate analysis, 2026-06-09):**
`NormalDistPatientModel.__init__` calls **`np.random.seed(0)`** (simulator/patient_model.py:28),
hard-resetting the global numpy RNG every time a simulation is built. Because the patient model
is constructed AFTER `config.set_global_seeds(seed)`, every "seed" produced the IDENTICAL demand
path — cross-seed variance was exactly zero (caught because the tuning mean on seeds 1–10 equaled
the reporting mean on seeds 11–30 to the digit). Any historical experiment that used the normal
demand model and reported multi-seed statistics was actually reporting one demand path. Our
runner re-applies `set_global_seeds(seed)` after construction (run_ladder.py, run_one), restoring
genuine per-seed noise; verification gate 6 now checks cross-seed variance > 0.

- `config.set_global_seeds(seed)` seeds python/numpy (config.py:287-298); rule-based runs have
  no other entropy source.
- **Verified finding (2026-06-09):** the prior base-stock run
  (`r5_test_results_basestock_ds1_disrupted/basestock_ds1_log.csv`) used `'constant'` demand and
  has **exactly zero cross-seed variance** (during-phase DS_disrupted backlog = 1983 in all 10
  seeds). Its "mean ± SE over 10 seeds" was 10 identical replicates.
- **Study decision:** primary and secondary configs use `PATIENT_MODEL_TYPE='normal'`
  (non-urgent N(120, 5); urgent N(0,0) primary / N(20,0) secondary) so paired seeds carry real
  demand noise. The constant-demand config is retained as verification gate 1: rung (a) under
  constant demand must EXACTLY reproduce the known 1983 trajectory.

## 8. Simulation construction (no core edits)

Build pattern proven in the earlier base-stock script: `ConfigDrivenProfile()` +
`PerAgentDecisionMaker` with `SimpleHCDecisionMaker` / `SimpleMNDecisionMaker` /
`SimpleDSDecisionMaker` (all DSs rule-based), advanced by `runner.next_cycle()`. Custom HC
decision makers are injected per-agent from `routing_study/policies.py`; rung (c)'s δ′ is set
via `hc.delta = …` on the built agents. Per-period metrics are collected inside the loop
(history older than `AGENT_HISTORY_PRESERVE_TIME=60` is purged, agent.py:288/296 — post-hoc
extraction is impossible).

## Assumptions stated

- `INFO_SHARING_SCENARIO` does not affect rule-based decision makers (it shapes DRL state only);
  left at repo default.
- `AGENT_FIXED_ORDER_UP_TO_LEVEL=False`: up-to levels are recomputed each period from demand and
  lead-time estimates, so they rise during the disruption for all policies alike.
- The DS order is split equally across its upstream MNs (one MN each in this topology — no
  routing freedom exists at the DS→MN layer; the only routing freedom in this topology is the
  HC→DS split under study).
