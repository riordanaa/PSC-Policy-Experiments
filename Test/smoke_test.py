"""
Quick smoke test: runs the full DRL simulation pipeline for 2 episodes x 10 periods
to verify everything connects and runs without errors.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

import pandas as pd
from sim_test_config import build_simulation

TEST_EPS = 2
TEST_PERIODS = 15
DATA_COLUMNS = ['time', 'agent', 'item', 'value', 'unit']


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
    return my_data


if __name__ == '__main__':
    print(f"=== Smoke Test: {TEST_EPS} episodes x {TEST_PERIODS} periods ===\n")

    simulation, runner, drl_dms = build_simulation(
        total_periods=TEST_PERIODS,
        study_name='smoke_test',
        drl_total_episodes=TEST_EPS)
    runner._update_patient(0)
    runner._update_agents(0)

    do_reset = False
    all_ok = True
    for eps in range(TEST_EPS):
        data = pd.DataFrame(columns=DATA_COLUMNS)
        for dm in drl_dms:
            dm.ds_env.reset()
            dm.episode = eps

        for pr in range(TEST_PERIODS):
            try:
                runner.next_cycle(do_reset)
                do_reset = False
                if pr > 0:
                    data = collect_data(data, runner, simulation.now)
            except Exception as e:
                print(f"  ERROR at Episode {eps}, Period {pr}: {e}")
                all_ok = False
                break

        do_reset = True

        if not data.empty:
            print(f"  Episode {eps}: {len(data)} rows collected")
            agents_in_data = data['agent'].unique()
            metrics_in_data = data['item'].unique()
            print(f"    Agents: {list(agents_in_data)}")
            print(f"    Metrics: {list(metrics_in_data)}")

            for col in DATA_COLUMNS:
                assert col in data.columns, f"Missing column: {col}"

            null_counts = data.isnull().sum().sum()
            if null_counts > 0:
                print(f"    WARNING: {null_counts} null values in data")
            else:
                print(f"    No null values - all rows consistent")

            inv_data = data[data['item'] == 'inventory']
            for ag in inv_data['agent'].unique():
                vals = inv_data[inv_data['agent'] == ag]['value'].values
                print(f"    {ag} inventory range: [{min(vals):.0f}, {max(vals):.0f}]")
        else:
            print(f"  Episode {eps}: No data collected (too few periods)")

    if all_ok:
        print(f"\n=== SMOKE TEST PASSED: Pipeline runs end-to-end ===")
    else:
        print(f"\n=== SMOKE TEST FAILED ===")
        sys.exit(1)
