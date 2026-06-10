"""
Config-driven simulation profile that supports any N_MN x N_DS x N_HC topology.
All parameters come from config.py.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from simulator.network import *
from simulator.agent import agent_id_from_name
from simulator.patient_model import *
from simulator.simulation import *
from simulator.disruption import LineShutDownDisruption
import config


class ConfigDrivenProfile(object):
    """Builds a simulation from config.py -- supports any topology."""

    def __init__(self, name=None):
        self.name = name or config.STUDY_NAME
        self.time_periods = config.TOTAL_PERIODS

        self.simulation = Simulation()
        self.agent_builder = AgentBuilder()
        self.parameterize_agent_builder()

        self.create_sim_agents()
        self.create_network()
        self.define_agent_connections()
        self.parameterize_sim_agents()
        self.add_patient_model()
        self.add_disruptions()

        self.manufacturers = self.simulation.manufacturers
        self.distributors = self.simulation.distributors
        self.health_centers = self.simulation.health_centers

    def parameterize_agent_builder(self):
        self.agent_builder.lead_time = config.AGENT_LEAD_TIME
        self.agent_builder.review_time = config.AGENT_REVIEW_TIME
        self.agent_builder.cycle_service_level = config.AGENT_CYCLE_SERVICE_LEVEL
        self.agent_builder.history_preserve_time = config.AGENT_HISTORY_PRESERVE_TIME
        self.agent_builder.demand_predictor_type = config.DEMAND_PREDICTOR_TYPE
        if config.AGENT_FIXED_ORDER_UP_TO_LEVEL:
            self.agent_builder.use_fixed_order_up_to_level()
        else:
            self.agent_builder.fixed_order_up_to_level = False

    def create_sim_agents(self):
        for i in range(config.N_MN):
            agent = self.agent_builder.build('manufacturer')
            agent.agent_name = f'MN{i + 1}'
            self.simulation.add_agent(agent)
        for i in range(config.N_DS):
            agent = self.agent_builder.build('distributor')
            agent.agent_name = f'DS{i + 1}'
            self.simulation.add_agent(agent)
        for i in range(config.N_HC):
            agent = self.agent_builder.build('health_center')
            agent.agent_name = f'HC{i + 1}'
            self.simulation.add_agent(agent)

    def create_network(self):
        num_agents = len(self.simulation.agents)
        net = Network(num_agents)
        info_net = Network(num_agents)
        for i in range(num_agents):
            for j in range(num_agents):
                net.connectivity[i, j] = config.PHYSICAL_LEAD_TIME
                info_net.connectivity[i, j] = config.INFO_LEAD_TIME
        self.simulation.network = net
        self.simulation.info_network = info_net

    def define_agent_connections(self):
        mns = self.simulation.manufacturers
        dss = self.simulation.distributors
        hcs = self.simulation.health_centers

        for mn_idx, ds_idx in config.MN_DS_LINKS:
            dss[ds_idx].upstream_nodes.append(mns[mn_idx].name())
            mns[mn_idx].downstream_nodes.append(dss[ds_idx].name())

        for ds_idx, hc_idx in config.DS_HC_LINKS:
            hcs[hc_idx].upstream_nodes.append(dss[ds_idx].name())
            dss[ds_idx].downstream_nodes.append(hcs[hc_idx].name())

    def parameterize_sim_agents(self):
        for hc in self.simulation.health_centers:
            hc.in_transit_inventory = {}
            for upst in hc.upstream_nodes:
                l_time = self.simulation.network.connectivity[agent_id_from_name(upst), hc.id]
                hc.in_transit_inventory[upst] = np.zeros(l_time)
                hc.expctd_on_order[upst] = np.zeros(l_time)
        for ds in self.simulation.distributors:
            ds.in_transit_inventory = {}
            for upst in ds.upstream_nodes:
                l_time = self.simulation.network.connectivity[agent_id_from_name(upst), ds.id]
                ds.in_transit_inventory[upst] = np.zeros(l_time)
                ds.expctd_on_order[upst] = np.zeros(l_time)
        for mn in self.simulation.manufacturers:
            mn.in_transit_inventory[mn.name()] = np.zeros(mn.lead_time)

        for agent in self.simulation.agents:
            agent.up_to_level = config.AGENT_DEFAULT_UP_TO_LEVEL

        for mn in self.simulation.manufacturers:
            mn.num_of_lines = config.MN_NUM_LINES
            mn.line_capacity = config.MN_LINE_CAPACITY
            mn.num_active_lines = config.MN_NUM_ACTIVE_LINES

        connect = self.simulation.network.connectivity
        for hc in self.simulation.health_centers:
            for upst in hc.upstream_nodes:
                hc.lead_time_dict[upst] = connect[agent_id_from_name(upst), hc.id]
        for ds in self.simulation.distributors:
            for upst in ds.upstream_nodes:
                ds.lead_time_dict[upst] = connect[agent_id_from_name(upst), ds.id]
        for mn in self.simulation.manufacturers:
            mn.lead_time_dict[mn] = mn.lead_time

        for hc in self.simulation.health_centers:
            for upst in hc.upstream_nodes:
                hc.ontime_deliv_rate[upst] = 1
        for ds in self.simulation.distributors:
            for upst in ds.upstream_nodes:
                ds.ontime_deliv_rate[upst] = 1

        if not config.AGENT_FIXED_ORDER_UP_TO_LEVEL:
            now = self.simulation.now
            for agent in self.simulation.agents:
                agent.up_to_level = agent.order_up_to_level_calculator.calculate(now)

    def add_patient_model(self):
        hcs = self.simulation.health_centers
        if config.PATIENT_MODEL_TYPE == 'constant':
            pm = ConstantPatientModel(hcs)
            pm.urgent = config.PATIENT_URGENT
            pm.non_urgent = config.PATIENT_NON_URGENT
        elif config.PATIENT_MODEL_TYPE == 'normal':
            pm = NormalDistPatientModel(hcs)
            pm.urgent_mean = config.PATIENT_NORMAL_URGENT_MEAN
            pm.urgent_stdev = config.PATIENT_NORMAL_URGENT_STDEV
            pm.non_urgent_mean = config.PATIENT_NORMAL_NON_URGENT_MEAN
            pm.non_urgent_stdev = config.PATIENT_NORMAL_NON_URGENT_STDEV
        else:
            pm = ConstantPatientModel(hcs)
        self.simulation.patient_model = pm

    def add_disruptions(self):
        for d_cfg in config.DISRUPTIONS:
            if d_cfg['type'] == 'LineShutDown':
                dis = LineShutDownDisruption(self.simulation, d_cfg['num_active_lines'])
                dis.manufacturer_id = d_cfg['manufacturer_index']
                dis.happen_day_1 = d_cfg['happen_day_1']
                dis.end_day_1 = d_cfg['end_day_1']
                dis.decrease_factor_1 = d_cfg['decrease_factor_1']
                dis.happen_day_2 = d_cfg.get('happen_day_2', -1)
                dis.end_day_2 = d_cfg.get('end_day_2', -1)
                dis.decrease_factor_2 = d_cfg.get('decrease_factor_2', 0)
                self.simulation.disruptions.append(dis)
