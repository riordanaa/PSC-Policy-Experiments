import tensorflow as tf
from tensorflow.keras.layers import (Input, Dense, Lambda, GRU,
                                     TimeDistributed, Dropout)
import numpy as np
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

tf.keras.backend.set_floatx('float64')

try:
    import config as _cfg
    _HIDDEN = getattr(_cfg, 'DRL_HIDDEN_SIZE', 128)
    _DROPOUT = getattr(_cfg, 'DRL_DROPOUT', 0.3)
    _CLIP = getattr(_cfg, 'DRL_GRADIENT_CLIP', 1.0)
    _ACTOR_FC = getattr(_cfg, 'DRL_ACTOR_FC_LAYERS', 2)
    _CRITIC_FC = getattr(_cfg, 'DRL_CRITIC_FC_LAYERS', 3)
    _ENTROPY_COEFF = getattr(_cfg, 'DRL_ENTROPY_COEFF', 0.01)
except ImportError:
    _HIDDEN = 128
    _DROPOUT = 0.3
    _CLIP = 1.0
    _ACTOR_FC = 2
    _CRITIC_FC = 3
    _ENTROPY_COEFF = 0.01


class Actor:
    def __init__(self, state_dim, action_dim, action_bound, std_bound,
                 actor_lr, is_test=False, layer_type='Dense', use_net=True,
                 history_size=None, obs_per_step=None):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.action_bound = action_bound
        self.std_bound = std_bound
        self.is_test = is_test
        self.use_net = use_net
        self.layer_type = layer_type
        self.gradient_clip = _CLIP
        self.history_size = history_size or 1
        self.obs_per_step = obs_per_step or state_dim
        self.gru_seq_len = 1
        self.model = self.create_model()
        if not self.is_test:
            self.opt = tf.keras.optimizers.Adam(actor_lr)

    def create_model(self):
        h = _HIDDEN
        gru_h = max(16, h)   # thesis Table 3.5: GRU width = HIDDEN_SIZE (128)
        drop = _DROPOUT
        if self.layer_type == 'GRU':
            state_input = Input((self.gru_seq_len, self.state_dim,))
            x = TimeDistributed(
                Dense(gru_h, activation='relu', dtype='float64'))(state_input)
            x = GRU(gru_h, activation='relu', dtype='float64')(x)
            x = Dropout(drop)(x)
            for _ in range(_ACTOR_FC):
                x = Dense(h, activation='relu', dtype='float64')(x)
            attention = Dense(h, activation='tanh', dtype='float64')(x)
            out_mu = Dense(self.action_dim, activation='tanh',
                          dtype='float64')(attention)
            mu_output = Lambda(lambda v: v * self.action_bound)(out_mu)
            std_output = Dense(self.action_dim, activation='softplus',
                              dtype='float64')(attention)
            return tf.keras.models.Model(
                state_input, [mu_output, std_output])
        else:
            n_fc = _ACTOR_FC + 1  # Dense mode: 1 extra FC layer (replaces GRU)
            state_input = Input((self.state_dim,))
            x = Dense(h, activation='relu')(state_input)
            for _ in range(n_fc):
                x = Dense(h, activation='relu')(x)
            x = Dropout(drop)(x)
            attention = Dense(h, activation='tanh')(x)
            out_mu = Dense(self.action_dim, activation='tanh')(attention)
            mu_output = Lambda(lambda v: v * self.action_bound)(out_mu)
            std_output = Dense(self.action_dim, activation='softplus')(
                attention)
            return tf.keras.models.Model(
                state_input, [mu_output, std_output])

    def get_action(self, state, exploration_rate=1.0):
        state = np.array(state).flatten()
        num_states = max(1, state.size // self.state_dim)
        if self.layer_type == 'GRU':
            state = np.reshape(state, [num_states, self.gru_seq_len, self.state_dim])
        else:
            state = np.reshape(state, [num_states, self.state_dim])
        state = state.astype(np.float64)
        mu, std = self.model.predict(state, verbose=0)
        std = np.clip(std, self.std_bound[0], self.std_bound[1])
        std = np.exp(std) * exploration_rate
        action = np.tanh(np.random.normal(mu, std))
        return action[0]

    def take_action(self, state, exploration_rate=1.0):
        action = self.get_action(state, exploration_rate)
        action = action * self.action_bound / 2 + self.action_bound / 2
        return action

    def log_pdf(self, mu, std, action):
        std = tf.clip_by_value(std, self.std_bound[0], self.std_bound[1])
        var = std ** 2
        log_policy_pdf = -0.5 * (action - mu) ** 2 / \
                         var - 0.5 * tf.math.log(var * 2 * np.pi)
        return tf.reduce_sum(log_policy_pdf, 1, keepdims=True)

    def compute_loss(self, mu, std, actions, advantages):
        log_policy_pdf = self.log_pdf(mu, std, actions)
        loss_policy = log_policy_pdf * advantages
        std_clipped = tf.clip_by_value(std, self.std_bound[0], self.std_bound[1])
        entropy = 0.5 * tf.reduce_sum(
            tf.math.log(2 * np.pi * np.e * std_clipped ** 2 + 1e-8),
            axis=1, keepdims=True)
        return tf.reduce_sum(-loss_policy - _ENTROPY_COEFF * entropy)

    def train(self, states, actions, advantages):
        if self.layer_type == 'GRU':
            states = np.array(states)
            total = states.size
            if total % self.state_dim != 0:
                raise ValueError(
                    f"states size ({total}) not divisible by "
                    f"state_dim ({self.state_dim})")
            shape = total // self.state_dim
            states = np.reshape(states, (shape, self.gru_seq_len, self.state_dim))
        else:
            states = np.array(states)
            shape = states.size // self.state_dim
            states = np.reshape(states, (shape, self.state_dim))
        states = states.astype(np.float64)

        if not self.is_test:
            with tf.GradientTape() as tape:
                mu, std = self.model(states, training=True)
                loss = self.compute_loss(mu, std, actions, advantages)
            grads = tape.gradient(loss, self.model.trainable_variables)
            grads, _ = tf.clip_by_global_norm(grads, self.gradient_clip)
            self.opt.apply_gradients(
                zip(grads, self.model.trainable_variables))
            return loss
        else:
            with tf.GradientTape() as tape:
                mu, std = self.model(states, training=True)
                loss = self.compute_loss(mu, std, actions, advantages)
            return loss


class Critic:
    def __init__(self, state_dim, critic_lr, is_test=False,
                 layer_type='Dense', use_net=True,
                 history_size=None, obs_per_step=None):
        self.state_dim = state_dim
        self.is_test = is_test
        self.use_net = use_net
        self.layer_type = layer_type
        self.gradient_clip = _CLIP
        self.history_size = history_size or 1
        self.obs_per_step = obs_per_step or state_dim
        self.gru_seq_len = 1
        self.model = self.create_model()
        if not self.is_test:
            self.opt = tf.keras.optimizers.Adam(critic_lr)

    def create_model(self):
        h = _HIDDEN
        gru_h = max(16, h)   # thesis Table 3.5: GRU width = HIDDEN_SIZE (128)
        drop = _DROPOUT
        if self.layer_type == 'GRU':
            input_layer = Input((self.gru_seq_len, self.state_dim,))
            x = TimeDistributed(
                Dense(gru_h, activation='relu', dtype='float64'))(input_layer)
            x = GRU(gru_h, activation='relu', dtype='float64')(x)
            x = Dropout(drop)(x)
            for _ in range(_CRITIC_FC):
                x = Dense(h, activation='relu', dtype='float64')(x)
            attention = Dense(h, activation='tanh', dtype='float64')(x)
            output_layer = Dense(1, activation='linear')(attention)
            return tf.keras.models.Model(input_layer, output_layer)
        else:
            n_fc = _CRITIC_FC + 1
            input_layer = Input((self.state_dim,))
            x = Dense(h, activation='relu')(input_layer)
            for _ in range(n_fc):
                x = Dense(h, activation='relu')(x)
            x = Dropout(drop)(x)
            attention = Dense(h, activation='tanh')(x)
            output_layer = Dense(1, activation='linear')(attention)
            return tf.keras.models.Model(input_layer, output_layer)

    def compute_loss(self, v_pred, td_targets):
        huber = tf.keras.losses.Huber(delta=1.0)
        return huber(td_targets, v_pred)

    def train(self, states, td_targets):
        if self.layer_type == 'GRU':
            states = np.array(states)
            num_states = states.size // self.state_dim
            states = np.reshape(states, [num_states, self.gru_seq_len, self.state_dim])
        else:
            states = np.array(states)
            shape = states.size // self.state_dim
            states = np.reshape(states, (shape, self.state_dim))
        states = states.astype(np.float64)

        if not self.is_test:
            with tf.GradientTape() as tape:
                v_pred = self.model(states, training=True)
                assert v_pred.shape == td_targets.shape
                loss = self.compute_loss(v_pred, tf.stop_gradient(td_targets))
            grads = tape.gradient(loss, self.model.trainable_variables)
            grads, _ = tf.clip_by_global_norm(grads, self.gradient_clip)
            self.opt.apply_gradients(
                zip(grads, self.model.trainable_variables))
            return loss
        else:
            with tf.GradientTape() as tape:
                v_pred = self.model(states, training=True)
                assert v_pred.shape == td_targets.shape
                loss = self.compute_loss(v_pred, tf.stop_gradient(td_targets))
            return loss


class a2c_Model:
    def __init__(self, state_dim, action_dim, action_bound, gamma,
                 actor_lr, critic_lr, training_num=1,
                 isTest=False, Layer_Type='Dense', useNet=True, Paths=None,
                 history_size=None, obs_per_step=None):
        if Paths is None:
            Paths = ['', '']
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.action_bound = action_bound
        self.gamma = gamma
        self.actor_lr = actor_lr
        self.critic_lr = critic_lr
        self.std_bound = [1e-2, 1.0]
        self.is_test = isTest
        self.use_net = useNet
        self.layer_type = Layer_Type
        self.history_size = history_size or 1
        self.obs_per_step = obs_per_step or state_dim
        self.actor = Actor(self.state_dim, self.action_dim,
                           self.action_bound, self.std_bound, self.actor_lr,
                           self.is_test, self.layer_type, self.use_net,
                           self.history_size, self.obs_per_step)
        self.critic = Critic(self.state_dim, self.critic_lr,
                             self.is_test, self.layer_type, self.use_net,
                             self.history_size, self.obs_per_step)
        if self.is_test or self.use_net:
            if os.path.exists(Paths[0]) and os.path.exists(Paths[1]):
                try:
                    self.actor.model.load_weights(Paths[0])
                    self.critic.model.load_weights(Paths[1])
                except Exception as e:
                    print(f"Warning: could not load weights ({e}), "
                          "starting with random weights")
            else:
                print(f"Warning: weight files not found ({Paths[0]}, "
                      f"{Paths[1]}), starting with random weights")

    def td_target(self, reward, next_state, done):
        if done:
            return reward
        next_state = np.array(next_state)
        num_states = next_state.size // self.state_dim
        if num_states == 0:
            num_states = 1
        if self.layer_type == 'GRU':
            states = np.reshape(
                next_state, [num_states, 1, self.state_dim])
        else:
            states = np.reshape(next_state, [num_states, self.state_dim])
        states = states.astype(np.float64)
        v_value = self.critic.model.predict(states, verbose=0)
        return np.reshape(reward + self.gamma * v_value[0], [1, 1])

    def advantage(self, td_targets, baselines):
        return td_targets - baselines

    def list_to_batch(self, items):
        batch = items[0]
        for elem in items[1:]:
            batch = np.append(batch, elem, axis=0)
        return batch
