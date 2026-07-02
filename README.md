# PSC Policy Experiments

Experimental snapshot of a Deep Reinforcement Learning (DRL) framework for ordering and allocation decisions in a multi-echelon pharmaceutical supply chain (PSC) under disruptions, plus a reward-shaping audit and a series of deterministic policy studies built on top of it.

> **Start here: [`value_decomposition_study/report/robustness_report.pdf`](value_decomposition_study/report/)** — **the capacity report**, the key result of the project so far: "shed" (the disrupted distributor deprioritizing its trust hospital so it reroutes) is a *capacity-conditional misaligned incentive* — privately rational at any capacity, system-destructive below healthy-chain capacity ≈ 180–240. Then [`lead_time_severity_report.pdf`](value_decomposition_study/report/) (its lead-time/severity follow-up). For everything from the earlier studies, check [`consolidated_report/consolidated_findings.pdf`](consolidated_report/) — the claims scorecard with status codes and a superseded-claims (do-not-cite) list — before citing any study-folder number.

## Study index (newest first; every folder has its own README)

| Folder | Question | Headline (audited) |
|---|---|---|
| `value_decomposition_study/report/robustness_report.pdf` | **does the shed/rerouting result survive capacity stress, δ, and metric scrutiny? (the capacity report)** | shed = capacity-conditional misaligned incentive; system profit flips sign at MN2 ≈ 180–240; rerouted load amplified ~10× on the healthy chain; δ-invariant; trust hospital worse off than the captive at severe scarcity |
| `value_decomposition_study/report/lead_time_severity_report.pdf` | do the capacity findings survive longer lead times and milder severities? | base stock auto-scales: backlog *falls* with lead time and the collapse mildens, but lost patients jump ~2.5× past lead time ~5; shed/flip is severity-gated (inert < ~65–80% cut) |
| `value_decomposition_study/` (June 10–11 campaigns) | value decomposition; simple-rules-vs-RL from the distributor's seat | info-sharing reroute ≡ perfect-onset oracle (bit-exact); **the shed/taper finding**: simple distributor compound removes 49–51% of base stock's loss (thesis RL claimed 89%, unreplicated); lever-flip map; hypothesis cards H1–H10 |
| `consolidated_report/` | claims scorecard (single source of truth up to June 11) | claims table + 4 findings + do-not-cite list (predates the two reports above) |
| `understanding_study/` | with routing repaired, what's left? | allocation channel ≤12%; residual is mostly dead-factory bookkeeping; dynamics anatomy |
| `routing_study/` | is the disruption pile-up physics or a routing artifact? | 67–91% of disruption cost removable by HC routing rules alone; **its `run_ladder.py`/`metrics.py` are the shared harness all later studies reuse** |
| `reward_report_pdf/`, `reward_fix_report/` | does the thesis's shaped reward shape? does fixing it fix the agent? | reward components defective/saturated; repaired pipeline trains stably but loses to base stock on system profit |

All studies: gated harness (bit-exact baseline reproduction, determinism, conservation), pre-registered tuning/reporting seed splits (1–10 / 11–30), dual cost accounting, and per-phase independent audits re-deriving headline numbers from raw CSVs.

## Repository map (top level)

| Path | What it is |
|---|---|
| `config.py`, `model_a2c.py`, `ds_world.py`, `simulator/`, `Test/` | The original DRL codebase (untouched by the studies — experiments inject parameters at runtime). See `CLAUDE.md` / `documentation/`. |
| `value_decomposition_study/`, `routing_study/`, `understanding_study/` | The 2026 deterministic policy studies (each has a README; results CSVs are local-only). |
| `consolidated_report/`, `reward_report_pdf/`, `reward_fix_report/` | Reports: the claims scorecard and the May reward-audit pair. |
| `documentation/` | Deep dives: architecture, configuration, DRL/reward, simulator, studies, plotting. |
| `r5_test_results*/` | Committed May-2026 RL diagnostic outputs (data, not code). `r5_test_results/memory/` is a local-only assistant-memory dir (gitignored). |
| `gen_*.py`, `generate_plots.py`, `regen_plots.py`, `run_r5_diagnostic.py` | Reward-audit plot/diagnostic scripts (documented in `documentation/plotting-and-diagnostics.md`). |
| `run_all_studies.sh`, `run_parallel.sh`, `run_batch_*.sh` | RL study batch runners (see Quick Start below). |
| `archive/` | Historical local artifacts moved out of the root (old RL training checkpoints, logs). |
| `meeting_transcripts/` | Local-only working notes (gitignored; not part of the public repo). |

## What this repository adds on top of the original codebase

This is a working copy of the original `Inventory_DRL_MAB` research code (A2C + MAB reward shaping; see the original README content below) extended with:

**Reward audit and fixes (flag-gated, default OFF — defaults reproduce the original behavior):**

| Flag in `config.py` | Default | What it enables |
|---|---|---|
| `DRL_REWARD_FIX` | `False` | Repaired formulas for reward components r1/r4 (true reversal count), r2 (fractional gap tolerance), r3 (wider inventory band), r5 (raw order quantity in the action buffer), r6 (graded production-alignment sign). Originals preserved in the `else` branches in `ds_world.py`. |
| `DRL_FIXED_EXPLORATION_SCHEDULE` | `False` | Replaces the adaptive exploration-rate rule with a linear decay schedule (1.0 → 0.1 over `DRL_FIXED_DECAY_EPISODES`, default 50). |

**Reports (LaTeX sources + compiled PDFs):**
- `reward_report.tex` / `reward_report_pdf/` — audit of the six shaped-reward components: which emit a usable learning signal as coded, and why.
- `reward_fix_followup_report.tex` / `reward_fix_report/` — experiments with the repaired rewards: component-level signal checks, multi-checkpoint policy-oscillation analysis, the exploration-schedule experiment, and a DRL vs base-stock head-to-head (backlog dynamics and profit).

**Experiment outputs** (plots, configs, JSON logs; large CSVs and model weights are gitignored):
- `r5_test_results/` — original-reward diagnostic baseline.
- `r5_test_results_fixed/` — repaired rewards, adaptive exploration rule still active (300 episodes).
- `r5_test_results_fixed_pretrain/` — repaired rewards with a pretraining phase.
- `r5_test_results_fixed_schedule/` — repaired rewards + linear exploration schedule (early-stopped at episode 89; the stably-training configuration).
- `r5_test_results_basestock_ds1_disrupted/` — base-stock policy at the disrupted distributor, used as the comparison baseline.
- `r5_test_results_dense_partial_05/` — Dense/partial-info configuration run.

**Documentation:** `documentation/` contains deep dives (architecture, configuration, DRL and reward, simulator, studies, plotting) and thesis chapter summaries. `CLAUDE.md` is an orientation file for AI coding assistants.

**Status note:** with the repairs above the agent trains stably and holds a sensible policy, but it does not beat the base-stock baseline on cumulative system profit in this configuration; the comparison and caveats are laid out in the follow-up report. Treat results in this repo as diagnostics of this code version, not as a reproduction of the original thesis results.

---

# Original README: DRL Pharmaceutical Supply Chain Simulator

Deep Reinforcement Learning (DRL) framework for optimizing ordering and allocation decisions in a multi-echelon pharmaceutical supply chain (PSC) under disruptions.

## Overview

This project implements an Advantage Actor-Critic (A2C) model with Multi-Armed Bandit (MAB) adaptive reward shaping for distributor agents in a three-echelon supply chain:

- **Manufacturers (MN)**: Produce drugs using base-stock policy
- **Distributors (DS)**: DRL-controlled agents that learn ordering and allocation
- **Health Centers (HC)**: Order drugs using trust-based or equal-split policies

The topology is configurable (default 2x2x2, supports NxNxN).

## Requirements

- Python 3.10+
- TensorFlow 2.11+

### Install Dependencies

```bash
pip install -r requirements.txt
```

## Project Structure

```
Inventory_DRL_MAB/
├── config.py                    # Central configuration (all parameters)
├── model_a2c.py                 # A2C Actor-Critic model (Dense + GRU)
├── ds_world.py                  # DRL environment for distributor agents
├── generate_plots.py            # Plot reward comparisons
├── requirements.txt             # Python dependencies
├── test_pipeline.py             # Unit tests
├── run_all_studies.sh           # Run all studies sequentially
├── run_parallel.sh              # Run studies in parallel (3 batches)
├── run_batch_A.sh               # Batch A: Study 1 + 3 + Core eval
├── run_batch_B.sh               # Batch B: Study 2 + 4 + 5
├── run_batch_C.sh               # Batch C: Study 6
│
├── simulator/                   # Supply chain simulation engine
│   ├── agent.py                 # Agent types (MN, DS, HC)
│   ├── simulation.py            # Simulation container
│   ├── simulation_runner.py     # Simulation cycle logic
│   ├── decision_maker.py        # Decision makers (rule-based + DRL)
│   ├── decision.py              # Decision types
│   ├── order.py                 # Order data structure
│   ├── network.py               # Network topology
│   ├── patient_model.py         # Demand generation
│   ├── demand_predictor.py      # Demand forecasting
│   ├── lead_time_estimator_new.py  # Lead time estimation
│   ├── order_up_to_level_calculator.py  # Base-stock level
│   ├── disruption.py            # Disruption types
│   └── test_agent.py            # Agent unit tests
│
└── Test/                        # Experiment scripts
    ├── sim_test_config.py       # Config-driven training entry point
    ├── drl_simulation_profile_config.py  # Config-driven profile
    ├── smoke_test.py            # Quick end-to-end validation
    ├── drl_evaluation.py        # DRL vs baseline comparison
    ├── evaluate_drl.py          # DRL evaluation entry point
    ├── transfer_learning_runner.py     # Transfer learning + sweeps
    ├── study_gru_vs_dense.py    # Study 1: Architecture comparison
    ├── study_state_space.py     # Study 2: State-space sensitivity
    ├── study_mab_ablation.py    # Study 3: MAB ablation
    └── study_scalability.py     # Study 6: Scalability (2x2x2 vs 4x4x4)
```

## Quick Start

All commands are run from the project root directory.

### 1. Run Smoke Test (quick validation)

```bash
cd Test
python smoke_test.py
```

### 2. Run Full Training (config-driven)

Edit `config.py` to set your parameters, then:

```bash
cd Test
python sim_test_config.py
```

### 3. Run DRL vs Baseline Comparison

```bash
cd Test
python evaluate_drl.py --episodes 80 --periods 300
```

### 4. Run All Studies

```bash
# Sequential (single machine)
chmod +x run_all_studies.sh
EPISODES=80 PERIODS=300 ./run_all_studies.sh

# Parallel (multi-core / cloud VM)
chmod +x run_parallel.sh run_batch_A.sh run_batch_B.sh run_batch_C.sh
QUICK=1 nohup ./run_parallel.sh &> run_parallel.log &
```

### 5. Run Individual Studies

```bash
cd Test

# Study 1: GRU vs Dense
python study_gru_vs_dense.py --episodes 80 --periods 300

# Study 2: State-space sensitivity
python study_state_space.py --episodes 80 --periods 300

# Study 3: MAB ablation (fixed vs adaptive reward)
python study_mab_ablation.py --episodes 80 --periods 300

# Study 4: Transfer learning
python transfer_learning_runner.py --phase train --scenario long_disruption --episodes 80

# Study 5: Information sharing sweep
python transfer_learning_runner.py --phase sweep --sweep-param info_sharing --episodes 80

# Study 6: Scalability (2x2x2 vs 4x4x4)
python study_scalability.py --episodes 80 --periods 300
```

## Configuration

All parameters are in `config.py`. Key sections:

### Topology

```python
N_MN = 2                    # Number of manufacturers
N_DS = 2                    # Number of distributors (DRL agents)
N_HC = 2                    # Number of health centers
MN_DS_LINKS = [(0,0),(1,1)] # MN-to-DS connections
DS_HC_LINKS = [(0,0),(0,1),(1,0),(1,1)]  # DS-to-HC connections
```

### Simulation

```python
TOTAL_EPISODES = 500        # Training episodes
TOTAL_PERIODS = 300         # Periods per episode
```

### DRL Hyperparameters

```python
DRL_LAYER_TYPE = 'Dense'    # 'Dense' or 'GRU'
DRL_GAMMA = 0.95            # Discount factor
DRL_ACTOR_LR = 0.001        # Actor learning rate
DRL_CRITIC_LR = 0.001       # Critic learning rate
DRL_HISTORY_SIZE = 8        # State observation window
DRL_ORDER_HI = 240          # Max order quantity
DRL_ORDER_LO = 0            # Min order quantity
```

### Disruption

```python
DISRUPTIONS = [{
    'type': 'LineShutDown',
    'manufacturer_index': 0,
    'happen_day_1': 110,
    'end_day_1': 157,
    'decrease_factor_1': 0.95,
}]
```

### Information Sharing

```python
INFO_SHARING_SCENARIO = 'partial'  # 'full', 'partial', or 'none'
```

### Profit Evaluation

```python
PROFIT_PER_UNIT = 10.0       # Revenue per unit allocated
INVENTORY_HOLDING_COST = 1.0 # Cost per unit held
BACKLOG_COST = 10.0          # Cost per unit of backlog
```

## Studies

| Study | Script | Description |
|-------|--------|-------------|
| Study 1 | `study_gru_vs_dense.py` | GRU vs Dense architecture comparison |
| Study 2 | `study_state_space.py` | State-space sensitivity (minimal / partial / full) |
| Study 3 | `study_mab_ablation.py` | Fixed vs adaptive (MAB) reward weighting |
| Study 4 | `transfer_learning_runner.py` | Transfer learning across disruption scenarios |
| Study 5 | `transfer_learning_runner.py` | Information sharing sweep (full / partial / none) |
| Study 6 | `study_scalability.py` | Scalability (2x2x2 vs 4x4x4 topology) |

## Architecture

Each DRL distributor agent has:

- **Actor**: Dense/GRU layers with attention and tanh output
- **Critic**: Dense/GRU layers with attention and linear output
- **Actions**: 1 order quantity + N allocation ratios (one per connected HC)
- **State**: Sliding window (M=8) of HC/DS/MN metrics
- **Reward**: 6 components weighted by MAB-selected arm

### Reward Components

1. HC backlog trend
2. Order fulfillment rate
3. Inventory level stability
4. DS backlog reduction
5. Action stability
6. MN production-demand alignment

### Adaptive Mechanisms

- **UCB-P Multi-Armed Bandit**: Dynamically selects reward weight vectors
- **Adaptive learning rate**: Adjusts LR based on TD error magnitude
- **Adaptive exploration**: Adjusts exploration rate based on TD error

## Reproducibility

Each experiment run saves:
- `config_snapshot.json`: Full parameter snapshot
- `run_seed.json`: Random seed metadata
- `learning_curve.json`: Per-episode metrics
- Model checkpoints (actor/critic weights)

Set seeds via `config.RANDOM_SEED` or `--seed` argument.

## License

Apache License 2.0
