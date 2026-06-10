""" lead_time_estimator provides tools for estimating effective lead time and
    on-time delivery rate
"""
import math
default_leadtime = 2.0
default_max_leadtime = 6.0
PRINTON = False


class LeadTimeEstimator(object):

    def __init__(self, agent):
        """
        Constructor
        :param agent: the agent that the LeadTimeEstimator is working on
        :type agent: Agent
        """
        self.agent = agent
        self.grace_period = 2
        self.trust_hist_length = agent.trust_history_length

    def estimate(self, now):
        """ estimates the effective lead time and the on-time deliver rate """
        self.estimate_on_time_delivery_rate(now)
        self.estimate_effective_lead_time(now)
        self.estimate_overall_effective_lead_time(now)

    def estimate_on_time_delivery_rate(self, now):
        self.agent.on_time_delivery_rate = []

        for node in self.agent.upstream_nodes:
            delivered = 0.0
            ordered = 0.0

            for _, history_item in self.agent.history.items():

                # Too recent history
                if history_item['time'] < 10 or history_item['time'] < now - self.trust_hist_length or \
                                history_item['time'] >= now - self.grace_period:
                    continue

                for order in history_item['order']:
                    if order.dst != node:
                        continue

                    ordered += order.amount
                    for delivery in order.delivery:
                        if delivery['time'] <= order.place_time + self.grace_period:
                            delivered += delivery['amount']

            if ordered == 0:
                self.agent.on_time_delivery_rate.append(1)
            else:
                # print 'ordered'
                # print ordered
                # print 'delivered'
                # print delivered
                # print 'rate'
                # print delivered / ordered
                self.agent.on_time_delivery_rate.append(delivered / ordered)

    def estimate_effective_lead_time(self, now):
        # effective lead-time of each upstream
        self.agent.effective_lead_times = []

        for node in self.agent.upstream_nodes:
            delivered = 0.0
            ordered = 0.0

            for _, history_item in self.agent.history.items():

                for order in history_item['order']:
                    delivered_in_order = 0

                    if order.dst != node:
                        continue

                    ordered += order.amount
                    for delivery in order.delivery:
                        delivered += delivery['amount'] * (delivery['time'] - order.place_time)
                        delivered_in_order += delivery['amount']


                    remaining = order.amount - delivered_in_order
                    delivered += remaining * (now - order.place_time)

            if ordered == 0:
                self.agent.effective_lead_times.append(self.grace_period)
            else:
                self.agent.effective_lead_times.append(delivered / ordered)

    def estimate_overall_effective_lead_time(self, now):
        if self.agent.expected_leadtime <= 0:
            self.agent.expected_leadtime = default_leadtime
            self.agent.effective_lead_time = default_leadtime
            return 0
        # overall effective lead time (for all upstreams)
        delivered = 0.0
        ordered = 0.0
        self.agent.lead_time_pdf[str(now)] = 0
        delivery_time = default_leadtime

        possible_deliveries = [str(i) for i in range(math.ceil(now+self.agent.expected_leadtime+1))]
        total_orders = dict(zip(possible_deliveries, [0] * len(possible_deliveries)))
        total_orders_counter = dict(zip(possible_deliveries, [0] * len(possible_deliveries)))
        sum_delivered_orders = dict(zip(possible_deliveries, [0] * len(possible_deliveries)))
        if self.agent.expected_leadtime == 0:
            self.agent.expected_leadtime = default_leadtime

        for _, history_item in self.agent.history.items():

            for order in history_item['order']:
                delivered_in_order = 0

                ordered += order.amount
                for delivery in order.delivery:
                    delivery_time = delivery['time'] - order.place_time
                    ## reset the delivered and total order dictionaries if
                    ## there is a jump in deliveries
                    #***************************
                    ##### ------------------- COMMENT FOLLOWING --------------------------------###
                    if delivery_time > self.agent.expected_leadtime * 1.5:
                       indent_time = delivery_time
                       #total_orders = {k: 0 for k in total_orders if int(k) < indent_time}
                       for key in total_orders.keys():
                           if int(key) < indent_time:
                               total_orders[key] = 0
                       #sum_delivered_orders = {str(k): 0 for k in total_orders if int(k) < indent_time}
                       for key in sum_delivered_orders.keys():
                           if int(key) < indent_time:
                               sum_delivered_orders[key] = 0

                    ### ------------------- COMMENT ABOVE --------------------------------###
                    delivered += delivery['amount'] * (delivery['time'] - order.place_time)
                    delivered_in_order += delivery['amount']
                    # Updating the total orders and the portion that is delivered in
                    # all possible time windows
                    dt_key = str(delivery_time)
                    if dt_key not in total_orders:
                        total_orders[dt_key] = 0
                        total_orders_counter[dt_key] = 0
                        sum_delivered_orders[dt_key] = 0
                    total_orders[dt_key] += order.amount
                    total_orders_counter[dt_key] += 1
                    sum_delivered_orders[dt_key] += delivery['amount']
                    # if (PRINTON): print('delivery time', delivery_time, 'delivered orders dict', sum_delivered_orders)

                remaining = order.amount - delivered_in_order
                # remaining orders = now + current lead time
                k = now - order.place_time + default_leadtime
                # self.agent.lead_time_pdf[str(k)] = remaining / max(1, order.amount)
                delivered += remaining * (now - order.place_time)

        # Updating the probability distribution of lead time
        self.agent.lead_time_pdf = {str(k): float(sum_delivered_orders[k]) /
                                          max(1,total_orders[k]) for k in total_orders}
        self.agent.lead_time_pdf = {str(k): min(1.0, float(self.agent.lead_time_pdf[k])/
                                        max(0.000001,sum(self.agent.lead_time_pdf.values())))
                                                for k in self.agent.lead_time_pdf}
        # print("sum of lead time probabilities: ", sum(self.agent.lead_time_pdf.values()))
        agent_expected_leadtime = 0
        for i in range(0, now):
            agent_expected_leadtime += i * max(0,self.agent.lead_time_pdf[str(i)])
        agent_expected_leadtime = min(default_max_leadtime, agent_expected_leadtime)
        self.agent.expected_leadtime_list.append(agent_expected_leadtime)
        self.agent.expected_leadtime = agent_expected_leadtime
        if self.agent.expected_leadtime == 0:
            self.agent.expected_leadtime = default_leadtime
        if ordered <= 0:
            self.agent.effective_lead_time = min(default_max_leadtime, max(default_leadtime, self.grace_period))
            # self.agent.effective_lead_time = self.agent.default_leadtime
        else:
            self.agent.effective_lead_time = delivered / ordered
