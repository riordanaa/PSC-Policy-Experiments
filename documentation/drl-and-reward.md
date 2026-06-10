# DRL model, reward, and adaptive mechanisms

This covers `model_a2c.py` (the network) and `ds_world.py` (the environment, reward, MAB, and training loop). One `DsWorld` instance exists per DRL distributor.

## A2C model (`model_a2c.py`)

Advantage Actor-Critic with two networks built by `Actor` and `Critic`, combined in `a2c_Model`. Keras global float dtype is forced to `float64` (`tf.keras.backend.set_floatx('float64')`).

Both networks branch on `layer_type` (`'Dense'` or `'GRU'`, from `config.DRL_LAYER_TYPE`) inside `create_model()`:

- **GRU path**: `Input(seq_len, state_dim)` → `TimeDistributed(Dense(relu))` → `GRU(relu)` → `Dropout` → `DRL_ACTOR_FC_LAYERS` dense layers → a `tanh` "attention" dense layer → outputs.
- **Dense path**: `Input(state_dim)` → dense → `DRL_ACTOR_FC_LAYERS + 1` dense layers → `Dropout` → `tanh` attention → outputs. (The extra FC layer replaces the GRU.)

**Actor outputs** `(mu, std)`: `mu` is `tanh × action_bound`, `std` is `softplus` (clamped to `DRL_STD_BOUND`). Actions are sampled from the resulting Gaussian. **Critic** outputs a scalar state value (linear).

Architecture knobs come from config: `DRL_HIDDEN_SIZE` (128), `DRL_DROPOUT` (0.3), `DRL_GRADIENT_CLIP` (1.0), `DRL_ACTOR_FC_LAYERS`/`DRL_CRITIC_FC_LAYERS`, `DRL_ENTROPY_COEFF` (entropy bonus added to the actor loss). GRU layers use a reduced effective learning rate via `DRL_GRU_LR_FACTOR`. Optimizers are Adam; gradients are clipped.

## Action semantics

The action vector has length `1 + (#connected HCs)`:

- Index `0`: **order quantity**, scaled from the network's `[-1, 1]` range into `[DRL_ORDER_LO, DRL_ORDER_HI]` (0–240).
- Indices `1..N`: **allocation ratios** to each connected health center, in `[DRL_ALLOC_LO, DRL_ALLOC_HI]` (0–1), applied by `allocate_drl` in `decision_maker.py`.

## State representation

`DRLDSDecisionMaker.get_states()` assembles a flat per-period state from the live agent metrics of the distributor, its connected HCs, and its connected MN — restricted to the metrics enabled by `INFO_SHARING_SCENARIO` (via `build_state_config()`). `DsWorld` keeps a **sliding window of `DRL_HISTORY_SIZE` (=8) periods**; for the GRU this is the time axis, for Dense it is flattened.

`RunningNormalizer` (`ds_world.py:17`) applies Welford online mean/variance normalization with clipping (±5σ) to stabilize inputs. Its statistics are persisted alongside weights as `*_normalizer.npz` and must be restored with the checkpoint.

`DRL_WARMUP_STEPS` (10) skips DRL updates for the first periods of an episode while the window is still filling and state is incomplete.

## Reward: six components

Computed in `DsWorld.step_reward(done)` (`ds_world.py:392`). Each component lands in `self.reward_arr[0..5]`; most are sign-valued in `{-1, 0, +1}`.

| # | Name | Definition (as implemented) |
|---|------|------------------------------|
| R1 | HC backlog balance | Mean over connected HCs of `_compute_backlog_balance(HC backlog trend)`. |
| R2 | Order fulfillment | `sign(ε − |delivered − demand|)` over the DS window; ε = `DRL_REWARD_EPSILON` (50). +1 when delivery tracks demand within ε. |
| R3 | Inventory stability | Count periods where DS inventory sits inside `up_to_level ± 2σ`; reward = `sign(in − out)`. |
| R4 | DS backlog balance | `_compute_backlog_balance(DS backlog trend)`. |
| R5 | Action stability | `sign(1 − |β₁|)` where β₁ is the linear slope of recent order actions. Rewards a flat ordering trajectory. |
| R6 | MN demand alignment | +1 if every observed MN's `production/demand` ratio is within `[DRL_PMT_LOWER, DRL_PMT_UPPER]` (0.5–1.5), else −1. |

**Weighted total:** `reward = Σ arm_weight[i] · reward_arr[i]`, where `arm_weight` is the MAB-selected vector (below).

**Profit proxy:** if `DRL_EQ1_PROXY_WEIGHT > 0`, an additional term penalizes DS holding + backlog cost (scaled by `DRL_EQ1_PROXY_SCALE`), nudging the reward toward the economic objective.

> **Known caveat (documented in the r5 diagnostic):** R5's `sign(1 − |β₁|)` fires +1 ~100% of the time and barely changes during a disruption — it does not discriminate good from bad states. See `r5_test_results/r5_findings.md` and [plotting-and-diagnostics.md](plotting-and-diagnostics.md). Arm 8 in `MAB_REWARD_ARMS` exists to down-weight R5.

## MAB reward weighting — UCB-P (`UCBPBandit`, `ds_world.py:40`)

"Upper Confidence Bound with Predefined arms and change detection." Each **arm** is one of the `MAB_REWARD_ARMS` weight vectors. Per step:

- `select_arm()` — forces a round-robin exploration cycle of length `ceil(K/γ)` (γ = `MAB_DECAY_FACTOR`), then otherwise picks `argmax(mean_reward + sqrt(2·ln t / n))`.
- `update(arm, reward)` — accumulates reward; over the last `MAB_WINDOW_SIZE` (8) pulls of an arm, compares the first vs second half average and **resets all statistics** if the gap exceeds `MAB_THRESHOLD` (5.0). This is the change-detection that lets the bandit re-adapt after a disruption.

Disabling the MAB (Study 3 ablation) means using a single equal-weight arm.

## Adaptive learning rate & exploration

Both are driven by TD-error magnitude (the critic's surprise):

- **Learning rate** scales between `DRL_MIN_LR` and `DRL_MAX_LR` with sensitivity `DRL_BETA_ALPHA` — larger TD error → larger LR.
- **Exploration** (the sampled-action noise scale) moves between `DRL_MIN_EXPLORATION` and `DRL_MAX_EXPLORATION` with sensitivity `DRL_BETA_EPSILON`, decayed by `DRL_EXPLORATION_DECAY` each step from `DRL_INITIAL_EXPLORATION`.

## Training loop

`DsWorld.take_actions()` (`ds_world.py:684`) drives action selection per period; `update_drls()` (`ds_world.py:658`) runs the A2C update (advantage = reward + γ·V(next) − V(current); actor + critic gradient steps with entropy bonus and gradient clipping). Update cadence is bounded by `DRL_MAX_UPDATE_FREQ_EPISODES` / `DRL_MAX_UPDATE_FREQ_CYCLES`.

## Checkpoints (`save_checkpoint` / `load_checkpoint`, `ds_world.py:265`)

A checkpoint directory holds, per DS agent:

- `DS_<n>_actor.weights.h5`, `DS_<n>_critic.weights.h5` — Keras weights.
- `DS_<n>_normalizer.npz` — running normalization statistics.
- `training_state.json` — episode counter, exploration/LR state, MAB state.

`load_checkpoint(dir, freeze_critic=...)` warm-starts and optionally freezes the critic. Transfer learning (`TRANSFER_CHECKPOINT_DIR`) loads a checkpoint and rescales the LR by `TRANSFER_FINETUNE_LR_FACTOR` for fine-tuning. **Checkpoints are tied to the state/action dimensions** — i.e. the topology and `INFO_SHARING_SCENARIO` must match.
