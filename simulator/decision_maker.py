''' decision_maker provides simple decision makers for the simulation '''

import copy as copy
import sys
import os
from .agent import *
from .decision import *
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import config as sim_config
import ds_world
import re
PRINTON = False

class DecisionMaker(object):
    ''' Decision Maker makes decisions for all the agents '''

    def make_decision(self, now):
        ''' make decisions for all the agents'''
        pass

    def __getstate__(self):
        # Copy the object's state from self.__dict__ which contains
        # all our instance attributes. Always use the dict.copy()
        # method to avoid modifying the original state.
        state = self.__dict__.copy()
        return state

    def __setstate__(self, state):
        # Restore instance attributes (i.e., filename and lineno).
        self.__dict__.update(state)


class PerAgentDecisionMaker(DecisionMaker):
    ''' PerAgentDecisionMaker is a decision maker that combines all the
        agent level decision makers.
    '''

    def __init__(self):
        self.decision_makers = []

    def add_decision_maker(self, decision_maker):
        ''' Register a agent level decision maker'''
        self.decision_makers.append(decision_maker)

    def make_decision(self, now):
        for decision_maker in self.decision_makers:
            decision_maker.make_decision(now)


# The treatment policy should change
class UrgentFirstHCDecisionMaker(DecisionMaker):
    def __init__(self, hc):
        self.hc = hc

    def make_decision(self, now):
        num_upstream_node = len(self.hc.upstream_nodes)
        total_inventory = sum(tempIn.amount for tempIn in self.hc.inventory)
        total_on_order = sum(tempO.amount for tempO in self.hc.on_order)
        total_demand = self.hc.urgent + self.hc.non_urgent

        # Treat decision
        treat_decision = TreatDecision()
        if total_inventory < total_demand:
            treat_decision.non_urgent = int(
                total_inventory * (float(self.hc.non_urgent) / total_demand))
            treat_decision.urgent = total_inventory - treat_decision.non_urgent
            self.hc.decisions.append(treat_decision)
        else:
            treat_decision.non_urgent = self.hc.non_urgent
            treat_decision.urgent = self.hc.urgent
            self.hc.decisions.append(treat_decision)

        # Order decision
        total_inventory = total_inventory - \
                          treat_decision.urgent - treat_decision.non_urgent
        order_amount = self.hc.up_to_level - total_inventory - total_on_order

        if order_amount < 0:
            order_amount = 0
        for agent in self.hc.upstream_nodes:
            order_decision = OrderDecision()
            order_decision.upstream = agent
            order_decision.amount = int(
                float(order_amount) / num_upstream_node)
            self.hc.decisions.append(order_decision)


class SimpleHCDecisionMaker(DecisionMaker):
    def __init__(self, hc, split_recipe):
        self.hc = hc
        self.split_recipe = split_recipe

    def make_decision(self, now):
        totalInv = sum(tempIn.amount for tempIn in self.hc.inventory)
        totalOnOrder = sum(tempO.amount for tempO in self.hc.on_order)  # I should add the backlog to this
        totalBacklog_non_urgent = self.hc.backlog_non_urgent + self.hc.non_urgent  # Backlog for non-urgent
        totalDemand = self.hc.urgent + totalBacklog_non_urgent

        # update trust
        delivery_amnt = {}
        for up_agent in self.hc.upstream_nodes:
            delivery_amnt[up_agent] = 0
        delivery = self.hc.get_history_item(now)['delivery']
        for deliv in delivery:
            delivery_amnt[deliv['src']] += deliv['item'].amount

        for up_agent in self.hc.upstream_nodes:
            recent_ordered = 0.0
            lookback = min(3, now)
            for ht in range(max(1, now - lookback), now):
                if self.hc.is_history_available(ht):
                    for order in self.hc.get_history_item(ht)['order']:
                        if order.dst == up_agent:
                            recent_ordered += order.amount
            avg_expected = recent_ordered / max(1, lookback)
            if avg_expected > 1:
                self.hc.ontime_deliv_rate[up_agent] = min(
                    1.0, delivery_amnt[up_agent] / avg_expected)
            elif hasattr(self.hc, 'on_time_delivery_rate'):
                idx = list(self.hc.upstream_nodes).index(up_agent)
                if idx < len(self.hc.on_time_delivery_rate):
                    self.hc.ontime_deliv_rate[up_agent] = \
                        self.hc.on_time_delivery_rate[idx]

        if self.split_recipe != 'bytrust' or now < 2:
            for up_agent in self.hc.upstream_nodes:
                self.hc.trust[up_agent] = 1
        else:
            for up_agent in self.hc.upstream_nodes:
                self.hc.trust[up_agent] = (1 - self.hc.delta) * self.hc.trust[up_agent] + \
                                          self.hc.delta * self.hc.ontime_deliv_rate[up_agent]

        decisionT = TreatDecision()
        if totalDemand == 0:
            decisionT.non_urgent = 0
            decisionT.urgent = 0
        elif totalInv < totalDemand:
            decisionT.non_urgent = round(
                totalInv * (float(totalBacklog_non_urgent) / totalDemand))
            decisionT.urgent = min(self.hc.urgent,
                                   totalInv - decisionT.non_urgent)
        else:
            decisionT.non_urgent = int(totalBacklog_non_urgent)
            decisionT.urgent = int(self.hc.urgent)
        self.hc.decisions.append(decisionT)

        # update residual inventory used later for calculating order amount
        self.res_inventory = totalInv - decisionT.urgent - decisionT.non_urgent

        # order decision  ## I should update this (Omid: demand of urgent will be lost and only non-urgent has
        # backlog so up-to-level is only calculated by non-urgent backlog)
        totalBacklog_non_urgent -= decisionT.non_urgent
        orderAmount = max(self.hc.up_to_level -
                          totalOnOrder - self.res_inventory + totalBacklog_non_urgent, 0)
        max_hc_order = max(2.0 * self.hc.demand(now), 120)
        orderAmount = min(orderAmount, max_hc_order)

        if self.split_recipe == 'equally':
            # Order Equally Recipe
            noUptr = len(self.hc.upstream_nodes)
            for agent in self.hc.upstream_nodes:
                decisionO = OrderDecision()
                decisionO.upstream = agent
                decisionO.amount = int(float(orderAmount) / noUptr)
                self.hc.decisions.append(decisionO)
        elif self.split_recipe == 'bytrust':
            sum_trust = 0
            for up_agent in self.hc.upstream_nodes:
                sum_trust += self.hc.trust[up_agent]
            for up_agent in self.hc.upstream_nodes:
                decisionO = OrderDecision()
                decisionO.upstream = up_agent
                decisionO.amount = int(float(orderAmount * self.hc.trust[up_agent]) / sum_trust)
                self.hc.decisions.append(decisionO)
        else:
            raise ValueError("Split Order Recipe Is Not Defined")

# Placeholder - DRL agent for HC decsion maker: (can be completed similar to DRL DS)
class DRLHCDecisionMaker(DecisionMaker):
    def __init__(self, hc, split_recipe, ds, mns, max_periods, id='DS 1', episode=1):
        self.hc = hc
        self.split_recipe = split_recipe
        self.ds = ds
        self.id = id
        self.max_periods = max_periods
        self.ds_env = ds_world.DsWorld(DS_Id=id)
        self.ds_env.take_actions()
        self.ds_actions = self.ds_env.actions
        self.mns = mns
        self.hc_states = ['Inventory', 'Demand', 'Loss', 'Backlog', 'Order', 'Up-to-level', 'Lead-time', 'On-Order']
        self.ds_states = ['Backlog', 'Inventory-Level', 'Order', 'Delivery', 'Inventory', 'On-Order', 'Demand', 'Up-to-level', 'Lead-time']
        self.mn_states = ['Inventory', 'Backlog', 'In production', 'Up-to-level', 'Demand', 'Lead-time']
        self.episode = episode

    def make_decision(self, now):
        pass

class SimpleDSDecisionMaker(DecisionMaker):
    def __init__(self, ds):
        self.ds = ds

    def make_decision(self, now):
        inventory = self.ds.inventory_level()
        allocated = allocate_proportional(self.ds)
        inventory -= allocated

        on_order = sum(tempO.amount for tempO in self.ds.on_order)
        backlog = self.ds.backlog_level()
        backlog -= allocated
        order_amount = max(self.ds.up_to_level + backlog -
                           on_order - inventory, 0)
        max_order = max(2.0 * self.ds.predicted_demand, 120)
        order_amount = min(order_amount, max_order)

        num_upstream_nodes = len(self.ds.upstream_nodes)
        for agent in self.ds.upstream_nodes:
            per_up_order = int(float(order_amount) / num_upstream_nodes)
            decision = OrderDecision()
            decision.upstream = agent
            decision.amount = per_up_order
            self.ds.decisions.append(decision)


class DRLDSDecisionMaker(DecisionMaker):
    def __init__(self, ds, mns, hcs, max_periods, id='DS 1', episode=1):
        self.ds = ds
        self.id = id
        self.max_periods = max_periods
        self.ds_env = ds_world.DsWorld(DS_Id=id)

        transfer_dir = getattr(sim_config, 'TRANSFER_CHECKPOINT_DIR', None)
        if transfer_dir and os.path.isdir(transfer_dir):
            freeze = getattr(sim_config, 'TRANSFER_FREEZE_CRITIC', False)
            self.ds_env.load_checkpoint(transfer_dir, freeze_critic=freeze)
            ft_factor = float(getattr(sim_config, 'TRANSFER_FINETUNE_LR_FACTOR', 0.1))
            if hasattr(self.ds_env.ds_agent.actor, 'opt'):
                actor_lr = float(sim_config.DRL_ACTOR_LR) * ft_factor
                critic_lr = float(sim_config.DRL_CRITIC_LR) * ft_factor
                self.ds_env.ds_agent.actor.opt.learning_rate.assign(actor_lr)
                self.ds_env.ds_agent.critic.opt.learning_rate.assign(critic_lr)
                self.ds_env.set_per_episode_learning_rates(actor_lr, critic_lr)

        self.ds_env.take_actions()
        self.ds_actions = self.ds_env.actions
        self.mns = mns
        self.hcs = hcs
        self.hc_states = ['Inventory', 'Demand', 'Loss', 'Backlog', 'Order', 'Up-to-level', 'Lead-time', 'On-Order']
        self.ds_states = ['Backlog', 'Inventory-Level', 'Order', 'Delivery', 'Inventory', 'On-Order', 'Demand', 'Up-to-level', 'Lead-time']
        self.mn_states = ['Inventory', 'Backlog', 'In production', 'Up-to-level', 'Demand', 'Lead-time']
        self.episode = episode

    def get_states(self, now):
        done = True if (now == (self.max_periods - 1)) else False
        state_matrix = []
        for hc in self.hcs:
            digits = re.findall(r'\d+', getattr(hc.hc, 'agent_name', ''))
            agent_number = digits[0] if digits else str(hc.hc.id)
            hc_name = f'HC {agent_number}'
            state_matrix.append([now, hc_name, 'Inventory', hc.hc.inventory_level(), ''])
            state_matrix.append([now, hc_name, 'Demand', hc.hc.demand(now), ''])
            state_matrix.append([now, hc_name, 'Loss', hc.hc.urgent, ''])
            state_matrix.append([now, hc_name, 'Backlog', hc.hc.backlog_non_urgent, ''])
            state_matrix.append([now, hc_name, 'Order', sum(order.amount for order in hc.hc.get_history_item(now + 1)['order']), ''])
            state_matrix.append([now, hc_name, 'Up-to-level', hc.hc.up_to_level, ''])
            state_matrix.append([now, hc_name, 'Lead-time', hc.hc.expected_leadtime, ''])
            state_matrix.append([now, hc_name, 'On-Order', hc.hc.on_order_level(), ''])
        for mn in self.mns:
            digits = re.findall(r'\d+', getattr(mn.mn, 'agent_name', ''))
            agent_number = digits[0] if digits else str(mn.mn.id)
            mn_name = f'MN {agent_number}'
            state_matrix.append([now, mn_name, 'Inventory', mn.mn.inventory_level(), ''])
            state_matrix.append([now, mn_name, 'Backlog', sum(bl.amount for bl in mn.mn.backlog), ''])
            state_matrix.append([now, mn_name, 'In production', sum(in_prod.amount for in_prod in mn.mn.in_production), ''])
            state_matrix.append([now, mn_name, 'Up-to-level', mn.mn.up_to_level, ''])
            state_matrix.append([now, mn_name, 'Demand', mn.mn.demand(now), ''])
            state_matrix.append([now, mn_name, 'Lead-time', mn.mn.expected_leadtime, ''])
        # DS states:['Backlog', 'Inventory-Level', 'Order', 'Delivery', 'Inventory', 'On-Order', 'Demand', 'Up-to-level', 'Lead-time']
        on_order = sum([order.amount for order in self.ds.on_order])
        shipment_out = sum([allocation['item'].amount for allocation in self.ds.get_history_item(now)['allocate']])
        shipment_in = sum([allocation['item'].amount for allocation in self.ds.get_history_item(now)['delivery']])
        state_matrix.append([now, self.id, 'Backlog', self.ds.backlog_level(), ''])
        state_matrix.append([now, self.id, 'Inventory-Level', self.ds.inventory_level(), ''])
        state_matrix.append([now, self.id, 'Order', sum(order.amount for order in self.ds.get_history_item(now + 1)['order']), ''])
        state_matrix.append([now, self.id, 'Delivery', shipment_in, ''])
        state_matrix.append([now, self.id, 'Inventory', max(0, self.ds.inventory_level()), ''])
        state_matrix.append([now, self.id, 'On-Order', on_order, ''])
        state_matrix.append([now, self.id, 'Demand', self.ds.demand(now), ''])
        state_matrix.append([now, self.id, 'Up-to-level', self.ds.up_to_level, ''])
        state_matrix.append([now, self.id, 'Lead-time', self.ds.expected_leadtime, ''])
        if (PRINTON):
            print('agent', self.id)
            print('Backlog', self.ds.backlog_level())
            print('Inventory-Level', self.ds.inventory_level())
            print('Order', sum(order.amount for order in self.ds.get_history_item(now + 1)['order']))
            print('Delivery', shipment_out)
            print('Inventory', max(0, self.ds.inventory_level() - shipment_out))
            print('Demand', self.ds.demand(now))
        return [state_matrix, done]

    def make_decision(self, now):
        [state_data_matrix, done] = self.get_states(now)
        verbose = getattr(sim_config, 'DRL_VERBOSE_TRAINING', False)
        if verbose:
            print(f'DRL agent {self.id} - Episode {self.episode} ')
        self.ds_env.get_state_values(state_data_matrix)
        sel_arm, reward = self.ds_env.step_reward(done)
        self.ds.arm_score.append(''.join(str(x)+',' for x in sel_arm))
        self.ds.reward.append(reward)
        self.ds_actions = self.ds_env.take_actions()
        if verbose:
            print(
                f'action: {self.ds_actions} - Inv: {self.ds.inventory_level()} '
                f'-Bcklg: {self.ds.backlog_level()}')
        alloc_ratios = list(self.ds_env.actions[1:]) if len(self.ds_env.actions) > 1 else []
        allocate_drl(self.ds, alloc_ratios)
        order_total = int(self.ds_actions[0])
        max_order = max(int(2.0 * self.ds.predicted_demand), 120)
        order_total = min(max(order_total, 0), max_order)
        ups = list(self.ds.upstream_nodes)
        n_up = max(1, len(ups))
        for idx, agent in enumerate(ups):
            decision = OrderDecision()
            decision.upstream = agent
            q, r = divmod(order_total, n_up)
            decision.amount = q + (1 if idx < r else 0)
            self.ds.decisions.append(decision)

        return sel_arm



class TempMNDecisionMaker(DecisionMaker):
    def __init__(self, mn):
        self.mn = mn

    def make_decision(self, now):
        inventory = self.mn.inventory_level()

        # allocation decision
        # each time choose one of these to test the recipe
        allocated = allocate_proportional(self.mn)
        # allocated = allocate_equally(self.mn)
        inventory -= allocated

        # production Decision
        available_capacity = self.mn.num_active_lines * self.mn.line_capacity
        in_production = sum(
            in_prod.amount for in_prod in self.mn.in_production)
        in_backlog = self.mn.backlog_level()
        in_backlog -= allocated

        if now < 120:
            # use up-to level to calculate production amount
            prod_amount = self.mn.up_to_level + in_backlog - inventory - in_production
            if prod_amount < 0:
                prod_amount = 0
            elif prod_amount > available_capacity:
                prod_amount = available_capacity  # can't produce more than available capacity
        elif now < 140:
            prod_amount = 200
        elif now < 160:
            prod_amount = 60
        else:
            prod_amount = 120
            # # use up-to level to calculate production amount
            # prod_amount = self.mn.up_to_level + in_backlog - inventory - in_production
            # if prod_amount < 0:
            #     prod_amount = 0
            # elif prod_amount > available_capacity:
            #     prod_amount = available_capacity  # can't produce more than available capacity

        # adjust the production amount according to line capacity (when a line is open it works at its full capacity)
        line_cap = self.mn.line_capacity
        prod_amount = np.ceil(prod_amount / line_cap) * line_cap
        self.mn.prod_amount = prod_amount

        decision_p = ProduceDecision()
        decision_p.amount = prod_amount
        self.mn.decisions.append(decision_p)


class SimpleMNDecisionMaker(DecisionMaker):
    def __init__(self, mn):
        self.mn = mn

    def make_decision(self, now):
        inventory = self.mn.inventory_level()
        allocated = allocate_proportional(self.mn)
        inventory -= allocated

        available_capacity = self.mn.num_active_lines * self.mn.line_capacity
        in_production = sum(
            in_prod.amount for in_prod in self.mn.in_production)
        in_backlog = self.mn.backlog_level()
        in_backlog -= allocated
        prod_amount = self.mn.up_to_level + in_backlog - inventory - in_production
        if prod_amount < 0:
            prod_amount = 0
        elif prod_amount > available_capacity:
            prod_amount = available_capacity

        line_cap = self.mn.line_capacity
        prod_amount = np.ceil(prod_amount / line_cap) * line_cap
        self.mn.prod_amount = prod_amount

        decision_p = ProduceDecision()
        decision_p.amount = prod_amount
        self.mn.decisions.append(decision_p)


def allocate_proportional(agent):
    backlog = agent.backlog_level()
    inventory = agent.inventory_level()
    allocated = 0
    if inventory == 0 or backlog == 0:
        return 0

    demand_of = {}
    for a in agent.downstream_nodes:
        demand_of[a] = 0

    for bl in agent.backlog:
        if not bl.src in demand_of:
            demand_of[bl.src] = 0
        demand_of[bl.src] += bl.amount

    allocate_to = {}
    for ag in agent.downstream_nodes:
        allocate_to[ag] = int(min(demand_of[ag],
                                  (float(demand_of[ag] * inventory) / backlog)))

    allocated = sum(allocate_to.values())

    inv_ptr = 0
    inv_left = agent.inventory[0].amount
    for bl in agent.backlog:
        bl_left = bl.amount
        while allocate_to[bl.src] > 0 and bl_left > 0:
            if inv_ptr >= len(agent.inventory):
                break
            if min(allocate_to[bl.src], bl_left) <= inv_left:
                decision_al = AllocateDecision()
                decision_al.amount = min(allocate_to[bl.src], bl_left)
                allocate_to[bl.src] -= decision_al.amount
                bl_left -= decision_al.amount
                inv_left -= decision_al.amount
                decision_al.item = agent.inventory[inv_ptr]
                decision_al.order = bl
                agent.decisions.append(decision_al)
            else:
                decision_al = AllocateDecision()
                decision_al.amount = inv_left
                allocate_to[bl.src] -= decision_al.amount
                bl_left -= decision_al.amount
                decision_al.item = agent.inventory[inv_ptr]
                decision_al.order = bl
                agent.decisions.append(decision_al)
                inv_ptr += 1
                if inv_ptr >= len(agent.inventory):
                    break
                inv_left = agent.inventory[inv_ptr].amount

    return allocated


def allocate_equally(agent):
    inventory = agent.inventory_level()
    backlog = agent.backlog_level()
    allocated = 0

    if inventory == 0 or backlog == 0:
        return 0

    num_downstream = len(agent.downstream_nodes)
    demand_of = {}
    for a in agent.downstream_nodes:
        demand_of[a] = 0

    for bl in agent.backlog:
        if not bl.src in demand_of:
            demand_of[bl.src] = 0
        demand_of[bl.src] += bl.amount

    allocate_to = {}
    for ag in agent.downstream_nodes:
        allocate_to[ag] = min(
            demand_of[ag], (inventory / num_downstream))

    allocated = sum(allocate_to.values())

    inv_ptr = 0
    inv_left = agent.inventory[0].amount
    for bl in agent.backlog:
        bl_left = bl.amount
        while allocate_to[bl.src] > 0 and bl_left > 0:
            if inv_ptr >= len(agent.inventory):
                break
            if min(allocate_to[bl.src], bl_left) <= inv_left:
                decision_al = AllocateDecision()
                decision_al.amount = min(allocate_to[bl.src], bl_left)
                allocate_to[bl.src] -= decision_al.amount
                bl_left -= decision_al.amount
                inv_left -= decision_al.amount
                decision_al.item = agent.inventory[inv_ptr]
                decision_al.order = bl
                agent.decisions.append(decision_al)
            else:
                decision_al = AllocateDecision()
                decision_al.amount = inv_left
                allocate_to[bl.src] -= decision_al.amount
                bl_left -= decision_al.amount
                decision_al.item = agent.inventory[inv_ptr]
                decision_al.order = bl
                agent.decisions.append(decision_al)
                inv_ptr += 1
                if inv_ptr >= len(agent.inventory):
                    break
                inv_left = agent.inventory[inv_ptr].amount

    return allocated

def allocate_drl(agent, DRL_allocation):
    """Allocate inventory to downstream HCs using DRL-determined ratios."""
    inventory = agent.inventory_level()
    backlog = agent.backlog_level()

    if inventory == 0 or backlog == 0:
        return 0

    demand_of = {}
    for a in agent.downstream_nodes:
        demand_of[a] = 0
    for bl in agent.backlog:
        if bl.src not in demand_of:
            demand_of[bl.src] = 0
        demand_of[bl.src] += bl.amount

    drl_weights = list(DRL_allocation)
    total_w = sum(max(0, w) for w in drl_weights)
    if total_w == 0:
        total_w = len(agent.downstream_nodes)
        drl_weights = [1.0] * len(agent.downstream_nodes)

    allocate_to = {}
    for idx, ag in enumerate(agent.downstream_nodes):
        w = max(0, drl_weights[idx]) if idx < len(drl_weights) else 1.0
        share = (w / total_w) * inventory
        allocate_to[ag] = int(min(demand_of[ag], share))

    leftover = inventory - sum(allocate_to.values())
    if leftover > 0:
        for ag in agent.downstream_nodes:
            can_take = demand_of[ag] - allocate_to[ag]
            give = min(can_take, leftover)
            if give > 0:
                allocate_to[ag] += give
                leftover -= give
            if leftover <= 0:
                break

    allocated = 0
    inv_ptr = 0
    if not agent.inventory:
        return 0
    inv_left = agent.inventory[0].amount
    for bl in agent.backlog:
        bl_left = bl.amount
        while allocate_to.get(bl.src, 0) > 0 and bl_left > 0:
            if inv_ptr >= len(agent.inventory):
                break
            give = min(allocate_to[bl.src], bl_left, inv_left)
            if give <= 0:
                break
            decision_al = AllocateDecision()
            decision_al.amount = give
            allocate_to[bl.src] -= give
            bl_left -= give
            inv_left -= give
            decision_al.item = agent.inventory[inv_ptr]
            decision_al.order = bl
            allocated += give
            agent.decisions.append(decision_al)
            if inv_left <= 0:
                inv_ptr += 1
                if inv_ptr >= len(agent.inventory):
                    break
                inv_left = agent.inventory[inv_ptr].amount

    return allocated
