"""simulation package provides data structures to build a simulation"""

from simulator.agent import *


class Simulation(object):
    """ A Simulation represents the states of the everything being simulated.
    """

    def __init__(self):
        self.now = 0
        self.health_centers = []
        self.wholesalers = []
        self.distributors = []
        self.manufacturers = []
        self.agents = []  # A collection of all types of agents
        self.regulatory_agency = None
        self.network = None
        self.info_network = None
        self.patient_model = None
        self.disruptions = []

    def add_agent(self, agent):
        self.agents.append(agent)
        if isinstance(agent, HealthCenter):
            self.health_centers.append(agent)
        elif isinstance(agent, Distributor):
            self.distributors.append(agent)
        elif isinstance(agent, Manufacturer):
            self.manufacturers.append(agent)

    def __getstate__(self):
        # Copy the object's state from self.__dict__ which contains
        # all our instance attributes. Always use the dict.copy()
        # method to avoid modifying the original state.
        state = self.__dict__.copy()
        return state

    def __setstate__(self, state):
        # Restore instance attributes (i.e., filename and lineno).
        self.__dict__.update(state)