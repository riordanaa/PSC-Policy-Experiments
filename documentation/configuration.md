# Configuration (`config.py`)

`config.py` is a flat module of constants plus a few helper functions. There is no config file format or CLI for most parameters — experiment scripts either read these constants directly or mutate them in place (and usually restore them afterward). The values below are the committed defaults; treat the file itself as authoritative if they have drifted.

## Topology

```python
N_MN, N_DS, N_HC = 2, 2, 2          # counts per echelon
MN_DS_LINKS = [(0,0), (1,1)]        # manufacturer -> distributor edges (0-indexed)
DS_HC_LINKS = [(0,0),(0,1),(1,0),(1,1)]  # distributor -> health-center edges
HC_ORDER_SPLIT = ['bytrust', 'equally']  # per-HC supply split recipe
HC_TRUST_DELTA = 0.1
```

Edges are explicit, not inferred. Changing topology = change the counts **and** the edge lists. Helper functions derive neighbors and action sizes from these (see bottom of this doc).

## Simulation horizon

```python
TOTAL_EPISODES = 500
TOTAL_PERIODS  = 300
WARMUP_PERIODS = 60      # early periods before the system is "warm"
STUDY_NAME     = 'study_config'
```

Scripts override episodes/periods via `--episodes` / `--periods`; `build_simulation()` applies the override for one build then restores the module constant.

## Patient / demand model

```python
PATIENT_MODEL_TYPE = 'constant'     # 'constant' or normal-distributed
PATIENT_NON_URGENT = 120            # constant demand per HC per period
PATIENT_NORMAL_NON_URGENT_MEAN  = 120
PATIENT_NORMAL_NON_URGENT_STDEV = 5
```

Urgent vs non-urgent demand streams are tracked separately; the default config drives non-urgent demand of 120/period and no urgent demand.

## Manufacturer parameters

```python
MN_NUM_LINES = 40; MN_LINE_CAPACITY = 10; MN_NUM_ACTIVE_LINES = 40
MN_PRODUCTION_LEAD_TIME = 2
MN_DEFAULT_UP_TO_LEVEL  = 120
```

Production capacity = active lines × capacity. Disruptions reduce active lines.

## Inventory policy (rule-based agents)

```python
AGENT_LEAD_TIME = 2; AGENT_REVIEW_TIME = 0
AGENT_CYCLE_SERVICE_LEVEL = 0.9
AGENT_HISTORY_PRESERVE_TIME = 60
AGENT_FIXED_ORDER_UP_TO_LEVEL = False   # if True, use AGENT_DEFAULT_UP_TO_LEVEL
AGENT_DEFAULT_UP_TO_LEVEL = 120
DEMAND_PREDICTOR_TYPE = 'MovingAverage'
```

These feed the base-stock order-up-to-level calculator and demand predictor used by non-DRL agents.

## Profit / cost model

```python
PROFIT_PER_UNIT = 10.0
INVENTORY_HOLDING_COST = 1.0
BACKLOG_COST = 10.0
```

Profit per agent per period: `P = f·AD − (c·I + h·B)` where `f`=revenue/unit allocated, `c`=holding cost, `h`=backlog cost. This is the evaluation metric in `evaluate_drl.py`, and a scaled version feeds the DRL "profit proxy" reward term.

## Information sharing

```python
INFO_SHARING_SCENARIO = 'partial'   # 'full' | 'partial' | 'none'
```

- `full` — DS observes all HC and MN metrics (`HC_ALL_METRICS`, `MN_ALL_METRICS`).
- `partial` — DS observes only `HC_STATE_METRICS` (Loss, Backlog) and `MN_STATE_METRICS` (In production, Demand).
- `none` — DS observes only its own metrics.

This is consumed by `build_state_config()` and **changes the state dimension**, so it must match between training and any checkpoint reuse.

## Lead times

```python
PHYSICAL_LEAD_TIME = 2   # shipment travel time
INFO_LEAD_TIME = 0       # order-message delay
```

## Disruptions

```python
DISRUPTIONS = [{
    'type': 'LineShutDown',
    'manufacturer_index': 0,
    'num_active_lines': MN_NUM_ACTIVE_LINES,
    'happen_day_1': 110, 'end_day_1': 157, 'decrease_factor_1': 0.95,
    'happen_day_2': -1,  'end_day_2': -1,  'decrease_factor_2': 0,
}]
```

A `LineShutDown` cuts a manufacturer's active lines by `decrease_factor` between `happen_day` and `end_day`. Two windows are supported (`_2` fields, `-1` = disabled). Severity presets referenced across studies: **short** 110–115, **moderate** 110–127, **long** 110–157.

## DRL hyperparameters

```python
DRL_LAYER_TYPE = 'GRU'     # 'Dense' or 'GRU'  (Study 1 compares these)
DRL_GAMMA = 0.95
DRL_ACTOR_LR = DRL_CRITIC_LR = 0.01
DRL_ACTION_BOUND = 1.0; DRL_STD_BOUND = [1e-2, 1.0]

# architecture
DRL_HIDDEN_SIZE = 128; DRL_DROPOUT = 0.3; DRL_GRADIENT_CLIP = 1.0
DRL_ACTOR_FC_LAYERS = 2; DRL_CRITIC_FC_LAYERS = 3
DRL_GRU_LR_FACTOR = 0.3    # recurrent layers train at LR × this

# observation / action ranges
DRL_HISTORY_SIZE = 8       # sliding window length (M)
DRL_ORDER_HI = 240; DRL_ORDER_LO = 0
DRL_ALLOC_HI = 1.0; DRL_ALLOC_LO = 0.0

# adaptive learning rate (driven by TD-error magnitude)
DRL_BETA_ALPHA = 0.05; DRL_MIN_LR = 1e-4; DRL_MAX_LR = 0.005
# adaptive exploration (driven by TD-error magnitude)
DRL_BETA_EPSILON = 0.005; DRL_INITIAL_EXPLORATION = 1.0
DRL_MIN_EXPLORATION = 0.1; DRL_MAX_EXPLORATION = 2.0; DRL_EXPLORATION_DECAY = 0.998

DRL_WARMUP_STEPS = 10      # skip updates first N periods (state incomplete)
DRL_REWARD_EPSILON = 50.0  # tolerance band for R2 (order fulfillment)
DRL_ENTROPY_COEFF = 0.01   # entropy bonus in actor loss
DRL_PMT_LOWER, DRL_PMT_UPPER = 0.5, 1.5   # R6 production/demand ratio band

# profit proxy reward term
DRL_EQ1_PROXY_WEIGHT = 0.15; DRL_EQ1_PROXY_SCALE = 3500.0

EVAL_TRAIN_EPISODES = 45   # default training length for evaluation scripts

# transfer learning
TRANSFER_CHECKPOINT_DIR = None       # set to a dir to warm-start
TRANSFER_FREEZE_CRITIC = False
TRANSFER_FINETUNE_LR_FACTOR = 0.1    # base LR × this when fine-tuning
```

See [drl-and-reward.md](drl-and-reward.md) for how these are used.

## MAB reward weighting

```python
REWARD_NUM_COMPONENTS = 6
MAB_REWARD_ARMS = [ ... 8 weight vectors over the 6 components ... ]
MAB_WINDOW_SIZE = 8; MAB_THRESHOLD = 5.0; MAB_DECAY_FACTOR = 0.5
```

Each arm is a 6-vector of weights applied to the reward components. The UCB-P bandit picks an arm per step and detects distribution change to reset. Arm 1 = equal weights; arms 2–7 double one component; arm 8 halves R5.

## State observation schema

```python
HC_STATE_METRICS = ['Loss', 'Backlog']                     # partial mode
DS_STATE_METRICS = ['Backlog','Inventory-Level','Order','Delivery',
                    'Inventory','On-Order','Demand','Lead-time','Up-to-level']
MN_STATE_METRICS = ['In production', 'Demand']             # partial mode
HC_ALL_METRICS / MN_ALL_METRICS                            # full mode supersets
```

## Helper functions

| Function | Returns |
|----------|---------|
| `build_state_config()` | Per-agent `{agent: [metrics]}` dict, gated by `INFO_SHARING_SCENARIO`. |
| `get_ds_connected_hcs(i)` / `get_ds_connected_mns(i)` | Neighbor indices of distributor `i`. |
| `get_hc_connected_dss(i)` / `get_mn_connected_dss(i)` | Reverse-direction neighbors. |
| `get_num_actions_for_ds(i)` | `1 + len(connected HCs)` — Actor/Critic output dim. |
| `set_global_seeds(seed)` | Seeds `random`, `numpy`, `tensorflow`. |
| `snapshot_config()` / `save_config_snapshot(dir)` | JSON-serialize all public constants for reproducibility. |
| `save_run_seed_metadata(dir, seed)` | Record applied seed vs module default. |
| `load_config_from_snapshot(path)` | Restore constants from a prior run's snapshot. |

`RANDOM_SEED = 42` is the default.
