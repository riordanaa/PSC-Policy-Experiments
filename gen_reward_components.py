"""Plot all 6 reward components (r1-r6) over time from existing eval CSVs.

Loads r5_test_results/episode_*_DS1_r5log.csv and produces a 6-panel
stacked figure showing the per-period realized value of each reward
component, averaged across the 5 eval seeds with +/- 1 SE bands.
"""
import os
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

# ---------- Load all eval CSVs ----------
csv_files = sorted([
    os.path.join(RESULTS_DIR, f)
    for f in os.listdir(RESULTS_DIR)
    if f.endswith('_r5log.csv')
])
if not csv_files:
    raise SystemExit(f'No *_r5log.csv files found in {RESULTS_DIR}/')

df = pd.concat([pd.read_csv(p) for p in csv_files], ignore_index=True)
n_seeds = len(csv_files)
n_rows = len(df)
print(f'Loaded {n_rows} rows from {n_seeds} CSVs')

# ---------- Helpers ----------
periods = sorted(df['period'].unique())

def mean_se(col):
    g = df.groupby('period')[col]
    m = g.mean().reindex(periods).values
    se = g.sem().reindex(periods).fillna(0).values
    return m, se

def phase_means(col):
    pre = df.loc[(df['period'] >= WARMUP_END) & (df['period'] < DISRUPTION_START), col].mean()
    dur = df.loc[(df['period'] >= DISRUPTION_START) & (df['period'] <= DISRUPTION_END), col].mean()
    post = df.loc[df['period'] > DISRUPTION_END, col].mean()
    return pre, dur, post

# ---------- Figure ----------
fig, axes = plt.subplots(6, 1, figsize=(12, 14), sharex=True)
fig.suptitle(
    'Reward Components Over Time — DS 1 (DRL) Test Run\n'
    f'({n_seeds} eval seeds averaged, {TRAIN_EPISODES}-episode trained agent, '
    'MAB off, equal weights, full info sharing, 95% severe disruption (thesis-faithful))',
    fontsize=11, y=0.997)

colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']

for i, r in enumerate(['r1', 'r2', 'r3', 'r4', 'r5', 'r6']):
    ax = axes[i]
    intent, rng = REWARD_META[r]
    m, se = mean_se(r)

    ax.plot(periods, m, color=colors[i], lw=1.5)
    ax.fill_between(periods, m - se, m + se, color=colors[i], alpha=0.25)

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

    # Y-limits with padding so flat constants still legible
    arr = df[r].dropna().values
    if len(arr):
        lo, hi = float(np.min(arr)), float(np.max(arr))
        if hi == lo:
            pad = 0.5
        else:
            pad = max(0.2, (hi - lo) * 0.15)
        ax.set_ylim(lo - pad, hi + pad)

    ax.grid(True, alpha=0.3)
    if i == 0:
        ax.legend(loc='upper right', fontsize=8)

axes[-1].set_xlabel('Period', fontsize=11)
plt.tight_layout(rect=[0, 0, 1, 0.975])

png_path = os.path.join(RESULTS_DIR, 'reward_components.png')
pdf_path = os.path.join(RESULTS_DIR, 'reward_components.pdf')
fig.savefig(png_path, dpi=200, bbox_inches='tight')
print(f'Saved: {png_path}')
try:
    fig.savefig(pdf_path, bbox_inches='tight')
    print(f'Saved: {pdf_path}')
except PermissionError:
    print('PDF skipped (file open in viewer)')
plt.close(fig)

# ---------- Quick sanity report ----------
print('\nPhase means per reward:')
print(f"  {'r':<4} {'pre':>8} {'during':>8} {'post':>8}   range")
for r in ['r1', 'r2', 'r3', 'r4', 'r5', 'r6']:
    pre, dur, post = phase_means(r)
    print(f'  {r:<4} {pre:>8.3f} {dur:>8.3f} {post:>8.3f}   {REWARD_META[r][1]}')

print('Done.')
