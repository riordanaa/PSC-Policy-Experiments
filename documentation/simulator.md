# The `simulator/` package

A generic discrete-time, multi-echelon supply-chain simulator. It is independent of the RL code — the only RL touchpoint is `DRLDSDecisionMaker`, which holds a `DsWorld`. Everything here would run with purely rule-based decision makers.

## Core data model

| Module | Contents |
|--------|----------|
| `agent.py` | `Agent` base + `Manufacturer` / `Distributor` / `HealthCenter` subclasses, `Item`, `AgentBuilder`, and `agent_id_from_name()` (parses the trailing number out of names like `ds_2`). Agents carry inventory, backlog, on-order, a per-period history dict (`new_history_item`), and pluggable `demand_predictor` / `lead_time_estimator` / `order_up_to_level_calculator`. |
| `order.py` | `Order` — a quantity in transit through the order/shipment pipeline. |
| `decision.py` | Decision value objects: `ProduceDecision`, `AllocateDecision`, `OrderDecision`, `TreatDecision`. |
| `network.py` | `Network` and `InTransit` / `OrderMessage` payloads — moves shipments (physical lead time) and order messages (info lead time) between echelons. The simulation has both a physical `network` and an `info_network`. |
| `simulation.py` | `Simulation` container holding the agent lists (`manufacturers`, `distributors`, `health_centers`), the networks, the clock (`now`), and patient/disruption hooks. |
| `simulation_runner.py` | `SimulationRunner` — the per-period state machine (`next_cycle`, `_reset`). See [architecture.md](architecture.md#the-per-period-cycle). |
| `simulation_encoder.py` | Serialization helpers for simulation state. |

## Decision makers (`decision_maker.py`)

`PerAgentDecisionMaker` is a dispatcher: each agent registers one decision maker, and `make_decision` fans out to them. Implementations:

| Class | Echelon | Behavior |
|-------|---------|----------|
| `SimpleMNDecisionMaker` | Manufacturer | Base-stock production toward `up_to_level`; respects line capacity / disruptions. |
| `TempMNDecisionMaker` | Manufacturer | Alternate/experimental MN policy. |
| `SimpleHCDecisionMaker` | Health center | Splits demand across upstream DSs by recipe: `'bytrust'` (trust-weighted) or `'equally'` (from `HC_ORDER_SPLIT`). |
| `UrgentFirstHCDecisionMaker` | Health center | Prioritizes urgent demand. |
| `SimpleDSDecisionMaker` | Distributor | Rule-based base-stock baseline (the comparison point for DRL). |
| `DRLHCDecisionMaker` | Health center | DRL-controlled HC variant (owns a `DsWorld`). |
| `DRLDSDecisionMaker` | Distributor | **The main RL coupling.** Builds state, queries `DsWorld`, applies order + allocation. Handles transfer-learning warm-start. |

Free functions: `allocate_proportional` (rule-based split) and `allocate_drl` (apply DRL allocation ratios to available supply).

## Supporting models

| Module | Role |
|--------|------|
| `patient_model.py` | Demand generation at health centers. `ConstantPatientModel` (default) emits fixed demand; normal-distributed variants exist. Controlled by `PATIENT_*` config. |
| `demand_predictor.py` | Forecasts demand for base-stock sizing. `MovingAverage` is the default (`DEMAND_PREDICTOR_TYPE`). |
| `lead_time_estimator_new.py` | **Active** lead-time estimator (imported by `agent.py`). |
| `order_up_to_level_calculator.py` | Computes the base-stock order-up-to level from forecast demand, lead time, and `AGENT_CYCLE_SERVICE_LEVEL`. |
| `disruption.py` | **Active** disruption types, incl. `LineShutDownDisruption` (imported by `drl_simulation_profile_config.py`). |

## Tests

`unittest`-based, runnable individually:

```bash
python -m unittest simulator.test_agent
python -m unittest simulator.test_demand_predictor
python -m unittest simulator.test_lead_time_estimator
python -m unittest simulator.test_order_up_to_level_calculator
```

The root `test_pipeline.py` covers the integrated A2C + `DsWorld` + simulation pipeline.

## Legacy / unused — do not edit by mistake

These exist in the tree but are **not** the live versions. Confirm via imports before touching:

- `distruption.py` — misspelled legacy of `disruption.py` (the live one is the correctly-spelled file).
- `lead_time_estimator.py` — superseded by `lead_time_estimator_new.py` (which is what `agent.py` imports).
- `psychsim_decision_maker.py` — not wired into the active pipeline.
- `main.py` — older standalone entry; prefer the `Test/` scripts.
