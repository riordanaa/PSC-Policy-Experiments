"""
Central configuration for the DRL supply chain simulation.
All parameters are defined here. Change this file to modify the experiment.

Topology: supports any N_MN x N_DS x N_HC network.
Connections: defined explicitly via mn_ds_links and ds_hc_links.
"""
import json
import os


# ============================================================================
# TOPOLOGY (default: 2x2x2)
# ============================================================================
N_MN = 2
N_DS = 2
N_HC = 2

MN_DS_LINKS = [
    (0, 0),   # MN1 -> DS1
    (1, 1),   # MN2 -> DS2
]

DS_HC_LINKS = [
    (0, 0), (0, 1),   # DS1 -> HC1, HC2
    (1, 0), (1, 1),   # DS2 -> HC1, HC2
]

# HC1 splits by trust, HC2 splits equally
HC_ORDER_SPLIT = ['bytrust', 'equally']
HC_TRUST_DELTA = 0.1


# ============================================================================
# SIMULATION
# ============================================================================
TOTAL_EPISODES = 500
TOTAL_PERIODS = 300
WARMUP_PERIODS = 60
STUDY_NAME = 'study_config'


# ============================================================================
# PATIENT / DEMAND MODEL
# ============================================================================
PATIENT_MODEL_TYPE = 'constant'
PATIENT_URGENT = 0
PATIENT_NON_URGENT = 120
PATIENT_NORMAL_URGENT_MEAN = 0
PATIENT_NORMAL_URGENT_STDEV = 0
PATIENT_NORMAL_NON_URGENT_MEAN = 120
PATIENT_NORMAL_NON_URGENT_STDEV = 5


# ============================================================================
# MANUFACTURER PARAMETERS
# ============================================================================
MN_NUM_LINES = 40
MN_LINE_CAPACITY = 10
MN_NUM_ACTIVE_LINES = 40
MN_PRODUCTION_LEAD_TIME = 2
MN_DEFAULT_UP_TO_LEVEL = 120


# ============================================================================
# AGENT BUILDER / INVENTORY POLICY
# ============================================================================
AGENT_LEAD_TIME = 2
AGENT_REVIEW_TIME = 0
AGENT_CYCLE_SERVICE_LEVEL = 0.9
AGENT_HISTORY_PRESERVE_TIME = 60
AGENT_FIXED_ORDER_UP_TO_LEVEL = False
AGENT_DEFAULT_UP_TO_LEVEL = 120
DEMAND_PREDICTOR_TYPE = 'MovingAverage'


# ============================================================================
# PROFIT / COST PARAMETERS
# P_t^i = f^i * AD_t^i - (c^i * I_t^i + h_i * B_t^i)
# ============================================================================
PROFIT_PER_UNIT = 10.0
INVENTORY_HOLDING_COST = 1.0
BACKLOG_COST = 10.0


# ============================================================================
# INFORMATION SHARING SCENARIOS
# 'full': DS sees all HC + MN metrics
# 'partial': DS sees only Loss/Backlog from HCs, In-production/Demand from MNs
# 'none': DS sees only its own metrics
# ============================================================================
INFO_SHARING_SCENARIO = 'partial'


# ============================================================================
# NETWORK LEAD TIMES
# ============================================================================
PHYSICAL_LEAD_TIME = 2
INFO_LEAD_TIME = 0


# ============================================================================
# DISRUPTION (default: long disruption at MN1, strength 0.95)
# Short: 110-115  Moderate: 110-127  Long: 110-157
# ============================================================================
DISRUPTIONS = [
    {
        'type': 'LineShutDown',
        'manufacturer_index': 0,
        'num_active_lines': MN_NUM_ACTIVE_LINES,
        'happen_day_1': 110,
        'end_day_1': 157,
        'decrease_factor_1': 0.95,
        'happen_day_2': -1,
        'end_day_2': -1,
        'decrease_factor_2': 0,
    },
]


# ============================================================================
# DRL HYPERPARAMETERS
# ============================================================================
DRL_LAYER_TYPE = 'GRU'         # 'Dense' or 'GRU'
DRL_GAMMA = 0.95
DRL_ACTOR_LR = 0.01
DRL_CRITIC_LR = 0.01
DRL_ACTION_BOUND = 1.0
DRL_STD_BOUND = [1e-2, 1.0]

# Architecture
DRL_HIDDEN_SIZE = 128
DRL_DROPOUT = 0.3
DRL_GRADIENT_CLIP = 1.0
DRL_ACTOR_FC_LAYERS = 2        # FC layers after GRU in actor
DRL_CRITIC_FC_LAYERS = 3       # FC layers after GRU in critic
DRL_GRU_LR_FACTOR = 0.3       # GRU uses LR * this factor (recurrent layers need lower LR)

DRL_HISTORY_SIZE = 8
DRL_ORDER_HI = 240
DRL_ORDER_LO = 0
DRL_ALLOC_HI = 1.0
DRL_ALLOC_LO = 0.0
DRL_ACTION_LOWER_BOUND = 0.0

DRL_INVENTORY_TARGET = 120
DRL_BACKLOG_PENALTY_THRESH = 60

DRL_MAX_UPDATE_FREQ_EPISODES = 2
DRL_MAX_UPDATE_FREQ_CYCLES = 10
DRL_TRAINING_NUM = 1

DRL_PMT_LOWER = 0.5
DRL_PMT_UPPER = 1.5

# Adaptive learning rate
DRL_BETA_ALPHA = 0.05
DRL_MIN_LR = 1e-4
DRL_MAX_LR = 0.005

# Adaptive exploration rate
DRL_BETA_EPSILON = 0.005
DRL_INITIAL_EXPLORATION = 1.0
DRL_MIN_EXPLORATION = 0.1
DRL_MAX_EXPLORATION = 2.0
DRL_EXPLORATION_DECAY = 0.998

# Training warm-up: skip DRL updates for first N periods (state is incomplete)
DRL_WARMUP_STEPS = 10

DRL_REWARD_EPSILON = 50.0
DRL_ENTROPY_COEFF = 0.01       # entropy bonus in actor loss for exploration

# ----------------------------------------------------------------------------
# Reward-shaping fixes (see documentation/thesis-chapter3-summary.md +
# Reward_shaping_report-1.pdf). When DRL_REWARD_FIX is False the original
# thesis-faithful (broken/saturated) reward is used, so the two can be A/B'd.
#   r1/r4 : count true reversals of dB instead of the degenerate sign term
#   r2    : fractional fulfillment gap |delta|/demand vs DRL_REWARD_EPSILON_FRAC
#   r3    : widen in-band half-width to max(2*sigma, DRL_R3_BAND_FRAC * up-to)
#   r5    : store raw order quantity (not normalised ratio) for the slope
#   r6    : graded sign(n_in - n_out) over the window instead of all-or-nothing
# ----------------------------------------------------------------------------
DRL_REWARD_FIX = False
DRL_REWARD_EPSILON_FRAC = 0.1  # r2: tolerance as a fraction of window demand
DRL_R3_BAND_FRAC = 0.25        # r3: band half-width as a fraction of up-to-level

# Training logs (TensorFlow step logs are separate; set False for batch experiments)
DRL_VERBOSE_TRAINING = False

# Profit proxy: penalizes holding + backlog cost for the controlled DS.
DRL_EQ1_PROXY_WEIGHT = 0.15
DRL_EQ1_PROXY_SCALE = 3500.0

# Evaluation: train this many episodes unless overridden by script
EVAL_TRAIN_EPISODES = 45

# Transfer learning: pre-trained checkpoint directory (None = train from scratch)
TRANSFER_CHECKPOINT_DIR = None
TRANSFER_FREEZE_CRITIC = False
TRANSFER_FINETUNE_LR_FACTOR = 0.1  # multiply base LR by this when fine-tuning


# ============================================================================
# MAB (Multi-Armed Bandit) REWARD WEIGHTING  (Table 5 / Algorithm 2)
# ============================================================================
REWARD_NUM_COMPONENTS = 6
MAB_REWARD_ARMS = [
    [1.0, 1.0, 1.0, 1.0, 1.0, 1.0],      # Arm 1: equal
    [2.0, 1.0, 1.0, 1.0, 1.0, 1.0],      # Arm 2: r1 (HC backlog) 2w
    [1.0, 2.0, 1.0, 1.0, 1.0, 1.0],      # Arm 3: r2 (order fulfillment) 2w
    [1.0, 1.0, 2.0, 1.0, 1.0, 1.0],      # Arm 4: r3 (inv stability) 2w
    [1.0, 1.0, 1.0, 2.0, 1.0, 1.0],      # Arm 5: r4 (DS backlog) 2w
    [1.0, 1.0, 1.0, 1.0, 2.0, 1.0],      # Arm 6: r5 (action stability) 2w
    [1.0, 1.0, 1.0, 1.0, 1.0, 2.0],      # Arm 7: r6 (MN alignment) 2w
    [1.0, 1.0, 1.0, 1.0, 0.5, 1.0],      # Arm 8: r5 half weight 0.5w
]
MAB_WINDOW_SIZE = 8
MAB_THRESHOLD = 5.0
MAB_DECAY_FACTOR = 0.5


# ============================================================================
# DRL STATE OBSERVATION CONFIG
# ============================================================================
HC_STATE_METRICS = ['Loss', 'Backlog']
DS_STATE_METRICS = ['Backlog', 'Inventory-Level', 'Order', 'Delivery',
                    'Inventory', 'On-Order', 'Demand', 'Lead-time', 'Up-to-level']
MN_STATE_METRICS = ['In production', 'Demand']

HC_ALL_METRICS = ['Inventory', 'Demand', 'Loss', 'Backlog', 'Order',
                  'Up-to-level', 'Lead-time', 'On-Order']
MN_ALL_METRICS = ['Inventory', 'Backlog', 'In production', 'Up-to-level',
                  'Demand', 'Lead-time']


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
def build_state_config():
    """Build the State_Config dict dynamically from topology and info-sharing scenario."""
    cfg = {}
    if INFO_SHARING_SCENARIO == 'full':
        hc_metrics = list(HC_ALL_METRICS)
        mn_metrics = list(MN_ALL_METRICS)
    elif INFO_SHARING_SCENARIO == 'none':
        hc_metrics = []
        mn_metrics = []
    else:
        hc_metrics = list(HC_STATE_METRICS)
        mn_metrics = list(MN_STATE_METRICS)

    for i in range(1, N_HC + 1):
        cfg[f'HC {i}'] = list(hc_metrics)
    for i in range(1, N_DS + 1):
        cfg[f'DS {i}'] = list(DS_STATE_METRICS)
    for i in range(1, N_MN + 1):
        cfg[f'MN {i}'] = list(mn_metrics)
    return cfg


def get_ds_connected_hcs(ds_index):
    return sorted(set(hc for ds, hc in DS_HC_LINKS if ds == ds_index))


def get_ds_connected_mns(ds_index):
    return sorted(set(mn for mn, ds in MN_DS_LINKS if ds == ds_index))


def get_hc_connected_dss(hc_index):
    return sorted(set(ds for ds, hc in DS_HC_LINKS if hc == hc_index))


def get_mn_connected_dss(mn_index):
    return sorted(set(ds for mn, ds in MN_DS_LINKS if mn == mn_index))


def get_num_actions_for_ds(ds_index):
    return 1 + len(get_ds_connected_hcs(ds_index))


# ============================================================================
# REPRODUCIBILITY & CALIBRATION
# ============================================================================
RANDOM_SEED = 42

def set_global_seeds(seed=None):
    """Set all random seeds for reproducible experiments."""
    import numpy as _np
    import random as _random
    s = seed if seed is not None else RANDOM_SEED
    _random.seed(s)
    _np.random.seed(s)
    try:
        import tensorflow as _tf
        _tf.random.set_seed(s)
    except ImportError:
        pass


def snapshot_config():
    """Return a dict of all non-private, non-callable config values for logging."""
    import types
    snap = {}
    for k, v in globals().items():
        if k.startswith('_') or callable(v) or isinstance(v, types.ModuleType):
            continue
        try:
            json.dumps(v)
            snap[k] = v
        except (TypeError, ValueError):
            snap[k] = str(v)
    return snap


def save_config_snapshot(directory):
    """Save a JSON snapshot of all config parameters for experiment reproducibility."""
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, 'config_snapshot.json')
    with open(path, 'w') as f:
        json.dump(snapshot_config(), f, indent=2, sort_keys=True)
    return path


def save_run_seed_metadata(directory, seed_applied=None):
    """Record which seed was passed to set_global_seeds (may differ from RANDOM_SEED in snapshot)."""
    os.makedirs(directory, exist_ok=True)
    applied = int(seed_applied if seed_applied is not None else RANDOM_SEED)
    path = os.path.join(directory, 'run_seed.json')
    with open(path, 'w') as f:
        json.dump({
            'run_seed_applied': applied,
            'config_module_RANDOM_SEED': RANDOM_SEED,
        }, f, indent=2, sort_keys=True)
    return path


def load_config_from_snapshot(path):
    """Load config values from a previously saved snapshot (for exact reproduction)."""
    with open(path, 'r') as f:
        snap = json.load(f)
    g = globals()
    for k, v in snap.items():
        if k in g and not k.startswith('_') and not callable(g.get(k)):
            g[k] = v
