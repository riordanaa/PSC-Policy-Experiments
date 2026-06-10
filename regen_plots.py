"""Regenerate all plots from existing eval CSVs without re-running eval."""
import os, sys
sys.path.insert(0, '.')
sys.path.insert(0, 'Test')
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
import warnings; warnings.filterwarnings('ignore')
import pandas as pd

import run_r5_diagnostic as rdiag

rdiag.apply_config_overrides()

csv_files = sorted([
    os.path.join(rdiag.RESULTS_DIR, f)
    for f in os.listdir(rdiag.RESULTS_DIR)
    if f.endswith('_r5log.csv')
])
all_logs = [pd.read_csv(p) for p in csv_files]
print(f'Loaded {sum(len(l) for l in all_logs)} rows from {len(csv_files)} CSVs')

stats_df, df = rdiag.compute_statistics(all_logs)
rdiag.generate_plots(df)
rdiag.generate_deadzone_plot(df)
rdiag.generate_reward_components_plot(df)
rdiag.generate_training_curve_plot()

import subprocess
subprocess.run([sys.executable, 'gen_reward_inputs.py'], check=True)
subprocess.run([sys.executable, 'gen_reward_components_v2.py'], check=True)
subprocess.run([sys.executable, 'gen_reward_components_single.py', '42'], check=True)
print('Done regenerating plots.')
