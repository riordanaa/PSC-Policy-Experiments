import os
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

RESULTS_DIR = 'r5_test_results'
TRAIN_EPISODES = 500

csv_files = [os.path.join(RESULTS_DIR, f) for f in os.listdir(RESULTS_DIR) if f.endswith('_r5log.csv')]
df = pd.concat([pd.read_csv(p) for p in csv_files], ignore_index=True)
n_ts = len(df)
n_seeds = len(csv_files)
print(f'Loaded {n_ts} rows from {n_seeds} CSVs ({n_seeds} eval seeds)')

fig, axes = plt.subplots(1, 2, figsize=(12, 5))
fig.suptitle(
    f'r5 Dead-Zone Analysis: \u03b2\u2081 Distribution vs. \u00b11 Threshold\n'
    f'({n_ts} timesteps across {n_seeds} eval seeds, {TRAIN_EPISODES}-episode trained agent)',
    fontsize=11)

# --- Left: beta1 histogram ---
ax = axes[0]
beta1_vals = df['beta1'].dropna().values
ax.hist(beta1_vals, bins=50, color='#1f77b4', edgecolor='white', alpha=0.85)
ax.axvline(1.0, color='red', lw=2, ls='--', label='\u03b2\u2081 = +1 threshold')
ax.axvline(-1.0, color='red', lw=2, ls='--', label='\u03b2\u2081 = \u22121 threshold')
ax.axvline(0.0, color='black', lw=1, ls=':', alpha=0.6)
max_abs = float(np.abs(beta1_vals).max())

# Shade the r5=+1 zone between -1 and +1
ax.axvspan(-1.0, 1.0, alpha=0.06, color='green', label='r5 = +1 zone (|\u03b2\u2081| < 1)')
ax.set_xlim(-1.5, 1.5)
ylim = ax.get_ylim()
ax.annotate(
    f'Max |\u03b2\u2081| = {max_abs:.3f}\n(threshold = 1.0)',
    xy=(max_abs, ylim[1] * 0.4),
    xytext=(0.58, 0.72), textcoords='axes fraction',
    arrowprops=dict(arrowstyle='->', color='darkred'),
    fontsize=9, color='darkred',
    bbox=dict(boxstyle='round,pad=0.3', facecolor='lightyellow', alpha=0.8))
ax.set_xlabel('\u03b2\u2081 (OLS slope over last 8 order actions)', fontsize=10)
ax.set_ylabel('Frequency (timesteps)', fontsize=10)
ax.set_title(
    '(A) \u03b2\u2081 Distribution \u2014 all values far from \u00b11 threshold\n'
    'r5 fires +1 when |\u03b2\u2081| < 1, \u22121 when |\u03b2\u2081| > 1',
    fontsize=9)
ax.legend(fontsize=8)
ax.grid(True, alpha=0.3)

# --- Right: r5 value bar chart ---
ax = axes[1]
r5_counts = df['r5'].value_counts().sort_index()
all_vals = [-1.0, 0.0, 1.0]
counts = [int(r5_counts.get(v, 0)) for v in all_vals]
labels = ['r5 = \u22121\n(penalised)', 'r5 = 0\n(neutral)', 'r5 = +1\n(rewarded)']
bar_colors = ['#d62728', '#7f7f7f', '#2ca02c']
bars = ax.bar(labels, counts, color=bar_colors, edgecolor='white', width=0.5)
total = sum(counts)
for bar, count in zip(bars, counts):
    pct = count / total * 100 if total > 0 else 0
    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + total * 0.01,
            f'{count}\n({pct:.1f}%)', ha='center', va='bottom', fontsize=10, fontweight='bold')
ax.set_ylabel('Count (timesteps)', fontsize=10)
ax.set_title(
    '(B) r5 Value Distribution \u2014 r5 = \u22121 never fires\n'
    'All non-warmup timesteps receive r5 = +1 (structural false positive)',
    fontsize=9)
ax.set_ylim(0, total * 1.18)
ax.grid(True, alpha=0.3, axis='y')
neg_pct = counts[0] / total * 100 if total > 0 else 0
pos_pct = counts[2] / total * 100 if total > 0 else 0
ax.text(0.97, 0.96,
        f'r5 = +1: {pos_pct:.1f}% of timesteps\n'
        f'r5 = \u22121: {neg_pct:.1f}% of timesteps\n'
        f'Max |\u03b2\u2081| = {max_abs:.3f}  (threshold = 1.0)',
        transform=ax.transAxes, ha='right', va='top', fontsize=9,
        bbox=dict(boxstyle='round,pad=0.4', facecolor='lightyellow', alpha=0.9))

plt.tight_layout()
png_path = os.path.join(RESULTS_DIR, 'r5_deadzone.png')
pdf_path = os.path.join(RESULTS_DIR, 'r5_deadzone.pdf')
fig.savefig(png_path, dpi=200, bbox_inches='tight')
print(f'Saved: {png_path}')
try:
    fig.savefig(pdf_path, bbox_inches='tight')
    print(f'Saved: {pdf_path}')
except PermissionError:
    print('PDF skipped (file open in viewer)')
plt.close(fig)
print('Done.')
