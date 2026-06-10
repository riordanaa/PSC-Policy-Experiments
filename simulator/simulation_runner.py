"""SimulationRunner defines the behavior of the simulator
"""

import copy as copy
import math
import numpy as np

from .decision import TreatDecision
from .decision import OrderDecision
from .decision import ProduceDecision
from .decision import AllocateDecision
from .agent import Item, agent_id_from_name
from .order import Order
from .network import OrderMessage
from .network import InTransit


class SimulationRunner(object):
    """ A SimulationRunner defines how the simulation updates its states """

    def __init__(self, simulation, decision_maker, agent_builder, parametrize_sim_agents, add_patient_model, add_disruptions):
        self.simulation = simulation
        self.decision_maker = decision_maker
        self.agen_builder = agent_builder
        self.parametrize_sim_agents = parametrize_sim_agents
        self.add_patient_model = add_patient_model
        self.add_disruptions = add_disruptions

    def _reset(self):
        self.simulation.now = 0
        self._reset_agents()
        self.simulation.network.payloads = []
        self.simulation.info_network.payloads = []
        self.parametrize_sim_agents()
        self.add_patient_model()
        self.add_disruptions()
        print('simulation runner successfully reset~~~~~~~~~~~~~')

    def next_cycle(self, do_reset=False):
        if do_reset:
            self._reset()
        """ runs the simulation by one cycle"""
        self.simulation.now += 1

        self._update_patient(self.simulation.now)
        self._update_agents(self.simulation.now)
        self._update_network(self.simulation.now)
        self._exogenous_event(self.simulation.now)
        self._make_decision(self.simulation.now)
        self._apply_decision(self.simulation.now)
        # self._prepare_for_psychsim(self.simulation.now)

    def _make_decision(self, now):
        for agent in self.simulation.agents:
            agent.decisions = []
        self.decision_maker.make_decision(now)

    def _apply_decision(self, time):
        for hc in self.simulation.health_centers:
            self.apply_hc_decision(hc, time)

        for ds in self.simulation.distributors:
            self.apply_ds_decision(ds, time)

        for mn in self.simulation.manufacturers:
            self.apply_mn_decision(mn, time)

    def _update_agents(self, now):
        for agent in self.simulation.agents:
            agent.update(now)

    def _reset_agents(self):
        for agent in self.simulation.agents:
            agent.reset()
            self.agen_builder.reset(agent)

    def apply_hc_decision(self, hc, time):
        for d in hc.decisions:
            # if isinstance(d, TreatDecision):
            if type(d).__name__ == "TreatDecision":
                self.apply_treat_decision(hc, d)
            # elif isinstance(d, OrderDecision):
            elif type(d).__name__ == "OrderDecision":
                self.apply_order_decision(
                    hc, self.simulation.info_network, d, time)
            else:
                print('Health Center cannot handle decision of type {}'.format(d.__class__))

    def apply_ds_decision(self, ds, time):
        for d in ds.decisions:
            # if isinstance(d, OrderDecision):
            if type(d).__name__ == "OrderDecision":
                self.apply_order_decision(
                    ds, self.simulation.info_network, d, time)
            # elif isinstance(d, AllocateDecision):
            elif type(d).__name__ == "AllocateDecision":
                self.apply_allocation_decision(
                    ds, self.simulation.network, d, time)

    def apply_mn_decision(self, mn, time):
        for d in mn.decisions:
            # if isinstance(d, ProduceDecision):
            if type(d).__name__ == "ProduceDecision":
                self.apply_produce_decision(mn, d, time)
            # elif isinstance(d, AllocateDecision):
            elif type(d).__name__ == "AllocateDecision":
                self.apply_allocation_decision(
                    mn, self.simulation.network, d, time)

    def apply_treat_decision(self, hc, decision):
        hc.urgent -= decision.urgent
        hc.satisfied_urgent = decision.urgent
        hc.backlog_non_urgent += hc.non_urgent
        hc.backlog_non_urgent -= decision.non_urgent
        hc.satisfied_non_urgent = decision.non_urgent
        total = decision.urgent + decision.non_urgent
        for i in range(len(hc.inventory)):
            if hc.inventory[i].amount <= total:
                total -= hc.inventory[i].amount
                hc.inventory[i].amount = 0
            else:
                hc.inventory[i].amount -= total
                total = 0

        hc.inventory[:] = [i for i in hc.inventory if not i.amount <= 0]

    def apply_order_decision(self, agent, info_net, decision, time):
        """ convert an order decision to a real order

        :param agent: the agent that makes the decision
        :param info_net: the information network
        :param decision: the order decision
        :param time: current time

        :type agent: Agent
        :type info_net: Network
        :type decision: OrderDecision
        :type time: int

        """
        if decision.amount <= 1:
            return

        order = agent.make_order(decision.upstream, decision.amount, time)

        order_message = OrderMessage(order)
        # order_message.leadTime = info_net.connectivity[agent.id, order.dst.id]
        order_message.leadTime = info_net.connectivity[agent.id, agent_id_from_name(order.dst)]
        order_message.src = order.src
        order_message.dst = order.dst

        info_net.payloads.append(order_message)

    def apply_allocation_decision(self, agent, network, decision, time):
        """

        :param agent: The agent that applies the decision
        :param network:
        :param decision:
        :param time:

        :type agent: Agent

        :return:
        """
        if decision.amount == 0:
            return

        if decision.item is None or decision.order is None:
            self.apply_allocation_decision_without_specify_item_and_order(agent, network, decision, time)
            return

        # if network.connectivity[agent.id, decision.order.src.id] < 0:
        if network.connectivity[agent.id, agent_id_from_name(decision.order.src)] < 0:
            raise Exception("Agent {0} are not connected with agent {1}".format(
                # agent.id, decision.order.src.id))
                agent.id, agent_id_from_name(decision.order.src)))
        agent.fulfill_order_with_item(decision.order, decision.item, decision.amount, network, time)

    def apply_allocation_decision_without_specify_item_and_order(self, agent, network, decision, time):
        """
        If the item and the order is not specified in the decision, the simulation runner will use the oldest items
        to fulfill the oldest orders

        :param agent:
        :param network:
        :param decision:
        :param time:

        :type agent Agent
        :type network Network
        :type decision AllocateDecision
        :type time int

        """
        amount_left = decision.amount
        orders = [order for order in agent.backlog if order.src == decision.downstream_node]

        if not orders or not agent.inventory:
            return

        order_index = 0
        item_index = 0
        order = orders[order_index]
        item = agent.inventory[item_index]
        order_left = order.amount
        item_left = item.amount

        while amount_left > 0:

            if order_left < item_left:
                if order_left < amount_left:
                    agent.fulfill_order_with_item(order, item, order_left, network, time)
                    orders = [o for o in orders if o.amount > 0]
                    amount_left -= order_left
                    if not orders:
                        break
                    order = orders[0]
                    item_left = item.amount
                    order_left = order.amount
                else:
                    agent.fulfill_order_with_item(order, item, amount_left, network, time)
                    amount_left = 0
            else:
                if item_left < amount_left:
                    agent.fulfill_order_with_item(order, item, item_left, network, time)
                    amount_left -= item_left
                    if not agent.inventory:
                        break
                    item = agent.inventory[0]
                    item_left = item.amount
                    order_left = order.amount
                else:
                    agent.fulfill_order_with_item(order, item, amount_left, network, time)
                    amount_left = 0

    def apply_produce_decision(self, mn, decision, time):
        if decision.amount == 0:
            return
        used_lines = int(math.ceil(float(decision.amount) / mn.line_capacity))
        for i in range(1, used_lines + 1):
            item = Item()
            item.lead_time = mn.lead_time
            item.made_by = mn
            item.made_time = time
            item.line_no = i
            item.batch_no = str(item.made_by.id) + '_' + \
                str(item.made_time) + '_' + str(item.line_no)
            if i != used_lines:
                item.amount = copy.copy(mn.line_capacity)
            else:
                item.amount = decision.amount - \
                    mn.line_capacity * (used_lines - 1)
            mn.in_production.append(item)

    def _update_network(self, now):
        net = self.simulation.network
        # reduce the leadtime by 1 unit of time (time has passed)
        for in_transit in net.payloads:
            in_transit.leadTime -= 1
            # if any object has leadtime of zero we should deliver the inventory to the receiving (dst) agent
            if in_transit.leadTime <= 0:
                # in_transit.dst.receive_delivery(
                #     in_transit.item, in_transit.src, now)
                self.simulation.agents[agent_id_from_name(in_transit.dst)].receive_delivery(
                    in_transit.item, in_transit.src, now)
        # if any object has leadtime of zero should be removed from the in-transit network
        net.payloads[:] = [p for p in net.payloads if not p.leadTime <= 0]

        net = self.simulation.info_network
        # reduce the leadtime by 1 unit of time (time has passed)
        for msg in net.payloads:
            msg.leadTime -= 1
            # if any object has leadtime of zero the destination agent should receive the order
            if msg.leadTime <= 0:
                # msg.dst.receive_order(msg.order, now)
                self.simulation.agents[agent_id_from_name(msg.dst)].receive_order(msg.order, now)
        # if any object has leadtime of zero should be removed from the information network
        net.payloads[:] = [p for p in net.payloads if not p.leadTime <= 0]

    def _add_incoming_order_history(self, agent, now, order):
        item = agent.get_history_item(now)
        item['incoming_order'].append(copy.copy(order))

    def _update_patient(self, now):
        self.simulation.patient_model.generate_patient(now)

    def _exogenous_event(self, now):
        for disruption in self.simulation.disruptions:
            disruption.happen(self.simulation, now)

    def _prepare_for_psychsim(self, now):
        net = self.simulation.network
        for hc in self.simulation.health_centers:
            # in-transit inventory
            hc.in_transit_inventory = {}
            hc.expctd_on_order={}
            for upst in hc.upstream_nodes:
                # l_time = net.connectivity[upst.id, hc.id]
                l_time = net.connectivity[agent_id_from_name(upst), hc.id]
                hc.in_transit_inventory[upst] = np.zeros(l_time)
                hc.expctd_on_order[upst] = np.zeros(l_time+1)

            # on-order expected received time

            # max_time={}
            # for upst in hc.upstream_nodes:
            #     max_time[upst.id]=0
            for oo in hc.on_order:
                # lead_time= net.connectivity[oo.src.id, oo.dst.id]
                lead_time = net.connectivity[agent_id_from_name(oo.src), agent_id_from_name(oo.dst)]
                # if the expected received time has passed updated expected received time is now
                oo.exp_recv_time = max(oo.place_time+lead_time, now)
                # if oo.exp_recv_time > max_time[oo.dst.id]:
                #     max_time[oo.dst.id]=oo.exp_recv_time

            # for upst in hc.upstream_nodes:
            #     if max_time[upst.id]>0:
            #         hc.expctd_on_order[upst] = np.zeros(max_time[upst.id]-now+1)



        for ds in self.simulation.distributors:
            ds.in_transit_inventory = {}
            ds.expctd_on_order = {}
            for upst in ds.upstream_nodes:
                # l_time = net.connectivity[upst.id, ds.id]
                l_time = net.connectivity[agent_id_from_name(upst), ds.id]
                ds.in_transit_inventory[upst] = np.zeros(l_time)
                ds.expctd_on_order[upst] = np.zeros(l_time+1)

            # on-order expected received time
            # max_time={}
            # for upst in ds.upstream_nodes:
            #     max_time[upst.id]=0
            for oo in ds.on_order:
                # lead_time= net.connectivity[oo.src.id, oo.dst.id]
                lead_time = net.connectivity[agent_id_from_name(oo.src), agent_id_from_name(oo.dst)]
                # if the expected received time has passed updated expected received time is now
                oo.exp_recv_time = max(oo.place_time+lead_time, now)
                # if oo.exp_recv_time > max_time[oo.dst.id]:
                #     max_time[oo.dst.id]=oo.exp_recv_time

            # for upst in ds.upstream_nodes:
            #     if max_time[upst.id]>0:
            #         ds.expctd_on_order[upst] = np.zeros(max_time[upst.id]-now+1)

        for mn in self.simulation.manufacturers:
            # mn.in_transit_inventory[mn] = np.zeros(mn.lead_time)
            mn.in_transit_inventory[mn.name()] = np.zeros(mn.lead_time)
        current_time = self.simulation.now
        for load in net.payloads:
            if isinstance(load, InTransit):
                #expected_time = load.sendTime + load.leadTime - current_time - 1
                expected_time = load.leadTime - 1
                # load.dst.in_transit_inventory[load.src][expected_time] += load.item.amount
                self.simulation.agents[agent_id_from_name(load.dst)].in_transit_inventory[load.src][expected_time] += load.item.amount
        for mn in self.simulation.manufacturers:
            for product in mn.in_production:
                #expected_time = product.made_time + product.lead_time - current_time -1
                expected_time = product.lead_time - 1
                # mn.in_transit_inventory[mn][expected_time] += product.amount
                mn.in_transit_inventory[mn.name()][expected_time] += product.amount

        for ds in self.simulation.distributors:
            for oo in ds.on_order:
                loc= oo.exp_recv_time - now
                ds.expctd_on_order[oo.dst][loc] += oo.amount

        for hc in self.simulation.health_centers:
            for oo in hc.on_order:
                loc= oo.exp_recv_time - now
                hc.expctd_on_order[oo.dst][loc] += oo.amount

    def __getstate__(self):
        # Copy the object's state from self.__dict__ which contains
        # all our instance attributes. Always use the dict.copy()
        # method to avoid modifying the original state.
        state = self.__dict__.copy()
        return state

    def __setstate__(self, state):
        # Restore instance attributes (i.e., filename and lineno).
        self.__dict__.update(state)
