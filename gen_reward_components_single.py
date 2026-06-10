"""Plot the 6 reward components over time for a SINGLE eval seed.

Mirrors gen_reward_components.py but uses one CSV instead of averaging
across all 5, so the discrete {-1, 0, +1} (and {-3..+1}) jumps are
visible at each timestep.
"""
import os
import sys
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

RESULTS_DIR = 'r5_test_results'
TRAIN_EPISODES = 500
DISRUPTION_START = 110
DISRUPTION_END = 157
WARMUP_END = 60

REWARD_META = {
    'r1': ('HC backlog balance (mean over HCs)', '[−3, +1]'),
    'r2': ('Order fulfillment vs demand', '{−1, 0, +1}'),
    'r3': ('Inventory in-band of up-to-level (±2σ)', '{−1, 0, +1}'),
    'r4': ('DS backlog balance', '[−3, +1]'),
    'r5': ('Order-action stability  sign(1−|β₁|)', '{−1, 0, +1}'),
    'r6': ('MN production / demand alignment', '{−1, +1}'),
}

# Default to seed 42; allow override via CLI arg
seed = sys.argv[1] if len(sys.argv) > 1 else '42'
csv_path = os.path.join(RESULTS_DIR, f'episode_{seed}_DS1_r5log.csv')
if not os.path.exists(csv_path):
    raise SystemExit(f'Missing {csv_path}')

df = pd.read_csv(csv_path).sort_values('period').reset_index(drop=True)
print(f'Loaded {len(df)} rows from {csv_path}')

periods = df['period'].values


def phase_means(col):
    pre = df.loc[(df['period'] >= WARMUP_END) & (df['period'] < DISRUPTION_START), col].mean()
    dur = df.loc[(df['period'] >= DISRUPTION_START) & (df['period'] <= DISRUPTION_END), col].mean()
    post = df.loc[df['period'] > DISRUPTION_END, col].mean()
    return pre, dur, post


fig, axes = plt.subplots(6, 1, figsize=(12, 14), sharex=True)
fig.suptitle(
    f'Reward Components Over Time — DS 1 (DRL), Single Seed = {seed}\n'
    f'({TRAIN_EPISODES}-episode trained GRU agent, MAB off, full info sharing, '
    '95% severe disruption — thesis-faithful) — discrete values visible',
    fontsize=11, y=0.997)

colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']

for i, r in enumerate(['r1', 'r2', 'r3', 'r4', 'r5', 'r6']):
    ax = axes[i]
    intent, rng = REWARD_META[r]
    vals = df[r].values

    # Step-style plot to make discrete jumps explicit
    ax.step(periods, vals, color=colors[i], lw=1.2, where='post')
    # Scatter overlay for emphasis on each timestep value
    ax.scatter(periods, vals, color=colors[i], s=6, alpha=0.5, zorder=3)

    ax.axhline(0.0, color='black', ls=':', lw=0.7, alpha=0.5)
    ax.axvspan(DISRUPTION_START, DISRUPTION_END, alpha=0.12, color='red',
               label='Disruption (110–157)' if i == 0 else None)
    ax.axvline(DISRUPTION_START, color='red', lw=0.8, ls='--', alpha=0.5)
    ax.axvline(DISRUPTION_END, color='red', lw=0.8, ls='--', alpha=0.5)

    pre, dur, post = phase_means(r)
    ax.set_title(
        f'{r}: {intent}   |   range {rng}   |   '
        f'phase mean pre={pre:.2f}, during={dur:.2f}, post={post:.2f}',
        fontsize=9, loc='left')
    ax.set_ylabel(r, fontsize=11)

    # Force y-limits to the reward's full theoretical range so discreteness is obvious
    if r in ('r1', 'r4'):
        ax.set_ylim(-3.3, 1.3)
        ax.set_yticks([-3, -2, -1, 0, 1])
    else:
        ax.set_ylim(-1.3, 1.3)
        ax.set_yticks([-1, 0, 1])

    ax.grid(True, alpha=0.3)
    if i == 0:
        ax.legend(loc='upper right', fontsize=8)

axes[-1].set_xlabel('Period', fontsize=11)
plt.tight_layout(rect=[0, 0, 1, 0.975])

png = os.path.join(RESULTS_DIR, f'reward_components_seed{seed}.png')
pdf = os.path.join(RESULTS_DIR, f'reward_components_seed{seed}.pdf')
fig.savefig(png, dpi=200, bbox_inches='tight')
print(f'Saved: {png}')
try:
    fig.savefig(pdf, bbox_inches='tight')
    print(f'Saved: {pdf}')
except PermissionError:
    print('PDF skipped (file open)')
plt.close(fig)

# Quick per-value frequency report
print(f'\nValue frequencies for seed {seed}:')
for r in ['r1', 'r2', 'r3', 'r4', 'r5', 'r6']:
    counts = df[r].value_counts().sort_index()
    s = '   '.join(f'{v:+.0f}: {int(c)}' for v, c in counts.items())
    print(f'  {r}:  {s}')
print('Done.')
