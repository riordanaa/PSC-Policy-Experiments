import math
import numpy as np
from model_a2c import a2c_Model
import copy
from scipy import stats
import os
import config

State_Config = config.build_state_config()
reward_arms = config.MAB_REWARD_ARMS


def sigmoid(x, c1, c2):
    return 1.0 / (1.0 + np.exp(-c1 * (x - c2)))


class RunningNormalizer:
    """Welford's online algorithm for running mean/variance normalization."""

    def __init__(self, size, clip=5.0):
        self.mean = np.zeros(size, dtype=np.float64)
        self.var = np.ones(size, dtype=np.float64)
        self.count = 0
        self.clip = clip

    def update(self, x):
        x = np.asarray(x, dtype=np.float64)
        self.count += 1
        delta = x - self.mean
        self.mean += delta / self.count
        delta2 = x - self.mean
        self.var += (delta * delta2 - self.var) / max(2, self.count)

    def normalize(self, x):
        x = np.asarray(x, dtype=np.float64)
        std = np.sqrt(self.var + 1e-8)
        return np.clip((x - self.mean) / std, -self.clip, self.clip)


class UCBPBandit:
    """Upper Confidence Bound with Predefined arms and Change Detection (Algorithm 2)."""

    def __init__(self, arms, window_size, threshold, decay_factor):
        self.arms = arms
        self.K = len(arms)
        self.w = max(2, window_size)
        self.b = threshold
        self.gamma = max(0.01, decay_factor)
        self.tau = 0
        self.t = 0
        self.n = [0] * self.K
        self.reward_sums = [0.0] * self.K
        self.reward_history = [[] for _ in range(self.K)]

    def _reset_on_change(self):
        self.tau = self.t
        self.n = [0] * self.K
        self.reward_sums = [0.0] * self.K
        self.reward_history = [[] for _ in range(self.K)]

    def select_arm(self):
        self.t += 1
        local_t = self.t - self.tau
        cycle_len = max(1, math.ceil(self.K / self.gamma))
        explore_idx = (local_t - 1) % cycle_len

        if explore_idx < self.K:
            return explore_idx

        best_arm = 0
        best_ucb = -float('inf')
        for a in range(self.K):
            if self.n[a] == 0:
                return a
            mean_r = self.reward_sums[a] / self.n[a]
            bonus = math.sqrt(2.0 * math.log(max(1, local_t)) / self.n[a])
            ucb = mean_r + bonus
            if ucb > best_ucb:
                best_ucb = ucb
                best_arm = a
        return best_arm

    def update(self, arm, reward):
        self.n[arm] += 1
        self.reward_sums[arm] += reward
        self.reward_history[arm].append(reward)

        if self.n[arm] >= self.w:
            recent = self.reward_history[arm][-self.w:]
            half = self.w // 2
            first_avg = sum(recent[:half]) / max(1, half)
            second_avg = sum(recent[half:]) / max(1, half)
            if abs(first_avg - second_avg) > self.b:
                self._reset_on_change()

    def get_weights(self, arm):
        return list(self.arms[arm % self.K])

    def get_arm_counts(self):
        return self.n.copy()


class DsWorld():
    def __init__(self, isTest=False, training_num=None,
                 Layer_Type=None, DS_Id='DS 1', useNet=False,
                 init_with_last_state=False, total_episodes=None):
        if training_num is None:
            training_num = config.DRL_TRAINING_NUM
        if Layer_Type is None:
            Layer_Type = config.DRL_LAYER_TYPE
        if total_episodes is None:
            total_episodes = config.TOTAL_EPISODES

        self.arm = None
        self.config_state = config.build_state_config()
        self.ds_id = DS_Id
        ds_index = int(self.ds_id.split()[-1]) - 1
        connected_mns = config.get_ds_connected_mns(ds_index)
        self.mn_id = f'MN {connected_mns[0] + 1}' if connected_mns else 'MN 1'

        for i in range(1, config.N_DS + 1):
            if i != ds_index + 1:
                self.config_state[f'DS {i}'] = []
        for i in range(1, config.N_MN + 1):
            if (i - 1) not in connected_mns:
                self.config_state[f'MN {i}'] = []
        self.pmt_lower = config.DRL_PMT_LOWER
        self.pmt_upper = config.DRL_PMT_UPPER
        self.state_dict = {}
        self.period = 0
        self.init_period = 0
        self.lst_prd = 0
        self.history_size = config.DRL_HISTORY_SIZE
        self._get_observation_size()
        self.abstract_state = [0] * self.num_observations
        self.state_size = self.num_observations * self.history_size
        self.prev_obs = [0] * self.state_size
        self.istest = isTest
        self.layer_type = Layer_Type
        self.useNet = useNet
        self.checkpoint_path = 'training_' + str(training_num) + '_' + str(os.getpid()) + '/'
        os.makedirs(self.checkpoint_path, exist_ok=True)
        self.actor_path = (self.checkpoint_path + self.ds_id
                           + '_actor.weights.h5')
        self.critic_path = (self.checkpoint_path + self.ds_id
                            + '_critic.weights.h5')

        ds_index = int(self.ds_id.split()[-1]) - 1
        self.num_actions = config.get_num_actions_for_ds(ds_index)
        self.orders_to_receive = []
        self.order_received = False

        self.state = [0] * self.state_size
        self.next_state = [0] * self.state_size

        self.actions = [0] * self.num_actions
        self.last_actions = []
        self.drl_actions = []

        self.reward = 0

        self.state_normalizer = RunningNormalizer(self.state_size)
        self.reward_normalizer = RunningNormalizer(1)

        self.action_upper_bound = config.DRL_ACTION_BOUND
        self.action_lower_bound = config.DRL_ACTION_LOWER_BOUND
        self.action_multip = 0.7

        self.order_hi = config.DRL_ORDER_HI
        self.order_lo = config.DRL_ORDER_LO
        self.alloc_hi = config.DRL_ALLOC_HI
        self.alloc_lo = config.DRL_ALLOC_LO
        self.lead_time = np.array([])
        self.demand = np.array([])
        self.up_to_level = np.array([])
        self.on_order = np.array([])
        self.delivery = np.array([])
        self.inventory = 0
        self.backlog = 0

        self.state_batch = []
        self.ds_action_batch = []
        self.ds_td_target_batch = []
        self.ds_advantage_batch = []

        gru_lr_factor = getattr(config, 'DRL_GRU_LR_FACTOR', 0.3)
        actor_lr = config.DRL_ACTOR_LR
        critic_lr = config.DRL_CRITIC_LR
        if self.layer_type == 'GRU':
            actor_lr *= gru_lr_factor
            critic_lr *= gru_lr_factor

        self.ds_agent = a2c_Model(
            state_dim=self.state_size, action_dim=self.num_actions,
            action_bound=self.action_upper_bound, gamma=config.DRL_GAMMA,
            actor_lr=actor_lr, critic_lr=critic_lr,
            training_num=training_num,
            isTest=self.istest, Layer_Type=self.layer_type, useNet=self.useNet,
            Paths=[self.actor_path, self.critic_path],
            history_size=self.history_size,
            obs_per_step=self.num_observations)

        self.episode_count = 0
        self.max_update_frequency_episodes = config.DRL_MAX_UPDATE_FREQ_EPISODES
        self.update_cycle_count = 0
        self.max_update_frequency = config.DRL_MAX_UPDATE_FREQ_CYCLES

        self.init_with_last_state = init_with_last_state
        self.last_state = None
        self.current_episode = 0
        self.total_episodes = total_episodes

        # Exploration rate
        self.exploration_rate = config.DRL_INITIAL_EXPLORATION

        # If not None, reset() restores actor/critic LRs to these (transfer fine-tuning)
        self._per_episode_actor_lr = None
        self._per_episode_critic_lr = None

        # UCB-P Bandit (Algorithm 2)
        self.bandit = UCBPBandit(
            arms=config.MAB_REWARD_ARMS,
            window_size=config.MAB_WINDOW_SIZE,
            threshold=config.MAB_THRESHOLD,
            decay_factor=config.MAB_DECAY_FACTOR,
        )
        self.selected_arm = self.bandit.select_arm()
        self.arm_weight = self.bandit.get_weights(self.selected_arm)
        self.reward_arr = [0.0] * config.REWARD_NUM_COMPONENTS
        self.reward_num = config.REWARD_NUM_COMPONENTS
        self.do_reset = True
        self.r5_log = []
        self.r5_log_enabled = False

        if self.init_with_last_state:
            self._initialize_with_last_state()

    def set_per_episode_learning_rates(self, actor_lr, critic_lr):
        """Pin optimizer LRs restored at each episode reset (e.g. transfer fine-tuning)."""
        self._per_episode_actor_lr = float(actor_lr)
        self._per_episode_critic_lr = float(critic_lr)

    def clear_per_episode_learning_rates(self):
        """Use config DRL_ACTOR_LR / DRL_CRITIC_LR again after every reset."""
        self._per_episode_actor_lr = None
        self._per_episode_critic_lr = None

    def _initialize_with_last_state(self):
        if not os.path.exists('last_state.txt'):
            with open('last_state.txt', 'w') as file:
                file.write('')
        try:
            with open('last_state.txt', 'r') as file:
                last_state_str = file.read()
                if last_state_str:
                    self.last_state = [float(x)
                                       for x in last_state_str.split(',')]
                    self.state = self.last_state
                else:
                    print("No saved state found. "
                          "Starting with default initial state.")
        except FileNotFoundError:
            print("No saved state found. Starting with default initial state.")

    def save_checkpoint(self, directory):
        """Save actor/critic weights and normalizer state for transfer learning."""
        os.makedirs(directory, exist_ok=True)
        safe_id = self.ds_id.replace(' ', '_')
        actor_dst = os.path.join(directory, f'{safe_id}_actor.weights.h5')
        critic_dst = os.path.join(directory, f'{safe_id}_critic.weights.h5')
        self.ds_agent.actor.model.save_weights(actor_dst)
        self.ds_agent.critic.model.save_weights(critic_dst)
        norm_path = os.path.join(directory, f'{safe_id}_normalizer.npz')
        np.savez(norm_path,
                 s_mean=self.state_normalizer.mean,
                 s_var=self.state_normalizer.var,
                 s_count=np.array([self.state_normalizer.count]),
                 r_mean=self.reward_normalizer.mean,
                 r_var=self.reward_normalizer.var,
                 r_count=np.array([self.reward_normalizer.count]))

    def load_checkpoint(self, directory, freeze_critic=False):
        """Load actor/critic weights from a previous training run (transfer learning).

        Args:
            directory: path containing saved weights
            freeze_critic: if True, freeze critic layers so only the actor fine-tunes
        """
        safe_id = self.ds_id.replace(' ', '_')
        actor_src = os.path.join(directory, f'{safe_id}_actor.weights.h5')
        critic_src = os.path.join(directory, f'{safe_id}_critic.weights.h5')
        if os.path.exists(actor_src):
            self.ds_agent.actor.model.load_weights(actor_src)
        else:
            print(f"Transfer: actor weights not found at {actor_src}")
        if os.path.exists(critic_src):
            self.ds_agent.critic.model.load_weights(critic_src)
        else:
            print(f"Transfer: critic weights not found at {critic_src}")
        if freeze_critic:
            for layer in self.ds_agent.critic.model.layers:
                layer.trainable = False
        norm_path = os.path.join(directory, f'{safe_id}_normalizer.npz')
        if os.path.exists(norm_path):
            data = np.load(norm_path)
            self.state_normalizer.mean = data['s_mean']
            self.state_normalizer.var = data['s_var']
            self.state_normalizer.count = int(data['s_count'][0])
            self.reward_normalizer.mean = data['r_mean']
            self.reward_normalizer.var = data['r_var']
            self.reward_normalizer.count = int(data['r_count'][0])

    def _update_hist(self, new_obs):
        for obs_num in range(self.num_observations):
            self.prev_obs.pop(0)
            self.prev_obs.append(new_obs[obs_num])

    def reset(self):
        self.current_episode += 1

        if self.current_episode == self.total_episodes:
            with open('last_state.txt', 'w') as file:
                file.write(','.join(map(str, self.state)))

        if self.init_with_last_state and self.last_state is not None:
            self.state = self.last_state.copy()
        else:
            self.state = [0] * self.state_size

        self.next_state = [0] * self.state_size
        self.actions = [0] * self.num_actions
        self.drl_actions = []
        self.orders_to_receive = []
        self.order_received = False
        self.reward = 0
        self.last_actions = []

        self.state_batch = []
        self.ds_action_batch = []
        self.ds_td_target_batch = []
        self.ds_advantage_batch = []

        self.episode_count = 0
        self.update_cycle_count = 0

        # Reset per-episode reward array but NOT the bandit (persists across episodes)
        self.reward_arr = [0.0] * config.REWARD_NUM_COMPONENTS

        # Reset learning rate each episode to baseline (or fine-tune pins for transfer)
        if not self.istest and hasattr(self.ds_agent.actor, 'opt'):
            ar = (self._per_episode_actor_lr if self._per_episode_actor_lr is not None
                  else config.DRL_ACTOR_LR)
            cr = (self._per_episode_critic_lr if self._per_episode_critic_lr is not None
                  else config.DRL_CRITIC_LR)
            self.ds_agent.actor.opt.learning_rate.assign(ar)
            self.ds_agent.critic.opt.learning_rate.assign(cr)
        self.exploration_rate = config.DRL_INITIAL_EXPLORATION

    def _select_state(self, agent, state_name):
        all_state_idx = np.array([])
        for prd in self.state_dict:
            try:
                val = self.state_dict[prd][agent][state_name]
                all_state_idx = np.append(all_state_idx, val)
            except (KeyError, TypeError):
                pass
        return all_state_idx

    def _get_trend(self, npstate):
        x = range(0, len(npstate))
        y = npstate
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
        return slope, intercept, r_value, p_value, std_err

    def _compute_backlog_balance(self, backlog_values):
        """Backlog balance metric applied to a backlog time-series."""
        if len(backlog_values) < 2:
            return 0.0
        delta_b = np.diff(backlog_values)
        term1 = -float(np.sign(np.sum(delta_b)))
        if len(delta_b) >= 2:
            fluct_sum = 0.0
            for j in range(len(delta_b) - 1):
                if getattr(config, 'DRL_REWARD_FIX', False):
                    # Count true direction reversals of the backlog deltas.
                    # |sign(dB[j+1]) - sign(dB[j])| = 2 on a reversal, 0 otherwise.
                    fluct_sum += abs(float(np.sign(delta_b[j + 1]))
                                    - float(np.sign(delta_b[j])))
                else:
                    # Original (thesis Eq. 3.13 as printed): degenerate, since
                    # |sign(d) - sign(-d)| is always 2 (or 0), pinning term2 = -1.
                    diff = delta_b[j + 1] - delta_b[j]
                    fluct_sum += abs(float(np.sign(diff))
                                    - float(np.sign(-diff)))
            term2 = float(np.sign(1.0 - fluct_sum))
        else:
            term2 = 0.0
        return term1 + term2 - 1.0

    def step_reward(self, done):
        current_state = np.reshape(self.state, [1, self.state_size])
        if len(self.drl_actions) == 0:
            ds_actions = np.zeros([1, self.num_actions])
        else:
            ds_actions = np.reshape(self.drl_actions, [1, self.num_actions])
        self.reward = 0

        if self.order_received:
            self.orders_to_receive.pop(0)
            self.orders_to_receive.append(self.actions[0])
        else:
            self.orders_to_receive.append(self.actions[0])

        next_state = np.reshape(self.next_state, [1, self.state_size])

        # ---- R1: HC Backlog Balance ----
        self.reward_arr[0] = 0.0
        hc_count = 0
        for hc_i in range(1, config.N_HC + 1):
            hc_key = f'HC {hc_i}'
            if len(self.config_state.get(hc_key, [])) == 0:
                continue
            try:
                hc_backlog = self._select_state(hc_key, 'Backlog')
                if len(hc_backlog) >= 2:
                    self.reward_arr[0] += self._compute_backlog_balance(
                        hc_backlog)
                    hc_count += 1
            except (KeyError, IndexError):
                pass
        if hc_count > 0:
            self.reward_arr[0] /= hc_count

        # ---- R2: Order Fulfillment ----
        self.reward_arr[1] = 0.0
        _r2_total_demand = 0.0
        _r2_total_delivered = 0.0
        try:
            demand_states = self._select_state(self.ds_id, 'Demand')
            received_states = self._select_state(self.ds_id, 'Delivery')
            _r2_total_demand = float(sum(demand_states))
            _r2_total_delivered = float(sum(received_states))
            _r2_gap = abs(_r2_total_delivered - _r2_total_demand)
            if getattr(config, 'DRL_REWARD_FIX', False):
                # Fractional gap: tolerance scales with demand, so the reward
                # stays reachable instead of saturating at -1 (eps=50 vs ~500).
                eps_frac = getattr(config, 'DRL_REWARD_EPSILON_FRAC', 0.1)
                self.reward_arr[1] = float(
                    np.sign(eps_frac - _r2_gap / max(1.0, _r2_total_demand)))
            else:
                epsilon = config.DRL_REWARD_EPSILON
                self.reward_arr[1] = float(np.sign(epsilon - _r2_gap))
        except (KeyError, IndexError):
            pass

        # ---- R3: Inventory Level Stability ----
        self.reward_arr[2] = 0.0
        _r3_utl_last, _r3_utl_std, _r3_inv_last = 0.0, 0.0, 0.0
        _r3_n_in, _r3_n_out = 0, 0
        try:
            inventory_states = self._select_state(self.ds_id, 'Inventory')
            up_to_states = self._select_state(self.ds_id, 'Up-to-level')
            if len(inventory_states) >= 2 and len(up_to_states) >= 2:
                utl_std = (np.std(up_to_states)
                           if len(up_to_states) > 1 else 0.0)
                utl_std = max(utl_std, 1.0)
                _r3_utl_std = float(utl_std)
                _r3_utl_last = float(up_to_states[-1])
                _r3_inv_last = float(inventory_states[-1])
                n_check = min(len(inventory_states), len(up_to_states))
                count = 0
                _r3_band_frac = getattr(config, 'DRL_R3_BAND_FRAC', 0.25)
                for j in range(n_check):
                    if getattr(config, 'DRL_REWARD_FIX', False):
                        # Widen the band so it isn't pinned to ~[118,122] when
                        # sigma hits its floor of 1; gives the agent room to be
                        # "in band" instead of r3 collapsing to a constant -1.
                        half_width = max(2.0 * utl_std,
                                         _r3_band_frac * up_to_states[j])
                    else:
                        half_width = 2.0 * utl_std
                    upper = up_to_states[j] + half_width
                    lower = up_to_states[j] - half_width
                    if lower < inventory_states[j] < upper:
                        count += 1
                        _r3_n_in += 1
                    else:
                        count -= 1
                        _r3_n_out += 1
                self.reward_arr[2] = float(np.sign(count))
        except (KeyError, IndexError):
            pass

        # ---- R4: DS Backlog Balance ----
        self.reward_arr[3] = 0.0
        try:
            backlog_states = self._select_state(self.ds_id, 'Backlog')
            if len(backlog_states) >= 2:
                self.reward_arr[3] = self._compute_backlog_balance(
                    backlog_states)
        except (KeyError, IndexError):
            pass

        # ---- R5: Action Stability ----
        self.reward_arr[4] = 0.0
        _r5_slope = 0.0
        if len(self.last_actions) >= 3:
            try:
                order_actions = np.array([a[0] for a in self.last_actions])
                slope, _, _, _, _ = self._get_trend(order_actions)
                _r5_slope = float(slope)
                self.reward_arr[4] = float(np.sign(1.0 - abs(slope)))
            except Exception:
                pass

        # ---- R6: MN Demand Alignment ----
        self.reward_arr[5] = 0.0
        if getattr(config, 'DRL_REWARD_FIX', False):
            # Graded: count in-band vs out-of-band periods and return
            # sign(n_in - n_out). Avoids the all-or-nothing collapse where a
            # single out-of-band period (common in warm-up/disruption) pins -1.
            _r6_n_in, _r6_n_out = 0, 0
            for prd_key in self.state_dict:
                try:
                    mn_data = self.state_dict[prd_key].get(self.mn_id, {})
                    mn_prod = mn_data.get('In production', 0)
                    mn_demand = mn_data.get('Demand', 0)
                    if mn_demand > 0:
                        ratio = mn_prod / mn_demand
                        if self.pmt_lower <= ratio <= self.pmt_upper:
                            _r6_n_in += 1
                        else:
                            _r6_n_out += 1
                except (KeyError, TypeError):
                    pass
            self.reward_arr[5] = float(np.sign(_r6_n_in - _r6_n_out))
            all_ok = (_r6_n_out == 0)  # for diagnostic logging compatibility
        else:
            all_ok = True
            for prd_key in self.state_dict:
                try:
                    mn_data = self.state_dict[prd_key].get(self.mn_id, {})
                    mn_prod = mn_data.get('In production', 0)
                    mn_demand = mn_data.get('Demand', 0)
                    if mn_demand > 0:
                        ratio = mn_prod / mn_demand
                        if not (self.pmt_lower <= ratio <= self.pmt_upper):
                            all_ok = False
                            break
                except (KeyError, TypeError):
                    pass
            self.reward_arr[5] = 1.0 if all_ok else -1.0

        # Capture latest-period MN snapshot for diagnostic logging
        _r6_mn_prod_last, _r6_mn_demand_last, _r6_ratio_last = 0.0, 0.0, 0.0
        try:
            _latest_mn = self.state_dict.get(str(self.lst_prd), {}).get(self.mn_id, {})
            _r6_mn_prod_last = float(_latest_mn.get('In production', 0))
            _r6_mn_demand_last = float(_latest_mn.get('Demand', 0))
            _r6_ratio_last = (_r6_mn_prod_last / _r6_mn_demand_last
                              if _r6_mn_demand_last > 0 else 0.0)
        except (KeyError, AttributeError, TypeError, ValueError):
            pass

        # ---- Diagnostic logging: all 6 rewards + their input variables ----
        if self.r5_log_enabled:
            _bl = self._select_state(self.ds_id, 'Backlog')
            _inv = self._select_state(self.ds_id, 'Inventory-Level')
            _hc1_bl = self._select_state('HC 1', 'Backlog')
            _hc2_bl = self._select_state('HC 2', 'Backlog')
            self.r5_log.append({
                'period': int(self.lst_prd),
                'ds_id': self.ds_id,
                'episode': int(self.current_episode),
                # Rewards
                'r1': self.reward_arr[0], 'r2': self.reward_arr[1],
                'r3': self.reward_arr[2], 'r4': self.reward_arr[3],
                'r5': self.reward_arr[4], 'r6': self.reward_arr[5],
                # r5 inputs
                'beta1': _r5_slope,
                'order_action': float(self.last_actions[-1][0]) if self.last_actions else 0.0,
                # r1, r4 inputs (state snapshots)
                'ds_backlog': float(_bl[-1]) if len(_bl) else 0.0,
                'ds_inventory': float(_inv[-1]) if len(_inv) else 0.0,
                'hc1_backlog': float(_hc1_bl[-1]) if len(_hc1_bl) else 0.0,
                'hc2_backlog': float(_hc2_bl[-1]) if len(_hc2_bl) else 0.0,
                # r2 inputs
                'r2_total_demand': _r2_total_demand,
                'r2_total_delivered': _r2_total_delivered,
                'r2_delivery_gap': _r2_total_delivered - _r2_total_demand,
                'r2_epsilon': float(config.DRL_REWARD_EPSILON),
                # r3 inputs
                'r3_inv_last': _r3_inv_last,
                'r3_utl_last': _r3_utl_last,
                'r3_utl_std': _r3_utl_std,
                'r3_n_in_band': _r3_n_in,
                'r3_n_out_band': _r3_n_out,
                # r6 inputs
                'r6_mn_prod': _r6_mn_prod_last,
                'r6_mn_demand': _r6_mn_demand_last,
                'r6_ratio': _r6_ratio_last,
                'r6_all_ok': int(all_ok),
                'r6_pmt_lower': float(self.pmt_lower),
                'r6_pmt_upper': float(self.pmt_upper),
            })

        # ---- Weighted reward using current arm weights ----
        self.reward = sum(
            w * r for w, r in zip(self.arm_weight, self.reward_arr))

        # ---- Profit proxy (DS backlog + inventory cost) ----
        eq1_w = getattr(config, 'DRL_EQ1_PROXY_WEIGHT', 0.0)
        if eq1_w > 0.0:
            try:
                bl_seq = self._select_state(self.ds_id, 'Backlog')
                inv_seq = self._select_state(self.ds_id, 'Inventory-Level')
                b_now = float(bl_seq[-1]) if len(bl_seq) else 0.0
                i_now = float(inv_seq[-1]) if len(inv_seq) else 0.0
                scale_den = max(
                    1.0, getattr(config, 'DRL_EQ1_PROXY_SCALE', 3500.0))
                proxy = -(config.BACKLOG_COST * b_now
                          + config.INVENTORY_HOLDING_COST * i_now) / scale_den
                proxy = float(np.clip(proxy, -2.5, 2.5))
                self.reward += eq1_w * proxy
            except (KeyError, IndexError, TypeError, ValueError):
                pass

        # ---- MAB: update bandit with observed reward, select next arm ----
        self.bandit.update(self.selected_arm, self.reward)
        self.selected_arm = self.bandit.select_arm()
        self.arm_weight = self.bandit.get_weights(self.selected_arm)

        if getattr(config, 'DRL_VERBOSE_TRAINING', False):
            print()

        # ---- Normalize reward for stable training ----
        self.reward_normalizer.update([self.reward])
        normalized_reward = float(
            self.reward_normalizer.normalize([self.reward])[0])

        # ---- TD target & advantage ----
        ds_reward = np.reshape(normalized_reward, [1, 1])
        ds_td_target = self.ds_agent.td_target(ds_reward, next_state, done)

        if self.layer_type == 'GRU':
            current_state = np.array(current_state)
            num_states = current_state.size // self.state_size
            if num_states == 0:
                num_states = 1
            state = np.reshape(
                current_state, [num_states, 1, self.state_size])
            state = state.astype(np.float64)
            ds_advantage = self.ds_agent.advantage(
                ds_td_target,
                self.ds_agent.critic.model.predict(state, verbose=0))
        else:
            current_state = np.array(current_state)
            num_states = current_state.size // self.state_size
            if num_states == 0:
                num_states = 1
            state = np.reshape(
                current_state, (num_states, self.state_size))
            state = state.astype(np.float64)
            ds_advantage = self.ds_agent.advantage(
                ds_td_target,
                self.ds_agent.critic.model.predict(state, verbose=0))

        # ---- Adaptive learning rate and exploration ----
        td_error_val = float(np.mean(np.abs(ds_advantage.flatten())))
        if not self.istest and hasattr(self.ds_agent.actor, 'opt'):
            curr_actor_lr = float(self.ds_agent.actor.opt.learning_rate)
            new_actor_lr = np.clip(
                curr_actor_lr * np.exp(
                    -config.DRL_BETA_ALPHA * td_error_val),
                config.DRL_MIN_LR, config.DRL_MAX_LR)
            self.ds_agent.actor.opt.learning_rate.assign(new_actor_lr)

            curr_critic_lr = float(self.ds_agent.critic.opt.learning_rate)
            new_critic_lr = np.clip(
                curr_critic_lr * np.exp(
                    -config.DRL_BETA_ALPHA * td_error_val),
                config.DRL_MIN_LR, config.DRL_MAX_LR)
            self.ds_agent.critic.opt.learning_rate.assign(new_critic_lr)

        if getattr(config, 'DRL_FIXED_EXPLORATION_SCHEDULE', False):
            # Decisive-test override: linear decay by episode number, no per-period
            # adaptive update. Tests whether the adaptive rule is the destabiliser.
            decay_eps = max(1, getattr(config, 'DRL_FIXED_DECAY_EPISODES', 50))
            frac = min(1.0, float(self.current_episode) / float(decay_eps))
            eps_init = config.DRL_INITIAL_EXPLORATION
            eps_min = config.DRL_MIN_EXPLORATION
            self.exploration_rate = float(eps_init + (eps_min - eps_init) * frac)
        else:
            decay = getattr(config, 'DRL_EXPLORATION_DECAY', 0.998)
            self.exploration_rate = float(np.clip(
                self.exploration_rate * decay * np.exp(
                    config.DRL_BETA_EPSILON * td_error_val),
                config.DRL_MIN_EXPLORATION, config.DRL_MAX_EXPLORATION))

        # ---- Append to training batches ----
        self.state_batch.append(current_state)
        self.ds_action_batch.append(ds_actions)
        self.ds_td_target_batch.append(ds_td_target)
        self.ds_advantage_batch.append(ds_advantage)

        warmup = getattr(config, 'DRL_WARMUP_STEPS', 10)
        if self.period > warmup:
            self.update_drls()
        self.state = copy.deepcopy(self.next_state)
        return self.bandit.get_arm_counts(), self.reward

    def update_drls(self):
        self.episode_count += 1
        if self.episode_count <= self.max_update_frequency_episodes:
            self.perform_update()
        else:
            if self.update_cycle_count >= self.max_update_frequency:
                self.update_cycle_count = 0
                self.perform_update()
            else:
                self.update_cycle_count += 1

    def perform_update(self):
        if self.istest:
            return
        states = self.ds_agent.list_to_batch(self.state_batch)
        actions = self.ds_agent.list_to_batch(self.ds_action_batch)
        td_targets = self.ds_agent.list_to_batch(self.ds_td_target_batch)
        advantages = self.ds_agent.list_to_batch(self.ds_advantage_batch)
        actor_loss = self.ds_agent.actor.train(states, actions, advantages)
        critic_loss = self.ds_agent.critic.train(states, td_targets)
        self.ds_agent.actor.model.save_weights(self.actor_path)
        self.ds_agent.critic.model.save_weights(self.critic_path)
        if getattr(config, 'DRL_VERBOSE_TRAINING', False):
            print("{} actor loss {} critic loss {}".format(
                self.ds_id, -1 * actor_loss, critic_loss))

    def take_actions(self):
        ds_actions = self.ds_agent.actor.take_action(
            self.state, self.exploration_rate)
        ds_actions[0] = max(ds_actions[0], self.action_lower_bound)

        if len(self.last_actions) > 1:
            prev_actions = list(np.average(
                np.array(self.last_actions), axis=0))
        else:
            alloc_avg = (self.alloc_lo + self.alloc_hi) / 2
            prev_actions = [alloc_avg] * self.num_actions

        all_actions = list(ds_actions)
        all_actions_input = list(ds_actions)
        if len(all_actions) == 1:
            all_actions = all_actions[0]
        if len(all_actions_input) == 1:
            all_actions_input = all_actions_input[0]
        self.drl_actions = copy.deepcopy(ds_actions)

        # Order quantity: od' = od × bounded(D - I + B + safety_stock)
        _ds_snap = self.state_dict.get(str(self.lst_prd), {}).get(self.ds_id, {})
        last_demand = _ds_snap.get('Demand', 0)
        last_inv = _ds_snap.get('Inventory', _ds_snap.get('Inventory-Level', 0))
        last_bklg = _ds_snap.get('Backlog', 0)

        safety_stock = 0.0
        if len(self.lead_time) > 1 and len(self.demand) > 1:
            z_alpha = stats.norm.ppf(
                max(0.5, config.AGENT_CYCLE_SERVICE_LEVEL))
            lt_mean = np.mean(self.lead_time[-self.history_size:])
            d_var = np.var(self.demand[-self.history_size:])
            lt_var = np.var(self.lead_time[-self.history_size:])
            d_mean = np.mean(self.demand[-self.history_size:])
            ss_val = lt_mean * d_var + lt_var * (d_mean ** 2)
            if ss_val > 0:
                safety_stock = z_alpha * np.sqrt(ss_val)

        raw_gap = last_demand - last_inv + last_bklg + safety_stock
        gap = np.clip(raw_gap, self.order_lo, self.order_hi)
        all_actions[0] = max(self.order_lo,
                             min(self.order_hi, all_actions[0] * gap))

        # Allocation ratios
        n_alloc = self.num_actions - 1
        alloc_raw = [all_actions[1 + i] for i in range(n_alloc)]
        alloc_sum = sum(alloc_raw)
        if alloc_sum == 0:
            ratios = [1.0 / max(1, n_alloc)] * n_alloc
        else:
            ratios = [a / alloc_sum for a in alloc_raw]

        _ds_alloc_snap = self.state_dict.get(str(self.lst_prd), {}).get(self.ds_id, {})
        to_be_allocated = _ds_alloc_snap.get('Inventory', _ds_alloc_snap.get('Inventory-Level', 0))
        for i in range(n_alloc):
            all_actions[1 + i] = max(0, int(to_be_allocated * ratios[i]))
            all_actions_input[1 + i] = ratios[i]

        all_actions_input[0] = all_actions[0] / max(1.0, gap) if gap > 0 else 0.0

        if getattr(config, 'DRL_REWARD_FIX', False):
            # r5 fix (advisor-confirmed): store the raw scaled order quantity in
            # the slope history so |beta1| can exceed 1 during disruption,
            # instead of the normalised ratio in [0,1] that pins r5 at +1.
            # self.actions keeps the normalised value (unchanged downstream).
            last_action_entry = list(all_actions_input)
            last_action_entry[0] = float(all_actions[0])
        else:
            last_action_entry = all_actions_input

        if len(self.last_actions) > self.history_size:
            self.last_actions.pop(0)
        self.last_actions.append(last_action_entry)
        self.actions = all_actions_input
        return all_actions

    def _update_next_state(self, observation):
        self._update_hist(observation)
        raw_state = list(self.prev_obs)
        self.state_normalizer.update(raw_state)
        self.next_state = list(self.state_normalizer.normalize(raw_state))

    def _update_states_from_dict(self):
        self.abstract_state = []
        prd_data = self.state_dict.get(str(self.lst_prd), {})
        for agent in self.config_state.keys():
            if len(self.config_state[agent]) > 0:
                ag_data = prd_data.get(agent, {})
                for ag_state in self.config_state[agent]:
                    self.abstract_state.append(ag_data.get(ag_state, 0))
        self._update_next_state(self.abstract_state)

    def _get_observation_size(self):
        state_size = 0
        self.state_dict['0'] = {}
        for ag in self.config_state.keys():
            state_size += len(self.config_state[ag])
            self.state_dict['0'][ag] = {}
            if len(self.config_state[ag]) > 0:
                for ag_st in self.config_state[ag]:
                    self.state_dict['0'][ag][ag_st] = 0
        self.num_observations = state_size

    def get_state_values(self, list_of_dict):
        prd = str(self.period)
        if self.period > 0:
            self.state_dict[prd] = {}
        for x in list_of_dict:
            if x[1] not in self.state_dict[prd].keys():
                self.state_dict[prd][x[1]] = {x[2]: x[3]}
            else:
                self.state_dict[prd][x[1]][x[2]] = x[3]
            if x[1] == self.ds_id:
                if x[2] == 'Inventory':
                    self.inventory = x[3]
                if x[2] == 'Demand':
                    self.demand = np.append(self.demand, x[3])
                if x[2] == 'Backlog':
                    self.backlog = x[3]
                if x[2] == 'Delivery':
                    self.delivery = np.append(self.delivery, x[3])
                if x[2] == 'Lead-time':
                    self.lead_time = np.append(self.lead_time, x[3])
                if x[2] == 'Up-to-level':
                    self.up_to_level = np.append(self.up_to_level, x[3])
                if x[2] == 'On-Order':
                    self.on_order = np.append(self.on_order, x[3])
        self.lst_prd = self.period
        if self.period + 1 > self.history_size:
            self.state_dict.pop(str(self.init_period))
            self.init_period += 1
        self._update_states_from_dict()
        self.period += 1
