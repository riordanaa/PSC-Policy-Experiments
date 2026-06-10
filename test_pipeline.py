"""
Comprehensive tests for:
  1. A2C model (Dense + GRU): creation, action, training
  2. DsWorld environment: state management, reward, actions
  3. Inventory policy pipeline: allocation, ordering, simulation cycle
"""
import unittest
import numpy as np
import sys
import os
import copy

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
sys.path.insert(0, os.path.dirname(__file__))

import tensorflow as tf
from model_a2c import Actor, Critic, a2c_Model
from ds_world import DsWorld, sigmoid, State_Config
from simulator.agent import (Agent, Manufacturer, Distributor, HealthCenter,
                              Item, AgentBuilder, agent_id_from_name)
from simulator.order import Order
from simulator.decision import (ProduceDecision, AllocateDecision,
                                 OrderDecision, TreatDecision)
from simulator.network import Network, InTransit, OrderMessage
from simulator.simulation import Simulation
from simulator.patient_model import ConstantPatientModel
from simulator.decision_maker import (
    allocate_proportional, allocate_drl, SimpleMNDecisionMaker,
    SimpleHCDecisionMaker, PerAgentDecisionMaker
)


# ---------------------------------------------------------------------------
# 1. A2C Model Tests
# ---------------------------------------------------------------------------
class TestActorDense(unittest.TestCase):
    """Test Actor with Dense layers."""

    def setUp(self):
        tf.keras.backend.clear_session()
        self.state_dim = 24
        self.action_dim = 3
        self.action_bound = 1.0
        self.std_bound = [1e-2, 1.0]
        self.actor = Actor(self.state_dim, self.action_dim, self.action_bound,
                           self.std_bound, 0.001, is_test=False,
                           layer_type='Dense', use_net=False)

    def test_model_output_shape(self):
        dummy = np.zeros((1, self.state_dim))
        mu, std = self.actor.model.predict(dummy)
        self.assertEqual(mu.shape, (1, self.action_dim))
        self.assertEqual(std.shape, (1, self.action_dim))

    def test_get_action_shape(self):
        state = np.random.randn(self.state_dim)
        action = self.actor.get_action(state)
        self.assertEqual(action.shape, (self.action_dim,))
        self.assertTrue(np.all(np.abs(action) <= 1.0))

    def test_take_action_range(self):
        state = np.random.randn(self.state_dim)
        action = self.actor.take_action(state)
        self.assertEqual(action.shape, (self.action_dim,))
        self.assertTrue(np.all(action >= 0))
        self.assertTrue(np.all(action <= self.action_bound))

    def test_train_returns_loss(self):
        states = np.random.randn(1, self.state_dim)
        actions = np.random.randn(1, self.action_dim)
        advantages = np.random.randn(1, 1)
        loss = self.actor.train(states, actions, advantages)
        self.assertIsNotNone(loss)
        self.assertFalse(np.isnan(loss.numpy()))

    def test_batch_train(self):
        batch_size = 5
        states = np.random.randn(batch_size, self.state_dim)
        actions = np.random.randn(batch_size, self.action_dim)
        advantages = np.random.randn(batch_size, 1)
        loss = self.actor.train(states, actions, advantages)
        self.assertIsNotNone(loss)
        self.assertFalse(np.isnan(loss.numpy()))


class TestActorGRU(unittest.TestCase):
    """Test Actor with GRU layers."""

    def setUp(self):
        tf.keras.backend.clear_session()
        self.state_dim = 24
        self.action_dim = 3
        self.action_bound = 1.0
        self.std_bound = [1e-2, 1.0]
        self.actor = Actor(self.state_dim, self.action_dim, self.action_bound,
                           self.std_bound, 0.001, is_test=False,
                           layer_type='GRU', use_net=False)

    def test_gru_model_output_shape(self):
        dummy = np.zeros((1, 1, self.state_dim))
        mu, std = self.actor.model.predict(dummy)
        self.assertEqual(mu.shape, (1, self.action_dim))
        self.assertEqual(std.shape, (1, self.action_dim))

    def test_gru_get_action_shape(self):
        state = np.random.randn(self.state_dim)
        action = self.actor.get_action(state)
        self.assertEqual(action.shape, (self.action_dim,))

    def test_gru_take_action_range(self):
        state = np.random.randn(self.state_dim)
        action = self.actor.take_action(state)
        self.assertEqual(action.shape, (self.action_dim,))
        self.assertTrue(np.all(action >= 0))
        self.assertTrue(np.all(action <= self.action_bound))

    def test_gru_train_returns_loss(self):
        states = np.random.randn(1, 1, self.state_dim)
        actions = np.random.randn(1, self.action_dim)
        advantages = np.random.randn(1, 1)
        loss = self.actor.train(states, actions, advantages)
        self.assertIsNotNone(loss)
        self.assertFalse(np.isnan(loss.numpy()))

    def test_gru_batch_train(self):
        batch_size = 4
        states = np.random.randn(batch_size, 1, self.state_dim)
        actions = np.random.randn(batch_size, self.action_dim)
        advantages = np.random.randn(batch_size, 1)
        loss = self.actor.train(states, actions, advantages)
        self.assertFalse(np.isnan(loss.numpy()))


class TestCriticDense(unittest.TestCase):
    def setUp(self):
        tf.keras.backend.clear_session()
        self.state_dim = 24
        self.critic = Critic(self.state_dim, 0.001, is_test=False,
                             layer_type='Dense', use_net=False)

    def test_output_shape(self):
        dummy = np.zeros((1, self.state_dim))
        v = self.critic.model.predict(dummy)
        self.assertEqual(v.shape, (1, 1))

    def test_train(self):
        states = np.random.randn(3, self.state_dim)
        targets = np.random.randn(3, 1)
        loss = self.critic.train(states, targets)
        self.assertFalse(np.isnan(loss.numpy()))


class TestCriticGRU(unittest.TestCase):
    def setUp(self):
        tf.keras.backend.clear_session()
        self.state_dim = 24
        self.critic = Critic(self.state_dim, 0.001, is_test=False,
                             layer_type='GRU', use_net=False)

    def test_gru_output_shape(self):
        dummy = np.zeros((1, 1, self.state_dim))
        v = self.critic.model.predict(dummy)
        self.assertEqual(v.shape, (1, 1))

    def test_gru_train(self):
        states = np.random.randn(3, 1, self.state_dim)
        targets = np.random.randn(3, 1)
        loss = self.critic.train(states, targets)
        self.assertFalse(np.isnan(loss.numpy()))


class TestA2CModel(unittest.TestCase):
    """Test full A2C model for both Dense and GRU."""

    def _make_model(self, layer_type):
        tf.keras.backend.clear_session()
        return a2c_Model(
            state_dim=24, action_dim=3, action_bound=1.0,
            gamma=0.6, actor_lr=0.001, critic_lr=0.0003,
            isTest=False, Layer_Type=layer_type, useNet=False, Paths=['', '']
        )

    def test_td_target_dense(self):
        model = self._make_model('Dense')
        reward = np.array([[1.0]])
        next_state = np.random.randn(24)
        td = model.td_target(reward, next_state, done=False)
        self.assertEqual(td.shape, (1, 1))
        self.assertFalse(np.isnan(td).any())

    def test_td_target_done(self):
        model = self._make_model('Dense')
        reward = np.array([[5.0]])
        td = model.td_target(reward, np.zeros(24), done=True)
        np.testing.assert_array_equal(td, reward)

    def test_td_target_gru(self):
        model = self._make_model('GRU')
        reward = np.array([[1.0]])
        next_state = np.random.randn(24)
        td = model.td_target(reward, next_state, done=False)
        self.assertEqual(td.shape, (1, 1))
        self.assertFalse(np.isnan(td).any())

    def test_advantage(self):
        model = self._make_model('Dense')
        td_target = np.array([[3.0]])
        baseline = np.array([[2.0]])
        adv = model.advantage(td_target, baseline)
        np.testing.assert_array_almost_equal(adv, [[1.0]])

    def test_list_to_batch(self):
        model = self._make_model('Dense')
        items = [np.array([[1, 2]]), np.array([[3, 4]]), np.array([[5, 6]])]
        batch = model.list_to_batch(items)
        self.assertEqual(batch.shape, (3, 2))


# ---------------------------------------------------------------------------
# 2. DsWorld Environment Tests
# ---------------------------------------------------------------------------
class TestDsWorld(unittest.TestCase):
    def setUp(self):
        tf.keras.backend.clear_session()
        self.env = DsWorld(isTest=False, training_num=1,
                           Layer_Type='Dense', DS_Id='DS 1',
                           useNet=False, total_episodes=5)

    def test_initial_state(self):
        self.assertEqual(len(self.env.state), self.env.state_size)
        self.assertEqual(len(self.env.next_state), self.env.state_size)
        self.assertEqual(self.env.num_actions, 3)

    def test_observation_size(self):
        expected = sum(len(v) for v in self.env.config_state.values())
        self.assertEqual(self.env.num_observations, expected)
        self.assertEqual(self.env.state_size, expected * self.env.history_size)

    def test_ds1_removes_ds2_mn2(self):
        self.assertEqual(self.env.config_state['DS 2'], [])
        self.assertEqual(self.env.config_state['MN 2'], [])
        self.assertGreater(len(self.env.config_state['DS 1']), 0)

    def test_take_actions_shape(self):
        actions = self.env.take_actions()
        self.assertEqual(len(actions), 3)

    def test_reset(self):
        self.env.state = [99] * self.env.state_size
        self.env.reset()
        self.assertEqual(self.env.state, [0] * self.env.state_size)
        self.assertEqual(self.env.reward, 0)

    def test_update_hist(self):
        obs = list(range(self.env.num_observations))
        self.env._update_hist(obs)
        for i, val in enumerate(obs):
            self.assertEqual(
                self.env.prev_obs[-(self.env.num_observations - i)], val
            )


class TestDsWorldDS2(unittest.TestCase):
    def setUp(self):
        tf.keras.backend.clear_session()
        self.env = DsWorld(isTest=False, training_num=1,
                           Layer_Type='GRU', DS_Id='DS 2',
                           useNet=False, total_episodes=5)

    def test_ds2_removes_ds1_mn1(self):
        self.assertEqual(self.env.config_state['DS 1'], [])
        self.assertEqual(self.env.config_state['MN 1'], [])
        self.assertGreater(len(self.env.config_state['DS 2']), 0)

    def test_gru_take_actions(self):
        actions = self.env.take_actions()
        self.assertEqual(len(actions), 3)


class TestSigmoid(unittest.TestCase):
    def test_sigmoid_center(self):
        self.assertAlmostEqual(sigmoid(5, 1, 5), 0.5, places=5)

    def test_sigmoid_range(self):
        vals = [sigmoid(x, 1, 0) for x in np.linspace(-10, 10, 50)]
        self.assertTrue(all(0 < v < 1 for v in vals))


# ---------------------------------------------------------------------------
# 3. Order ID Uniqueness
# ---------------------------------------------------------------------------
class TestOrderIDs(unittest.TestCase):
    def test_unique_ids(self):
        orders = [Order() for _ in range(100)]
        ids = [o.id for o in orders]
        self.assertEqual(len(ids), len(set(ids)))


# ---------------------------------------------------------------------------
# 4. Inventory Policy / Allocation Tests
# ---------------------------------------------------------------------------
class TestAllocation(unittest.TestCase):
    """Test the allocation functions used in the inventory policy."""

    def _make_agent_with_inventory_and_backlog(self, inv_amount, backlog_amounts):
        agent = Distributor()
        agent.id = 2
        agent.downstream_nodes = ['hc_4', 'hc_5']

        item = Item()
        item.amount = inv_amount
        agent.inventory.append(item)

        for src, amount in backlog_amounts:
            order = Order()
            order.src = src
            order.amount = amount
            agent.backlog.append(order)

        return agent

    def test_proportional_basic(self):
        agent = self._make_agent_with_inventory_and_backlog(
            100, [('hc_4', 60), ('hc_5', 40)])
        allocated = allocate_proportional(agent)
        self.assertGreater(allocated, 0)
        self.assertLessEqual(allocated, 100)
        self.assertTrue(len(agent.decisions) > 0)

    def test_proportional_no_inventory(self):
        agent = self._make_agent_with_inventory_and_backlog(
            0, [('hc_4', 60)])
        allocated = allocate_proportional(agent)
        self.assertEqual(allocated, 0)

    def test_proportional_no_backlog(self):
        agent = self._make_agent_with_inventory_and_backlog(100, [])
        allocated = allocate_proportional(agent)
        self.assertEqual(allocated, 0)

    def test_drl_allocation(self):
        agent = self._make_agent_with_inventory_and_backlog(
            200, [('hc_4', 80), ('hc_5', 120)])
        drl_alloc = [50, 60]
        allocated = allocate_drl(agent, drl_alloc)
        self.assertGreater(allocated, 0)
        self.assertLessEqual(allocated, 200)

    def test_drl_allocation_respects_cap(self):
        agent = self._make_agent_with_inventory_and_backlog(
            30, [('hc_4', 100), ('hc_5', 100)])
        drl_alloc = [100, 100]
        allocated = allocate_drl(agent, drl_alloc)
        self.assertLessEqual(allocated, 30)

    def test_allocation_no_index_error(self):
        """Ensure no IndexError when inventory is fragmented."""
        agent = Distributor()
        agent.id = 2
        agent.downstream_nodes = ['hc_4', 'hc_5']

        for _ in range(3):
            item = Item()
            item.amount = 10
            agent.inventory.append(item)

        for src in ['hc_4', 'hc_5']:
            order = Order()
            order.src = src
            order.amount = 50
            agent.backlog.append(order)

        allocated = allocate_proportional(agent)
        self.assertLessEqual(allocated, 30)


# ---------------------------------------------------------------------------
# 5. Simulation Pipeline Tests
# ---------------------------------------------------------------------------
class TestSimulationPipeline(unittest.TestCase):
    """Test the full simulation pipeline: patient -> agent update -> decision -> apply."""

    def setUp(self):
        self.sim = Simulation()
        builder = AgentBuilder()
        builder.history_preserve_time = 60
        builder.fixed_order_up_to_level = True

        mn = builder.build('manufacturer')
        mn.agent_name = 'MN1'
        mn.num_of_lines = 40
        mn.line_capacity = 10
        mn.num_active_lines = 40
        self.sim.add_agent(mn)

        ds = builder.build('distributor')
        ds.agent_name = 'DS1'
        self.sim.add_agent(ds)

        hc = builder.build('health_center')
        hc.agent_name = 'HC1'
        self.sim.add_agent(hc)

        num_agents = len(self.sim.agents)
        net = Network(num_agents)
        info_net = Network(num_agents)
        for i in range(num_agents):
            for j in range(num_agents):
                net.connectivity[i, j] = 1
                info_net.connectivity[i, j] = 0
        self.sim.network = net
        self.sim.info_network = info_net

        hc.upstream_nodes.append(ds.name())
        ds.downstream_nodes.append(hc.name())
        ds.upstream_nodes.append(mn.name())
        mn.downstream_nodes.append(ds.name())

        for agent in self.sim.agents:
            agent.up_to_level = 120

        patient_model = ConstantPatientModel(self.sim.health_centers)
        self.sim.patient_model = patient_model

        self.mn = mn
        self.ds = ds
        self.hc = hc
        self.builder = builder

    def test_patient_generation(self):
        self.sim.patient_model.generate_patient(1)
        self.assertEqual(self.hc.urgent, 0)
        self.assertEqual(self.hc.non_urgent, 120)

    def test_agent_update(self):
        self.sim.patient_model.generate_patient(1)
        for agent in self.sim.agents:
            agent.update(1)
        self.assertGreaterEqual(self.hc.up_to_level, 0)

    def test_order_decision_creates_order(self):
        self.sim.patient_model.generate_patient(1)
        self.hc.receive_patient(0, 120, 1)
        order = self.hc.make_order(self.ds.name(), 60, 1)
        self.assertEqual(order.amount, 60)
        self.assertEqual(order.dst, self.ds.name())
        self.assertEqual(len(self.hc.on_order), 1)

    def test_manufacturer_production(self):
        item = Item()
        item.lead_time = 1
        item.amount = 100
        self.mn.in_production.append(item)
        self.mn.apply_in_production_in_history(5)
        self.assertEqual(self.mn.inventory_level(), 100)
        self.assertEqual(len(self.mn.in_production), 0)

    def test_network_delivery(self):
        order = self.ds.make_order(self.mn.name(), 50, 0)

        item = Item()
        item.amount = 50
        in_transit = InTransit(item)
        in_transit.leadTime = 1
        in_transit.src = self.mn.name()
        in_transit.dst = self.ds.name()
        in_transit.sendTime = 0
        self.sim.network.payloads.append(in_transit)

        for p in self.sim.network.payloads:
            p.leadTime -= 1
            if p.leadTime <= 0:
                self.sim.agents[agent_id_from_name(p.dst)].receive_delivery(
                    p.item, p.src, 1)

        self.assertEqual(self.ds.inventory_level(), 50)
        self.assertEqual(len(self.ds.on_order), 0)


# ---------------------------------------------------------------------------
# 6. End-to-end DRL + Inventory Flow
# ---------------------------------------------------------------------------
class TestDRLInventoryFlow(unittest.TestCase):
    """Validate the DRL decision-making produces valid inventory actions."""

    def setUp(self):
        tf.keras.backend.clear_session()
        self.env = DsWorld(isTest=False, training_num=1,
                           Layer_Type='Dense', DS_Id='DS 1',
                           useNet=False, total_episodes=5)

    def test_action_order_within_bounds(self):
        actions = self.env.take_actions()
        self.assertGreaterEqual(actions[0], 0)

    def test_allocation_ratios_sum_to_one(self):
        for _ in range(5):
            self.env.take_actions()
        if len(self.env.last_actions) > 0:
            last = self.env.last_actions[-1]
            ratio_sum = last[1] + last[2]
            self.assertAlmostEqual(ratio_sum, 1.0, places=3)

    def test_state_update_flow(self):
        """Simulate feeding state data and verify state dict updates."""
        state_matrix = []
        for hc_name in ['HC 1', 'HC 2']:
            for metric in ['Inventory', 'Demand', 'Loss', 'Backlog',
                           'Order', 'Up-to-level', 'Lead-time', 'On-Order']:
                state_matrix.append([0, hc_name, metric, np.random.randint(0, 200), ''])
        for mn_name in ['MN 1', 'MN 2']:
            for metric in ['Inventory', 'Backlog', 'In production',
                           'Up-to-level', 'Demand', 'Lead-time']:
                state_matrix.append([0, mn_name, metric, np.random.randint(0, 200), ''])
        for ds_name in ['DS 1', 'DS 2']:
            for metric in ['Backlog', 'Inventory-Level', 'Order', 'Delivery',
                           'Inventory', 'On-Order', 'Demand', 'Up-to-level', 'Lead-time']:
                state_matrix.append([0, ds_name, metric, np.random.randint(0, 200), ''])

        self.env.get_state_values(state_matrix)
        self.assertEqual(self.env.period, 1)
        self.assertIn('0', self.env.state_dict)
        self.assertIn('DS 1', self.env.state_dict['0'])


# ---------------------------------------------------------------------------
# 7. Results / Data Collection Tests
# ---------------------------------------------------------------------------
class TestCollectData(unittest.TestCase):
    """Verify that collect_data produces consistent rows with 5 columns."""

    def setUp(self):
        self.sim = Simulation()
        builder = AgentBuilder()
        builder.history_preserve_time = 60
        builder.fixed_order_up_to_level = True

        mn = builder.build('manufacturer')
        mn.agent_name = 'MN1'
        mn.num_of_lines = 40
        mn.line_capacity = 10
        mn.num_active_lines = 40
        self.sim.add_agent(mn)

        ds = builder.build('distributor')
        ds.agent_name = 'DS1'
        self.sim.add_agent(ds)

        hc = builder.build('health_center')
        hc.agent_name = 'HC1'
        self.sim.add_agent(hc)

        hc.upstream_nodes.append(ds.name())
        ds.downstream_nodes.append(hc.name())
        ds.upstream_nodes.append(mn.name())
        mn.downstream_nodes.append(ds.name())

        for ag in self.sim.agents:
            ag.up_to_level = 120

        self.mn = mn
        self.ds = ds
        self.hc = hc

    def test_agent_collect_data_columns(self):
        """Base Agent.collect_data returns rows with exactly 5 columns."""
        rows = self.mn.collect_data(0)
        for i, row in enumerate(rows):
            self.assertEqual(len(row), 5,
                             f"Row {i} ('{row[2]}') has {len(row)} columns, expected 5")

    def test_manufacturer_collect_data_columns(self):
        rows = self.mn.collect_data(0)
        for i, row in enumerate(rows):
            self.assertEqual(len(row), 5,
                             f"MN row {i} ('{row[2]}') has {len(row)} columns")

    def test_distributor_collect_data_columns(self):
        """DS collect_data should have 5 columns even with arm_score/reward."""
        self.ds.arm_score.append('1,1,1,')
        self.ds.reward.append(0.5)
        rows = self.ds.collect_data(1)
        for i, row in enumerate(rows):
            self.assertEqual(len(row), 5,
                             f"DS row {i} ('{row[2]}') has {len(row)} columns")

    def test_healthcenter_collect_data_columns(self):
        """HC collect_data including trust rows should have 5 columns."""
        self.hc.trust[self.ds.name()] = 0.8
        self.hc.receive_patient(10, 100, 1)
        rows = self.hc.collect_data(1)
        for i, row in enumerate(rows):
            self.assertEqual(len(row), 5,
                             f"HC row {i} ('{row[2]}') has {len(row)} columns")

    def test_distributor_reward_indexing(self):
        """arm_score[now-1] and reward[now-1] match the correct period."""
        for t in range(1, 6):
            self.ds.arm_score.append(f'arm_at_time_{t}')
            self.ds.reward.append(t * 10.0)

        rows = self.ds.collect_data(3)
        arm_row = [r for r in rows if r[2] == 'arm_scores']
        reward_row = [r for r in rows if r[2] == 'reward']
        self.assertEqual(len(arm_row), 1)
        self.assertEqual(arm_row[0][3], 'arm_at_time_3')
        self.assertEqual(len(reward_row), 1)
        self.assertEqual(reward_row[0][3], 30.0)

    def test_on_order_not_halved(self):
        """on-order should report the full amount, not divided by 2."""
        o = Order()
        o.amount = 100
        o.dst = self.mn.name()
        o.src = self.ds.name()
        self.ds.on_order.append(o)
        rows = self.ds.collect_data(0)
        on_order_row = [r for r in rows if r[2] == 'on-order']
        self.assertEqual(len(on_order_row), 1)
        self.assertEqual(on_order_row[0][3], 100)


if __name__ == '__main__':
    unittest.main(verbosity=2)
