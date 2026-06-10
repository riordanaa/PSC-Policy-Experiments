# Architecture

The system has three layers that are deliberately decoupled:

1. **Configuration** (`config.py`) — a flat module of constants that is the single source of truth for an experiment.
2. **Simulation engine** (`simulator/`) — a generic discrete-time multi-echelon supply-chain simulator that knows nothing about reinforcement learning.
3. **DRL environment & model** (`ds_world.py`, `model_a2c.py`) — the A2C agent and its training loop, plugged into the engine through one decision maker.

The glue is the **decision maker layer** (`simulator/decision_maker.py`), which is where rule-based agents and the DRL agent meet a common interface.

```
config.py  ──►  drl_simulation_profile_config.ConfigDrivenProfile  (builds agents from topology)
                          │
                          ▼
            SimulationRunner.next_cycle()  ◄── PerAgentDecisionMaker
                          │                       ├── SimpleMNDecisionMaker   (manufacturers, base-stock)
                          │                       ├── SimpleHCDecisionMaker   (health centers, trust/equal split)
                          │                       └── DRLDSDecisionMaker      (distributors)
                          │                                   │
                          │                                   ▼
                          │                              ds_world.DsWorld  ──►  model_a2c.a2c_Model (Actor + Critic)
                          ▼                                   │                         ▲
                  agent state history  ───────────────────────┘   reward (6 comps × MAB weights)
```

## The per-period cycle

`SimulationRunner.next_cycle()` (`simulator/simulation_runner.py`) advances the simulation by one period and runs these phases in order:

1. `_update_patient` — generate demand at health centers (patient model).
2. `_update_agents` — agents advance internal state (inventory, predictions, lead-time estimates).
3. `_update_network` — move in-transit shipments and order messages along physical/info lead times.
4. `_exogenous_event` — apply disruptions (e.g. a manufacturer line shutdown) active for this period.
5. `_make_decision` — every agent's decision maker produces decisions (`Produce`, `Allocate`, `Order`, `Treat`).
6. `_apply_decision` — decisions mutate the world.

`_reset()` re-initializes the world at episode boundaries (resets agents, clears networks, re-parametrizes, re-attaches the patient model and disruptions).

## How the DRL agent couples in

`DRLDSDecisionMaker.__init__` (`simulator/decision_maker.py:224`) constructs a `DsWorld(DS_Id=...)`. Each period it:

1. Builds a **state matrix** from the live metrics of the distributor's connected HCs, MNs, and itself (`get_states`). Which metrics are visible is governed by `INFO_SHARING_SCENARIO`.
2. Feeds that into the `DsWorld`, which appends to a sliding window (`DRL_HISTORY_SIZE` periods), normalizes it, and asks the Actor for actions.
3. Applies the action: index `0` is an **order quantity** (scaled into `[DRL_ORDER_LO, DRL_ORDER_HI]`), indices `1..N` are **allocation ratios** to the N connected health centers, applied via `allocate_drl`.

Rule-based agents bypass all of this: manufacturers produce to a base-stock level (`SimpleMNDecisionMaker`), health centers split incoming supply by trust or equally (`SimpleHCDecisionMaker`, recipe from `HC_ORDER_SPLIT`).

## Topology is data, not code

There is no special-casing of the 2×2×2 default. `N_MN`/`N_DS`/`N_HC` plus the explicit edge lists `MN_DS_LINKS` and `DS_HC_LINKS` fully define the network. `ConfigDrivenProfile` builds exactly that many agents and wires the edges. Per-agent quantities derive from the links:

- `get_ds_connected_hcs(i)` / `get_ds_connected_mns(i)` — neighbors of distributor `i`.
- `get_num_actions_for_ds(i)` = `1 + len(connected HCs)` — the action-vector length, which sets the Actor/Critic output dimension.

To scale up (e.g. Study 6's 4×4×4) you change these constants; everything downstream adapts. The trade-off: the state dimension and action dimension change with topology and info-sharing mode, so **checkpoints are only interchangeable between runs with matching topology and `INFO_SHARING_SCENARIO`**.

## Entry points

| Entry point | Purpose |
|-------------|---------|
| `Test/sim_test_config.py` (`build_simulation`) | Canonical builder used by most scripts; reads `config.py`, wires decision makers, returns `(simulation, runner, drl_dms)`. Temporarily overrides episode/period counts then restores them. |
| `Test/smoke_test.py` | 2-episode end-to-end connectivity check. |
| `Test/evaluate_drl.py`, `Test/drl_evaluation.py` | DRL-vs-base-stock profit comparison (the headline claim). |
| `Test/study_*.py`, `Test/transfer_learning_runner.py` | The six studies (see [studies.md](studies.md)). |
| `run_r5_diagnostic.py`, `regen_plots.py`, `gen_*.py` | Diagnostics & figures (see [plotting-and-diagnostics.md](plotting-and-diagnostics.md)). |

All scripts insert the repo root (and usually `Test/`) onto `sys.path` so `import config` and `from sim_test_config import ...` resolve regardless of CWD — but the bash runners `cd Test` first, so prefer running from the repo root and let the scripts manage the path.
