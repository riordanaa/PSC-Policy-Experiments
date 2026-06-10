import copy
import re
import pandas as pd

from .order import Order
from .demand_predictor import *
from .lead_time_estimator_new import LeadTimeEstimator
from .order_up_to_level_calculator import *
from .network import InTransit
PRINTON = False


def agent_id_from_name(name):
    """Extract the numeric agent ID from a name string like 'mn_0', 'ds_2', 'hc_10'."""
    match = re.search(r'(\d+)$', name)
    if match:
        return int(match.group(1))
    return int(name[-1])


class Agent(object):
    """Agent is an entity that participate in the supply chain"""

    def __init__(self):
        self.reset()
        self.demand_predictor = None
        self.lead_time_estimator = None
        self.order_up_to_level_calculator = None
        self.id = 0
        self.agent_type = "agent"
        self.upstream_nodes = []
        self.downstream_nodes = []
        self.profit_per_unit = 5.0
        self.holding_cost = 1.0
        self.backlog_cost = 10.0

    # def __hash__(self):
    #     return hash(self.id)

    @staticmethod
    def new_history_item(time):
        return {
            'time': time,
            'inventory': 0,
            'allocate': [],
            'production': [],
            'delivery': [],
            'incoming_order': [],
            'patient': (0, 0),
            'patient_lost': (0, 0),
            'treat': (0, 0),
            'order': [],
        }

    def reset(self) -> None:
        """
        Resets all the data structures and attributes of the Agent to their initial state.
        """
        self.inventory = []
        self.predicted_demand = 0.0
        self.predicted_demand_stdev = 0.0
        self.up_to_level = 0.0
        # self.last_forecast = 0
        self.decisions = []  # keeps record of all decisions that were made by the agent
        self.effective_lead_times = []
        self.effective_lead_time = 2.0
        #self.on_time_delivery_rate = []
        self.backlog = []
        self.on_order = []
        self.history = {}
        self.history_length = int(100)
        self.lead_time_dict = {}
        self.lead_time_pdf = {}
        self.expected_leadtime_list = []
        self.expected_leadtime = 2.0
        self.effective_lead_time = 2.0
        self.default_leadtime = 2.0
        self.last_forecast = 0
        # needed for PsychSim
        # self.lead_time_dict = {}
        self.in_transit_inventory = {}
        # which horizon this agent is used to calculate delivery rate
        self.trust_history_length = 20
        self.sum_hc_demand = 0

    def is_history_available(self, time):
        """checks if the history of a certain time is still available or not"""

        return time in self.history

    def get_history_item(self, time):
        """get_current_history_item returns the history item that records
        what is happening now. If such item is already in the agents history,
        this function will simply return it. If the history item has not been
        created yet, this function will create one and return it.

        :param time: the history item you want you retrieve
        :type time: int

        :return: The history item of the current time
        """

        if time not in self.history:
            history_item = self.new_history_item(time)
            self.history[time] = history_item
            return history_item

        history_item = self.history[time]
        return history_item

    def inventory_level(self):
        """ the number of units of drugs currently available in the inventory
        :return: current inventory level
        """

        level = 0

        for item in self.inventory:
            level += item.amount

        return level

    def backlog_level(self):
        """
        :return: The current number of drugs in backlog
        """
        return sum(order.amount for order in self.backlog)
        #return self.backlog[-1].amount

    def on_order_level(self):
        """
        :return: The current on-order level (products ordered but not received yet)
        """
        return sum(order.amount for order in self.on_order)

    def demand(self, now):
        """
        get the demand of cycle now. The now time must be within the recorded
        history. If now is too old, this function returns 0.

        :param now: time
        :type now: int
        :return: the demand of cycle specified by now
        :rtype: int
        """
        item = self.get_history_item(now)
        demand = sum(in_order.amount for in_order in item['incoming_order'])
        if self.agent_type == 'hc':
            self.sum_hc_demand += demand
        return demand

    def receive_delivery(self, package, src, time):
        """ receives a package delivery from src

            :param package: the drug to receive
            :param src: from which agent
            :param time: current time

            :type package: Item
            :type src: Agent
            :type time: int
        """
        # remove on-order associated with the received order
        self.update_order_according_to_delivery(package, src, time)
        self.inventory.append(copy.copy(package))
        # keeping history
        self.record_delivery_history(package, src, time)

    def update_order_according_to_delivery(self, package, src, time):
        """ updates the order information upon receiving a package
        :param package: the package that is received
        :param src: the agent that send out the package
        :param time: the time that the package is received

        :type package: Item
        :type src: Agent
        :type time: int
        """
        if(PRINTON): print('time', time, 'agent', self.name, 'inventory', self.inventory_level(), 'on-order',
                           self.on_order_level(), 'source agent', src, 'received amount', package.amount)
        amount = package.amount
        on_order_id = 0
        while amount > 0 and on_order_id < len(self.on_order):
            on_order = self.on_order[on_order_id]

            if on_order.dst != src:
                on_order_id += 1
                continue

            if amount < on_order.amount:
                self.mark_delivery_in_order_history(on_order, amount, time)
                on_order.amount -= amount
                amount = 0
            else:
                self.mark_delivery_in_order_history(on_order, on_order.amount, time)
                amount -= on_order.amount
                on_order.amount = 0

            on_order_id += 1

        if amount > 0:
            raise ValueError("Delivered amount more than on_order amount")

        self.on_order[:] = [o for o in self.on_order if not o.amount <= 0]

    def mark_delivery_in_order_history(self, on_order, amount, time):
        """ Associate the delivery history with the order history

            :param on_order: the order from the on_order list that received
                             the delivery
            :param amount: the amount of the delivery
            :param time: the time that the delivery happens

            :type on_order: Order
            :type amount: integer
            :type time: integer
        """
        history_item = self.get_history_item(on_order.place_time)
        # if (PRINTON): print('place time', on_order.place_time, 'history_item', history_item)
        # Search for the order that matches the on_order provided.
        # Since everything in the history is a copy of its original data, this
        # search is inevitable.
        matching_order = None
        for order in history_item['order']:
            if order.id == on_order.id:
                matching_order = order

        delivery = {'amount': amount, 'time': time}
        if matching_order is not None:
            matching_order.delivery.append(delivery)

    def record_delivery_history(self, package, src, time):
        """ record the delivery history
        :param package: the package received
        :param src: the agent that send out this package
        :param time: the time when the package is received
        """
        history_item = self.get_history_item(time)
        delivery = {
            'src': src,
            'item': copy.copy(package),
        }
        history_item['delivery'].append(delivery)

    def receive_order(self, order, now):
        """ receive_order puts the order in the backlog and record the
            history

            :param order: the order to receive
            :type order: Order
            :param now: current time
            :type now: int
        """
        self.backlog.append(copy.copy(order))

        history_item = self.get_history_item(now)
        history_item['incoming_order'].append(copy.copy(order))

    def make_order(self, dst, amount, now):
        """ makes an order to the destination

        :param dst: the destination agent
        :param amount: the amount to order
        :param now: current time
        :type dst: Agent
        :type amount: int
        :type now: int

        :return: the order made
        :rtype: Order
        """
        order = Order()
        order.amount = amount
        order.dst = dst
        # order.src = self
        order.src = self.name()
        order.place_time = now

        self.on_order.append(copy.copy(order))

        history_item = self.get_history_item(now)
        history_item['order'].append(copy.copy(order))

        return order

    def update(self, now):
        """ Update agent status """
        self.remove_too_old_history(now)
        self.record_inventory_history(now)

        (self.predicted_demand, self.predicted_demand_stdev) = \
            self.demand_predictor.predict_demand(now)
        self.lead_time_estimator.estimate(now)
        self.up_to_level = self.order_up_to_level_calculator.calculate(now)

    def remove_too_old_history(self, now):
        """ removes the history items that is older than history_length cycles
            long

            :param now: current time
            :type now: int
        """
        self.history = {k: v for k, v in self.history.items()
                        if k > now - self.history_length}

    def record_inventory_history(self, now):
        """ record the current inventory level in the history """
        history_item = self.get_history_item(now)
        history_item['inventory'] = self.inventory_level()

    def name(self):
        """
        returns the name of the agent.
        :return: name of the agent
        :rtype: string
        """
        return self.agent_type + '_' + str(self.id)

    def fulfill_order_with_item(self, order, item, amount, network, time):
        shipment_item = copy.copy(item)
        shipment_item.amount = amount
        in_transit = InTransit(shipment_item)
        # in_transit.leadTime = network.connectivity[self.id, order.src.id]
        in_transit.leadTime = network.connectivity[self.id, agent_id_from_name(order.src)]
        in_transit.sendTime = time

        # in_transit.src = self
        in_transit.src = self.name()
        in_transit.dst = order.src
        network.payloads.append(in_transit)

        order.amount -= amount
        self.backlog[:] = [o for o in self.backlog if o.amount > 0]

        item.amount -= amount
        self.inventory[:] = [i for i in self.inventory if not i.amount <= 0]

        self._add_allocation_history(time, shipment_item, order)

    def _add_allocation_history(self, time, item, order):
        history_item = self.get_history_item(time)
        if 'allocate' not in history_item:
            history_item['allocate'] = []
        history_item['allocate'].append({
            'item': copy.copy(item),
            'order': copy.copy(order),
        })

    def collect_data(self, now):
        """
        Collect data collects data for data analytics and visualization
        :param now: current time
        :type now: int
        :return: a array of entries that contains all the collected data
        :rtype: list
        """
        name = self.name()
        return [
            [now, name, 'inventory', self.inventory_level(), ''],
            [now, name, 'demand', self.demand(now), ''],
            [now, name, 'up-to-level', self.up_to_level, ''],
            [now, name, 'lead-time', self.expected_leadtime, ''],
            [now, name, 'on-order', self.on_order_level(), ''],
            [now, name, 'shipment-out', sum([allocation['item'].amount
                                             for allocation in self.get_history_item(now)['allocate']]), ''],
            [now, name, 'shipment-in', sum([allocation['item'].amount
                                            for allocation in self.get_history_item(now)['delivery']]), ''],
        ]

    def __getstate__(self):
        # Copy the object's state from self.__dict__ which contains
        # all our instance attributes. Always use the dict.copy()
        # method to avoid modifying the original state.
        state = self.__dict__.copy()
        return state

    def __setstate__(self, state):
        # Restore instance attributes (i.e., filename and lineno).
        self.__dict__.update(state)


class Item(object):
    """ Item represents the drug in the inventory or in-transit
    """

    def __init__(self):
        self.reset()

    def reset(self):
        self.made_by = None  # manufacturer
        self.made_time = 0
        self.line_no = 0
        self.batch_no = None  # each line can have different batches of product
        self.amount = int(0)
        self.life_time = 10  # expiration date from now
        # For the in-production items
        self.lead_time = int(2)

    def __getstate__(self):
        # Copy the object's state from self.__dict__ which contains
        # all our instance attributes. Always use the dict.copy()
        # method to avoid modifying the original state.
        state = self.__dict__.copy()
        return state

    def __setstate__(self, state):
        # Restore instance attributes (i.e., filename and lineno).
        self.__dict__.update(state)


class Manufacturer(Agent):
    def __init__(self):
        super(Manufacturer, self).__init__()
        self.reset()
        self.agent_type = 'mn'
        self.downstream_nodes = []

    def reset(self) -> None:
        super(Manufacturer, self).reset()
        self.in_production = []
        self.line_capacity = 0
        self.num_active_lines = 0
        self.prod_amount = 0
        self.expected_leadtime = 2.0
        self.effective_lead_time = 2.0
        self.default_leadtime = 2.0
        self.lead_time = 2

    def update(self, now):
        super(Manufacturer, self).update(now)
        self.apply_in_production_in_history(now)

    def apply_in_production_in_history(self, now):
        """
        :param now: current time
        updates inventory level of manufacturer according to production lead time of in-production objects
        updates the history of manufacturer
        """
        for in_production in self.in_production:
            in_production.lead_time -= 1
            if in_production.lead_time <= 0:
                self.inventory.append(in_production)
                self.add_production_history(now, in_production)
        # remove what was produced from the in-production of manufacturer
        self.in_production[:] = [
            i for i in self.in_production if not i.lead_time <= 0]

    def add_production_history(self, now, item):
        """
        :param now: current time
        :param item: item that was just produced
        updates production history of manufacturer
        """
        history_item = self.get_history_item(now)
        if 'production' not in history_item:
            history_item['production'] = []
        history_item['production'].append(copy.copy(item))

    def collect_data(self, now):
        data = super(Manufacturer, self).collect_data(now)

        name = self.name()
        in_prod = sum(in_prod.amount for in_prod in self.in_production)
        bklg = self.backlog_level()
        data.append([now, name, 'in_production', in_prod, ''])
        data.append([now, name, 'backlog', bklg, ''])
        # P = f * AD - (c * I + h * B)
        ad = sum(a['item'].amount
                 for a in self.get_history_item(now)['allocate'])
        profit = (self.profit_per_unit * ad
                  - (self.holding_cost * self.inventory_level()
                     + self.backlog_cost * bklg))
        data.append([now, name, 'profit', profit, ''])

        return data

    def __getstate__(self):
        state = self.__dict__.copy()
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)


class Distributor(Agent):
    def __init__(self):
        super(Distributor, self).__init__()
        self.reset()
        self.agent_type = 'ds'

    def reset(self) -> None:
        super(Distributor, self).reset()
        # Dictonary, key is upstream node, value is percentage of on-time delivery from that upstream node
        self.ontime_deliv_rate = {}
        self.expctd_on_order = {}
        self.expected_leadtime = 2.0
        self.effective_lead_time = 2.0
        self.default_leadtime = 2.0
        self.arm_score = []
        self.reward = []
        self.on_order = []
        self.demand_sum = 0
        self.delivery_sum = 0
        self.inv_sum = 0


    def update(self, now):
        super(Distributor, self).update(now)
        # calculate on-time delivery rate of its manufacturers (upstream nodes)
        for u in range(len(self.upstream_nodes)):
            self.ontime_deliv_rate[self.upstream_nodes[u]] = self.on_time_delivery_rate[u]

    def calc_backlog(self, now):
        curr_shipment_out = sum([allocation['item'].amount for allocation in self.get_history_item(now)['allocate']])
        curr_demand = self.demand(now)
        self.demand_sum += curr_demand
        self.delivery_sum += curr_shipment_out
        return max(0, self.demand_sum - self.delivery_sum)

    def collect_data(self, now):
        data = super(Distributor, self).collect_data(now)

        name = self.name()
        # Use order backlog (matches backlog_level / simulator dynamics). calc_backlog() is cumulative
        # demand minus shipments and is not the backlog cost term.
        bklg = self.backlog_level()
        data.append([now, name, 'backlog', bklg, ''])
        idx = now - 1
        if 0 <= idx < len(self.arm_score):
            data.append([now, name, 'arm_scores', self.arm_score[idx], ''])
        if 0 <= idx < len(self.reward):
            data.append([now, name, 'reward', self.reward[idx], ''])
        downstream_hcs = sorted(
            [n for n in self.downstream_nodes if n.startswith('hc_')])
        ad_total = 0
        for hc_idx, hc_name in enumerate(downstream_hcs):
            hc_label = f'delivered-to-hc{hc_idx+1}'
            delivered = sum(
                allocation['item'].amount
                for allocation in self.get_history_item(now)['allocate']
                if allocation['order'].src == hc_name)
            data.append([now, name, hc_label, delivered, ''])
            ad_total += delivered
        # P = f * AD - (c * I + h * B)
        profit = (self.profit_per_unit * ad_total
                  - (self.holding_cost * self.inventory_level()
                     + self.backlog_cost * bklg))
        data.append([now, name, 'profit', profit, ''])
        return data

    def __getstate__(self):
        state = self.__dict__.copy()
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)


class HealthCenter(Agent):
    def __init__(self):
        super(HealthCenter, self).__init__()
        self.reset()
        self.agent_type = 'hc'

    def reset(self) -> None:
        super(HealthCenter, self).reset()
        self.urgent = 0  # number of urgent patients (doesn't have backlog)
        self.non_urgent = 0  # number of non-urgent patients
        self.backlog_non_urgent = 0  # number of patients backlogged (each patient needs 1 unit of product)
        self.satisfied_urgent = 0  # number urgent patients treated
        self.satisfied_non_urgent = 0  # number non-urgent patients treated
        self.treat_threshold = 20  # used in one of allocation schemes
        self.expected_leadtime = 3.0
        self.effective_lead_time = 3.0
        self.default_leadtime = 3.0

        # Dictonary, key is upstream node, value is percentage of on-time delivery from that upstream node
        self.ontime_deliv_rate = {}
        self.trust = {}
        self.expctd_on_order = {}
        self.delta = 0.1

    def demand(self, now):
        """
        return the current demand of cycle now, which is the sum of the
        urgent and non-urgent patient.

        :param now: current time
        :type now: int
        :return: the demand of cycle now
        :rtype: int
        """
        history_item = self.get_history_item(now)
        patient = history_item['patient']
        return sum(patient)

    def receive_patient(self, urgent, non_urgent, now):
        """
        discard lost patient and update new patient amount

        :param urgent: urgent patient amount
        :type urgent: int
        :param non_urgent: non-urgent patient amount
        :type non_urgent: int
        :param now: current time
        :type now: int
        """
        history_item = self.get_history_item(now)
        history_item['patient_lost'] = (self.urgent, self.non_urgent)

        self.urgent = urgent
        self.non_urgent = non_urgent

        history_item['patient'] = (urgent, non_urgent)

    def collect_data(self, now):
        data = super(HealthCenter, self).collect_data(now)

        name = self.name()
        for order in self.get_history_item(now)['order']:
            data.append([now, name, 'order-'+order.dst, order.amount, ''])
        for up in self.upstream_nodes:
            data.append([now, name, 'trust-'+up, self.trust.get(up, 0), ''])
        bklg = self.backlog_non_urgent
        data.append([now, name, 'backlog', bklg, ''])
        # P = f * AD - (c * I + h * B)
        ad = self.satisfied_urgent + self.satisfied_non_urgent
        profit = (self.profit_per_unit * ad
                  - (self.holding_cost * self.inventory_level()
                     + self.backlog_cost * bklg))
        data.append([now, name, 'profit', profit, ''])

        return data

    def update(self, now):
        super(HealthCenter, self).update(now)
        # calculate on-time delivery rate of its distributors (upstream nodes)
        for u in range(len(self.upstream_nodes)):
            self.ontime_deliv_rate[self.upstream_nodes[u]] = self.on_time_delivery_rate[u]

    def __getstate__(self):
        # Copy the object's state from self.__dict__ which contains
        # all our instance attributes. Always use the dict.copy()
        # method to avoid modifying the original state.
        state = self.__dict__.copy()
        return state

    def __setstate__(self, state):
        # Restore instance attributes (i.e., filename and lineno).
        self.__dict__.update(state)


class AgentBuilder(object):
    """ AgentBuilder builds fully usable agent """

    def __init__(self):
        self.demand_predictor_type = "MovingAverage"  # how to predict demand
        self.cycle_service_level = 0.97  # service level
        self.lead_time = 2  # used in up-to level calculation
        self.review_time = 1  # used in up-to level calculation
        self.history_preserve_time = 100  # keep the last 100 periods history
        self.next_id = 0  # unique id of the agent
        self.fixed_order_up_to_level = False  # True: a fixed number , False: calculate it

    def use_fixed_order_up_to_level(self):
        self.fixed_order_up_to_level = True

    def build(self, agent_type):
        """ build an agent

        :param agent_type: the type of the agent
        :type agent_type: string

        :return: the agent that is built
        """

        if agent_type == 'health_center':
            agent = HealthCenter()
        elif agent_type == 'distributor':
            agent = Distributor()
        elif agent_type == 'manufacturer':
            agent = Manufacturer()
        else:
            raise ValueError("agent type can only be health_center, "
                             "distributor, or manufacturer")

        agent.id = self.next_id
        self.next_id += 1

        if self.demand_predictor_type == 'MovingAverage':
            demand_predictor = MovingAverageDemandPredictor(
                agent,
                self.history_preserve_time
            )
        elif self.demand_predictor_type == 'RunningAverage':
            demand_predictor = RunningAverageDemandPredictor(agent)
        elif self.demand_predictor_type == 'ExponentialSmoothingDemand':
            demand_predictor = ExponentialSmoothingDemandPredictor(agent)
        else:
            raise ValueError("demand predictor type can only be MovingAverage "
                             "or RunningAverage")

        lead_time_estimator = LeadTimeEstimator(agent)
        agent.lead_time_estimator = lead_time_estimator

        if self.fixed_order_up_to_level:
            order_level_calculator = NullOrderUpToLevelCalculator(agent)
        else:
            order_level_calculator = OrderUpToLevelCalculatorImpl(agent)
            order_level_calculator.lead_time = self.lead_time
            order_level_calculator.review_period = self.review_time
            order_level_calculator.cycle_service_level = self.cycle_service_level

        agent.demand_predictor = demand_predictor
        agent.order_up_to_level_calculator = order_level_calculator
        agent.history_length = self.history_preserve_time

        return agent

    def reset(self, agent):
        """ reset an agent

        :param agent_type: the type of the agent
        :type agent_type: string

        :return: the agent that is built
        """
        if self.demand_predictor_type == 'MovingAverage':
            demand_predictor = MovingAverageDemandPredictor(
                agent,
                self.history_preserve_time
            )
        elif self.demand_predictor_type == 'RunningAverage':
            demand_predictor = RunningAverageDemandPredictor(agent)
        elif self.demand_predictor_type == 'ExponentialSmoothingDemand':
            demand_predictor = ExponentialSmoothingDemandPredictor(agent)
        else:
            raise ValueError("demand predictor type can only be MovingAverage "
                             "or RunningAverage")

        lead_time_estimator = LeadTimeEstimator(agent)
        agent.lead_time_estimator = lead_time_estimator

        if self.fixed_order_up_to_level:
            order_level_calculator = NullOrderUpToLevelCalculator(agent)
        else:
            order_level_calculator = OrderUpToLevelCalculatorImpl(agent)
            order_level_calculator.lead_time = self.lead_time
            order_level_calculator.review_period = self.review_time
            order_level_calculator.cycle_service_level = self.cycle_service_level

        agent.demand_predictor = demand_predictor
        agent.order_up_to_level_calculator = order_level_calculator
        agent.history_length = self.history_preserve_time


    def __getstate__(self):
        # Copy the object's state from self.__dict__ which contains
        # all our instance attributes. Always use the dict.copy()
        # method to avoid modifying the original state.
        state = self.__dict__.copy()
        return state

    def __setstate__(self, state):
        # Restore instance attributes (i.e., filename and lineno).
        self.__dict__.update(state)
