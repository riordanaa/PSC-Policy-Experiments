"""Plot input variables for each reward component (r1, r2, r3, r4, r6).

For each reward, produces a figure showing the raw inputs that feed
into it, plus the realized reward signal for cross-reference. r5 is
already covered by r5_diagnostic.png (order_action + beta1), so we
skip it here.

Generates:
  r5_test_results/r1_inputs.png  (HC backlog trends)
  r5_test_results/r2_inputs.png  (demand vs delivered, gap vs epsilon)
  r5_test_results/r3_inputs.png  (inventory inside utl +/- 2sigma band)
  r5_test_results/r4_inputs.png  (DS backlog dynamics)
  r5_test_results/r6_inputs.png  (MN production vs demand, ratio band)
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


# ---------- Load all eval CSVs ----------
csv_files = sorted([
    os.path.join(RESULTS_DIR, f)
    for f in os.listdir(RESULTS_DIR)
    if f.endswith('_r5log.csv')
])
if not csv_files:
    raise SystemExit(f'No *_r5log.csv files found in {RESULTS_DIR}/')

def _load_with_seed_tag():
    frames = []
    for p in csv_files:
        # Extract seed from filename, e.g. episode_42_DS1_r5log.csv -> 42
        base = os.path.basename(p)
        seed = base.split('_')[1] if base.startswith('episode_') else base
        frame = pd.read_csv(p)
        frame['seed'] = seed
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


df = _load_with_seed_tag()
n_seeds = len(csv_files)
print(f'Loaded {len(df)} rows from {n_seeds} CSVs')

# Check that the new instrumentation ran
required = ['r2_total_demand', 'r3_utl_last', 'r6_mn_prod']
missing = [c for c in required if c not in df.columns]
if missing:
    raise SystemExit(
        f'Missing columns {missing} — please re-run `python3 run_r5_diagnostic.py --skip-train` '
        'after the ds_world.py instrumentation update.')

periods = sorted(df['period'].unique())


def mean_se(col):
    g = df.groupby('period')[col]
    m = g.mean().reindex(periods).values
    se = g.sem().reindex(periods).fillna(0).values
    return m, se


def shade_disruption(ax, label_in_legend=False):
    ax.axvspan(DISRUPTION_START, DISRUPTION_END, alpha=0.12, color='red',
               label='Disruption (110–157)' if label_in_legend else None)
    ax.axvline(DISRUPTION_START, color='red', lw=0.8, ls='--', alpha=0.5)
    ax.axvline(DISRUPTION_END, color='red', lw=0.8, ls='--', alpha=0.5)


def plot_line(ax, col, color, label, lw=1.5, ls='-'):
    m, se = mean_se(col)
    ax.plot(periods, m, color=color, lw=lw, ls=ls, label=label)
    ax.fill_between(periods, m - se, m + se, color=color, alpha=0.2)


def save_fig(fig, name):
    png = os.path.join(RESULTS_DIR, f'{name}.png')
    pdf = os.path.join(RESULTS_DIR, f'{name}.pdf')
    fig.savefig(png, dpi=200, bbox_inches='tight')
    print(f'Saved: {png}')
    try:
        fig.savefig(pdf, bbox_inches='tight')
        print(f'Saved: {pdf}')
    except PermissionError:
        print(f'PDF skipped (file open): {pdf}')
    plt.close(fig)


# =========================================================================
# r1 — HC backlog inputs
# =========================================================================
fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
fig.suptitle(
    'r1 Inputs — HC Backlog Trends Feed into r1 = mean_HC(_compute_backlog_balance)\n'
    f'(range [−3, +1], {n_seeds} eval seeds averaged, {TRAIN_EPISODES}-episode trained agent)',
    fontsize=11)

ax = axes[0]
plot_line(ax, 'hc1_backlog', '#1f77b4', 'HC 1 backlog')
plot_line(ax, 'hc2_backlog', '#ff7f0e', 'HC 2 backlog')
shade_disruption(ax, label_in_legend=True)
ax.set_ylabel('HC backlog')
ax.set_title('(1) Raw HC backlog over time')
ax.legend(loc='upper left', fontsize=8)
ax.grid(True, alpha=0.3)

ax = axes[1]
# Per-period delta computed within each seed
df_delta = df.sort_values(['seed', 'period']).copy()
df_delta['delta_hc1'] = df_delta.groupby('seed')['hc1_backlog'].diff()
df_delta['delta_hc2'] = df_delta.groupby('seed')['hc2_backlog'].diff()
for col, color, label in [('delta_hc1', '#1f77b4', 'Δ HC 1 backlog'),
                           ('delta_hc2', '#ff7f0e', 'Δ HC 2 backlog')]:
    g = df_delta.groupby('period')[col]
    m = g.mean().reindex(periods).values
    se = g.sem().reindex(periods).fillna(0).values
    ax.plot(periods, m, color=color, lw=1.2, label=label)
    ax.fill_between(periods, m - se, m + se, color=color, alpha=0.2)
ax.axhline(0.0, color='black', ls=':', lw=0.7, alpha=0.5)
shade_disruption(ax)
ax.set_ylabel('Δ HC backlog')
ax.set_title('(2) Period-over-period change — r1 penalizes Σ(Δb) > 0')
ax.legend(loc='upper left', fontsize=8)
ax.grid(True, alpha=0.3)

ax = axes[2]
plot_line(ax, 'r1', '#1f77b4', 'r1 (realized)')
ax.axhline(0.0, color='black', ls=':', lw=0.7, alpha=0.5)
shade_disruption(ax)
ax.set_ylabel('r1')
ax.set_title('(3) Realized r1 over time — range [−3, +1]')
ax.set_xlabel('Period')
ax.grid(True, alpha=0.3)

plt.tight_layout(rect=[0, 0, 1, 0.96])
save_fig(fig, 'r1_inputs')


# =========================================================================
# r2 — Order fulfillment inputs
# =========================================================================
fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
fig.suptitle(
    'r2 Inputs — Demand vs Delivered Feeds into r2 = sign(ε − |delivered − demand|)\n'
    f'(range {{−1, 0, +1}}, ε = 50, {n_seeds} eval seeds averaged, {TRAIN_EPISODES}-episode trained agent)',
    fontsize=11)

ax = axes[0]
plot_line(ax, 'r2_total_demand', '#1f77b4', 'Σ demand to DS (window)')
plot_line(ax, 'r2_total_delivered', '#2ca02c', 'Σ delivered to DS (window)')
shade_disruption(ax, label_in_legend=True)
ax.set_ylabel('Window total')
ax.set_title('(1) Cumulative demand vs cumulative delivery over the reward window')
ax.legend(loc='upper left', fontsize=8)
ax.grid(True, alpha=0.3)

ax = axes[1]
# |gap| vs epsilon
df_abs = df.copy()
df_abs['abs_gap'] = df['r2_delivery_gap'].abs()
g = df_abs.groupby('period')['abs_gap']
m = g.mean().reindex(periods).values
se = g.sem().reindex(periods).fillna(0).values
ax.plot(periods, m, color='#d62728', lw=1.5, label='|delivered − demand|')
ax.fill_between(periods, m - se, m + se, color='#d62728', alpha=0.2)
eps = float(df['r2_epsilon'].iloc[0]) if 'r2_epsilon' in df.columns else 50.0
ax.axhline(eps, color='black', lw=1.2, ls='--', label=f'ε = {eps:.0f} (threshold)')
shade_disruption(ax)
ax.set_ylabel('|delivered − demand|')
ax.set_title('(2) Distance from balance vs ε — r2 = +1 only if |gap| < ε')
ax.legend(loc='upper left', fontsize=8)
ax.grid(True, alpha=0.3)

ax = axes[2]
plot_line(ax, 'r2', '#1f77b4', 'r2 (realized)')
ax.axhline(0.0, color='black', ls=':', lw=0.7, alpha=0.5)
shade_disruption(ax)
ax.set_ylabel('r2')
ax.set_ylim(-1.3, 1.3)
ax.set_title('(3) Realized r2 over time — range {−1, 0, +1}')
ax.set_xlabel('Period')
ax.grid(True, alpha=0.3)

plt.tight_layout(rect=[0, 0, 1, 0.96])
save_fig(fig, 'r2_inputs')


# =========================================================================
# r3 — Inventory band inputs
# =========================================================================
fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
fig.suptitle(
    'r3 Inputs — Inventory vs Up-to-Level Band Feeds into r3 = sign(n_in − n_out)\n'
    f'(range {{−1, 0, +1}}, band = utl ± 2σ, {n_seeds} eval seeds averaged)',
    fontsize=11)

ax = axes[0]
# Inventory + utl band
inv_m, inv_se = mean_se('r3_inv_last')
utl_m, _ = mean_se('r3_utl_last')
std_m, _ = mean_se('r3_utl_std')
upper = utl_m + 2.0 * std_m
lower = utl_m - 2.0 * std_m
ax.plot(periods, inv_m, color='#1f77b4', lw=1.5, label='DS inventory')
ax.fill_between(periods, inv_m - inv_se, inv_m + inv_se, color='#1f77b4', alpha=0.2)
ax.plot(periods, utl_m, color='#2ca02c', lw=1.2, ls='--', label='Up-to-level')
ax.fill_between(periods, lower, upper, color='#2ca02c', alpha=0.15,
                label='utl ± 2σ (target band)')
shade_disruption(ax, label_in_legend=True)
ax.set_ylabel('Inventory level')
ax.set_title('(1) Inventory vs target band — r3 = +1 only when inventory inside band')
ax.legend(loc='upper left', fontsize=8)
ax.grid(True, alpha=0.3)

ax = axes[1]
# Fraction in-band
df_frac = df.copy()
total = df_frac['r3_n_in_band'] + df_frac['r3_n_out_band']
df_frac['frac_in_band'] = np.where(total > 0, df_frac['r3_n_in_band'] / total, np.nan)
g = df_frac.groupby('period')['frac_in_band']
m = g.mean().reindex(periods).values
se = g.sem().reindex(periods).fillna(0).values
ax.plot(periods, m, color='#9467bd', lw=1.5, label='fraction in-band')
ax.fill_between(periods, m - se, m + se, color='#9467bd', alpha=0.2)
ax.axhline(0.5, color='black', ls=':', lw=0.7, alpha=0.5, label='50% threshold')
shade_disruption(ax)
ax.set_ylabel('Fraction in-band')
ax.set_ylim(-0.05, 1.05)
ax.set_title('(2) Fraction of window periods inside the band — r3 = +1 needs > 0.5')
ax.legend(loc='upper left', fontsize=8)
ax.grid(True, alpha=0.3)

ax = axes[2]
plot_line(ax, 'r3', '#1f77b4', 'r3 (realized)')
ax.axhline(0.0, color='black', ls=':', lw=0.7, alpha=0.5)
shade_disruption(ax)
ax.set_ylabel('r3')
ax.set_ylim(-1.3, 1.3)
ax.set_title('(3) Realized r3 over time — range {−1, 0, +1}')
ax.set_xlabel('Period')
ax.grid(True, alpha=0.3)

plt.tight_layout(rect=[0, 0, 1, 0.96])
save_fig(fig, 'r3_inputs')


# =========================================================================
# r4 — DS backlog inputs
# =========================================================================
fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
fig.suptitle(
    'r4 Inputs — DS Backlog Feeds into r4 = _compute_backlog_balance(ds_backlog)\n'
    f'(range [−3, +1], {n_seeds} eval seeds averaged, {TRAIN_EPISODES}-episode trained agent)',
    fontsize=11)

ax = axes[0]
plot_line(ax, 'ds_backlog', '#d62728', 'DS 1 backlog')
shade_disruption(ax, label_in_legend=True)
ax.set_ylabel('DS backlog')
ax.set_title('(1) DS 1 backlog over time')
ax.legend(loc='upper left', fontsize=8)
ax.grid(True, alpha=0.3)

ax = axes[1]
df_d4 = df.sort_values(['seed', 'period']).copy()
df_d4['delta_ds_backlog'] = df_d4.groupby('seed')['ds_backlog'].diff()
g = df_d4.groupby('period')['delta_ds_backlog']
m = g.mean().reindex(periods).values
se = g.sem().reindex(periods).fillna(0).values
ax.plot(periods, m, color='#d62728', lw=1.2, label='Δ DS backlog')
ax.fill_between(periods, m - se, m + se, color='#d62728', alpha=0.2)
ax.axhline(0.0, color='black', ls=':', lw=0.7, alpha=0.5)
shade_disruption(ax)
ax.set_ylabel('Δ DS backlog')
ax.set_title('(2) Period-over-period change — r4 penalizes Σ(Δb) > 0')
ax.legend(loc='upper left', fontsize=8)
ax.grid(True, alpha=0.3)

ax = axes[2]
plot_line(ax, 'r4', '#d62728', 'r4 (realized)')
ax.axhline(0.0, color='black', ls=':', lw=0.7, alpha=0.5)
shade_disruption(ax)
ax.set_ylabel('r4')
ax.set_title('(3) Realized r4 over time — range [−3, +1]')
ax.set_xlabel('Period')
ax.grid(True, alpha=0.3)

plt.tight_layout(rect=[0, 0, 1, 0.96])
save_fig(fig, 'r4_inputs')


# =========================================================================
# r6 — MN alignment inputs
# =========================================================================
fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
fig.suptitle(
    'r6 Inputs — MN Production / Demand Ratio Feeds into r6 = +1 if all periods in [0.5, 1.5]\n'
    f'(range {{−1, +1}}, {n_seeds} eval seeds averaged, {TRAIN_EPISODES}-episode trained agent)',
    fontsize=11)

ax = axes[0]
plot_line(ax, 'r6_mn_prod', '#1f77b4', 'MN production (latest period)')
plot_line(ax, 'r6_mn_demand', '#ff7f0e', 'MN demand (latest period)')
shade_disruption(ax, label_in_legend=True)
ax.set_ylabel('Units')
ax.set_title('(1) MN production vs demand (latest period of window)')
ax.legend(loc='upper left', fontsize=8)
ax.grid(True, alpha=0.3)

ax = axes[1]
plot_line(ax, 'r6_ratio', '#9467bd', 'production / demand (latest period)')
pmt_lower = float(df['r6_pmt_lower'].iloc[0]) if 'r6_pmt_lower' in df.columns else 0.5
pmt_upper = float(df['r6_pmt_upper'].iloc[0]) if 'r6_pmt_upper' in df.columns else 1.5
ax.axhline(pmt_lower, color='black', lw=1.2, ls='--', label=f'PMT_LOWER = {pmt_lower:.2f}')
ax.axhline(pmt_upper, color='black', lw=1.2, ls='--', label=f'PMT_UPPER = {pmt_upper:.2f}')
ax.axhspan(pmt_lower, pmt_upper, alpha=0.08, color='green', label='Safe band')
shade_disruption(ax)
ax.set_ylabel('Ratio = prod / demand')
ax.set_title('(2) Ratio with [0.5, 1.5] safe band — r6 = +1 only if every window period is inside')
# Cap y for readability if ratio explodes
ratio_vals = df['r6_ratio'].replace([np.inf, -np.inf], np.nan).dropna()
if len(ratio_vals):
    p99 = float(np.percentile(ratio_vals, 99))
    ax.set_ylim(0, max(2.0, min(p99 * 1.1, 5.0)))
ax.legend(loc='upper left', fontsize=8)
ax.grid(True, alpha=0.3)

ax = axes[2]
plot_line(ax, 'r6', '#1f77b4', 'r6 (realized)')
ax.axhline(0.0, color='black', ls=':', lw=0.7, alpha=0.5)
shade_disruption(ax)
ax.set_ylabel('r6')
ax.set_ylim(-1.3, 1.3)
ax.set_title('(3) Realized r6 over time — range {−1, +1}')
ax.set_xlabel('Period')
ax.grid(True, alpha=0.3)

plt.tight_layout(rect=[0, 0, 1, 0.96])
save_fig(fig, 'r6_inputs')

print('\nDone. r5 inputs already covered by r5_diagnostic.png panels 1+2.')
