""" provide services to calculate order-up-to-level """

import numpy as np
import scipy.stats as st


class OrderUpToLevelCalculator(object):
    """ OrderUpToLevelCalculator calculates the order-up-to-level """

    def calculate(self, now):
        """
        calculates the order-up-to-level
        :param now: current time
        :return: int
        """
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


class NullOrderUpToLevelCalculator(OrderUpToLevelCalculator):

    def __init__(self, agent):
        """
        constructor
        :param agent: The agent that the calculator works with
        :type agent: Agent
        """
        self.agent = agent

    def calculate(self, now):
        """ The NullOrderUpToLevelCalculator does not change the order up to level """
        return int(self.agent.up_to_level)


class OrderUpToLevelCalculatorImpl(OrderUpToLevelCalculator):

    def __init__(self, agent):
        """
        Constructor
        :param agent: the agent that this calculator is working with
        :type agent: Agent
        """
        self.review_period = 1
        self.lead_time = 1
        self.cycle_service_level = 0.97
        self.agent = agent

    def calculate(self, now):
        z = st.norm.ppf(self.cycle_service_level)
        mean = self.agent.predicted_demand
        stdev = self.agent.predicted_demand_stdev

        if np.isnan(mean):
            mean = 0
        if np.isnan(stdev):
            stdev = 0

        lead_time = max(self.lead_time, self.agent.expected_leadtime)
        lead_time = min(lead_time, self.lead_time * 2.0)
        lead_time_var = 0
        if hasattr(self.agent, 'effective_lead_times') and len(self.agent.effective_lead_times) > 1:
            lead_time_var = min(np.var(self.agent.effective_lead_times),
                                lead_time ** 2)

        # S = (L+R)*D_bar + z * sqrt((L+R)*s_D^2 + D_bar^2 * s_L^2)
        safety_stock = z * np.sqrt(
            (lead_time + self.review_period) * (stdev ** 2) +
            (mean ** 2) * lead_time_var
        )
        level = (lead_time + self.review_period) * mean + safety_stock

        return int(level)
