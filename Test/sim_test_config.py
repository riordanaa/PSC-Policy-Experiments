"""
Config-driven simulation entry point.
Reads topology (N_MN x N_DS x N_HC) and all params from config.py.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

import pandas as pd
import tensorflow as tf
import simulator.simulation_runner as sim_runner
import simulator.decision_maker as dmaker
from drl_simulation_profile_config import ConfigDrivenProfile
import config

DATA_COLUMNS = ['time', 'agent', 'item', 'value', 'unit']


def build_simulation(
        total_episodes=None,
        total_periods=None,
        study_name=None,
        drl_total_episodes=None):
    """
    Build simulation from config.py. Optional overrides apply only for this build
    (restored before return) so callers can shorten episodes/periods without
    mutating global config permanently.

    drl_total_episodes: passed to DRLDSDecisionMaker (training horizon); defaults
    to TOTAL_EPISODES after any total_episodes override.
    """
    _backup = {}
    try:
        if total_episodes is not None:
            _backup['TOTAL_EPISODES'] = config.TOTAL_EPISODES
            config.TOTAL_EPISODES = total_episodes
        if total_periods is not None:
            _backup['TOTAL_PERIODS'] = config.TOTAL_PERIODS
            config.TOTAL_PERIODS = total_periods
        if study_name is not None:
            _backup['STUDY_NAME'] = config.STUDY_NAME
            config.STUDY_NAME = study_name

        profile = ConfigDrivenProfile()

        decision_maker = dmaker.PerAgentDecisionMaker()

        hc_dmakers = []
        for i, hc in enumerate(profile.health_centers):
            recipe = config.HC_ORDER_SPLIT[i] if i < len(config.HC_ORDER_SPLIT) else 'equally'
            hc_dm = dmaker.SimpleHCDecisionMaker(hc, recipe)
            decision_maker.add_decision_maker(hc_dm)
            hc_dmakers.append(hc_dm)

        mn_dmakers = []
        for mn in profile.manufacturers:
            mn_dm = dmaker.SimpleMNDecisionMaker(mn)
            decision_maker.add_decision_maker(mn_dm)
            mn_dmakers.append(mn_dm)

        tf.keras.backend.clear_session()

        drl_eps = (drl_total_episodes if drl_total_episodes is not None
                   else config.TOTAL_EPISODES)
        drl_dmakers = []
        for i, ds in enumerate(profile.distributors):
            ds_id = f'DS {i + 1}'
            ds_dm = dmaker.DRLDSDecisionMaker(
                ds, mn_dmakers, hc_dmakers, profile.time_periods,
                ds_id, drl_eps)
            decision_maker.add_decision_maker(ds_dm)
            drl_dmakers.append(ds_dm)

        runner = sim_runner.SimulationRunner(
            profile.simulation, decision_maker, profile.agent_builder,
            profile.parameterize_sim_agents, profile.add_patient_model,
            profile.add_disruptions)

        return profile.simulation, runner, drl_dmakers
    finally:
        for key, val in _backup.items():
            setattr(config, key, val)


def collect_data(my_data, sim_runner, period):
    for hc in sim_runner.simulation.health_centers:
        my_data = pd.concat([my_data, pd.DataFrame(
            hc.collect_data(period), columns=DATA_COLUMNS)], ignore_index=True)
    for ds in sim_runner.simulation.distributors:
        my_data = pd.concat([my_data, pd.DataFrame(
            ds.collect_data(period), columns=DATA_COLUMNS)], ignore_index=True)
    for mn in sim_runner.simulation.manufacturers:
        my_data = pd.concat([my_data, pd.DataFrame(
            mn.collect_data(period), columns=DATA_COLUMNS)], ignore_index=True)
    now = sim_runner.simulation.now
    for ag in sim_runner.simulation.agents:
        name = ag.name()
        history = ag.get_history_item(now)
        my_data = pd.concat([my_data,
                             pd.DataFrame([[now, name, 'order',
                                            sum(order.amount for order in history['order']), '']],
                                          columns=DATA_COLUMNS)], ignore_index=True)
    return my_data


if __name__ == '__main__':
    print(f"Config: {config.N_MN} MN x {config.N_DS} DS x {config.N_HC} HC")
    print(f"Episodes: {config.TOTAL_EPISODES}  Periods: {config.TOTAL_PERIODS}")
    print(f"DRL: {config.DRL_LAYER_TYPE}  Order bounds: [{config.DRL_ORDER_LO}, {config.DRL_ORDER_HI}]")
    print()

    simulation, runner, drl_dmakers = build_simulation()
    runner._update_patient(0)
    runner._update_agents(0)

    do_reset = False
    for eps in range(config.TOTAL_EPISODES):
        data = pd.DataFrame(columns=DATA_COLUMNS)
        for dm in drl_dmakers:
            dm.ds_env.reset()
            dm.episode = eps
        for pr in range(config.TOTAL_PERIODS):
            print(f'Episode {eps} - Period {pr} ####')
            runner.next_cycle(do_reset)
            do_reset = False
            if pr > 0:
                data = collect_data(data, runner, simulation.now)
        do_reset = True
        results_dir = f'episodes_results_EPS{config.TOTAL_EPISODES}_PR{config.TOTAL_PERIODS}'
        os.makedirs(results_dir, exist_ok=True)
        data.to_csv(os.path.join(results_dir, f'drl_results_eps{eps}.csv'))
        print(f'Episode {eps} saved: {len(data)} rows')
