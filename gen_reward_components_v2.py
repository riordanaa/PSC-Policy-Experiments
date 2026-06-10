"""Reward components plot — median across seeds + histogram by phase.

For each of r1..r6:
  Left panel  (wide):    step-style median across 5 seeds over time,
                         with each individual seed overlaid as a thin
                         translucent line. Shows central tendency
                         without smoothing discreteness.
  Right panel (narrow):  grouped bar histogram of value frequencies
                         pooled across the 5 seeds, split by phase
                         (pre / during / post). Shows whether the
                         distribution of the reward shifts during
                         the disruption.

Output:  r5_test_results/reward_components_v2.png + .pdf
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
    'r1': ('HC backlog balance', '[−3, +1]', [-3, -2, -1, 0, 1]),
    'r2': ('Order fulfillment', '{−1, 0, +1}', [-1, 0, 1]),
    'r3': ('Inventory in-band', '{−1, 0, +1}', [-1, 0, 1]),
    'r4': ('DS backlog balance', '[−3, +1]', [-3, -2, -1, 0, 1]),
    'r5': ('Action stability', '{−1, 0, +1}', [-1, 0, 1]),
    'r6': ('MN alignment', '{−1, +1}', [-1, 0, 1]),
}

PHASE_COLORS = {'pre': '#1f77b4', 'during': '#d62728', 'post': '#2ca02c'}

# ---------- Load with seed tagging ----------
csv_files = sorted([
    os.path.join(RESULTS_DIR, f)
    for f in os.listdir(RESULTS_DIR)
    if f.endswith('_r5log.csv')
])
if not csv_files:
    raise SystemExit(f'No *_r5log.csv files found in {RESULTS_DIR}/')

frames = []
for p in csv_files:
    base = os.path.basename(p)
    seed = base.split('_')[1] if base.startswith('episode_') else base
    f = pd.read_csv(p)
    f['seed'] = seed
    frames.append(f)
df = pd.concat(frames, ignore_index=True)
n_seeds = len(csv_files)
print(f'Loaded {len(df)} rows from {n_seeds} CSVs')


def phase_of(p):
    if WARMUP_END <= p < DISRUPTION_START:
        return 'pre'
    if DISRUPTION_START <= p <= DISRUPTION_END:
        return 'during'
    if p > DISRUPTION_END:
        return 'post'
    return 'warmup'


df['phase'] = df['period'].apply(phase_of)
periods = sorted(df['period'].unique())
seed_ids = sorted(df['seed'].unique())
colors_seed = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']


def median_across_seeds(col):
    return df.groupby('period')[col].median().reindex(periods).values


# ---------- Figure ----------
fig, axes = plt.subplots(
    6, 2, figsize=(15, 16), sharex='col',
    gridspec_kw={'width_ratios': [3, 1], 'wspace': 0.18, 'hspace': 0.45},
)

_n_samples = n_seeds * 300
fig.suptitle(
    'Reward Components — Median + All-Seed Spread (left)  |  Value Histogram by Phase (right)\n'
    f'({n_seeds} eval seeds × 300 periods = {_n_samples} samples each, '
    f'{TRAIN_EPISODES}-episode trained GRU agent, MAB off, full info sharing, '
    '95% severe disruption (thesis-faithful))',
    fontsize=10, y=0.995)

for i, r in enumerate(['r1', 'r2', 'r3', 'r4', 'r5', 'r6']):
    intent, rng, tick_vals = REWARD_META[r]

    # ===== LEFT: time-series =====
    ax = axes[i, 0]

    # All 5 seeds, thin translucent
    for s_idx, sd in enumerate(seed_ids):
        sub = df[df['seed'] == sd].sort_values('period')
        ax.step(sub['period'], sub[r], where='post', lw=0.6, alpha=0.35,
                color=colors_seed[s_idx % len(colors_seed)],
                label=f'seed {sd}' if i == 0 else None)

    # Median across seeds, thick
    med = median_across_seeds(r)
    ax.step(periods, med, where='post', color='black', lw=1.6,
            label='median (5 seeds)' if i == 0 else None)

    ax.axhline(0.0, color='gray', ls=':', lw=0.7, alpha=0.5)
    ax.axvspan(DISRUPTION_START, DISRUPTION_END, alpha=0.10, color='red')
    ax.axvline(DISRUPTION_START, color='red', lw=0.7, ls='--', alpha=0.5)
    ax.axvline(DISRUPTION_END, color='red', lw=0.7, ls='--', alpha=0.5)

    ax.set_ylabel(r, fontsize=11)
    ax.set_title(f'{r}: {intent}   |   range {rng}',
                 fontsize=10, loc='left')
    if r in ('r1', 'r4'):
        ax.set_ylim(-3.4, 1.4)
        ax.set_yticks([-3, -2, -1, 0, 1])
    else:
        ax.set_ylim(-1.4, 1.4)
        ax.set_yticks([-1, 0, 1])
    ax.grid(True, alpha=0.3)
    if i == 0:
        ax.legend(loc='upper right', fontsize=7, ncol=2)
    if i == 5:
        ax.set_xlabel('Period', fontsize=11)

    # ===== RIGHT: histogram by phase =====
    ax = axes[i, 1]
    # Round to nearest integer to handle any tiny float artifacts
    df_r = df.copy()
    df_r[r + '_int'] = df_r[r].round().astype(int)

    width = 0.27
    x_pos = np.arange(len(tick_vals))

    for j, ph in enumerate(['pre', 'during', 'post']):
        sub = df_r[df_r['phase'] == ph]
        total = len(sub)
        if total == 0:
            continue
        counts = sub[r + '_int'].value_counts()
        pct = [100.0 * counts.get(v, 0) / total for v in tick_vals]
        offset = (j - 1) * width
        bars = ax.bar(x_pos + offset, pct, width=width,
                      color=PHASE_COLORS[ph],
                      edgecolor='white', linewidth=0.5,
                      label=ph if i == 0 else None)
        # Tag bars over 5% with their value to avoid clutter
        for bar, p in zip(bars, pct):
            if p >= 5:
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + 1.5,
                        f'{p:.0f}%', ha='center', va='bottom', fontsize=6)

    ax.set_xticks(x_pos)
    ax.set_xticklabels([f'{v:+d}' for v in tick_vals], fontsize=9)
    ax.set_ylim(0, 110)
    ax.set_ylabel('% of samples', fontsize=8)
    ax.set_title('Phase distribution', fontsize=9, loc='left')
    ax.grid(True, alpha=0.3, axis='y')
    if i == 0:
        ax.legend(loc='upper right', fontsize=7, title='phase')
    if i == 5:
        ax.set_xlabel('Reward value', fontsize=10)


plt.tight_layout(rect=[0, 0, 1, 0.975])

png = os.path.join(RESULTS_DIR, 'reward_components_v2.png')
pdf = os.path.join(RESULTS_DIR, 'reward_components_v2.pdf')
fig.savefig(png, dpi=200, bbox_inches='tight')
print(f'Saved: {png}')
try:
    fig.savefig(pdf, bbox_inches='tight')
    print(f'Saved: {pdf}')
except PermissionError:
    print('PDF skipped (file open)')
plt.close(fig)
print('Done.')
