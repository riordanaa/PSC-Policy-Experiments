"""Comparison figures for the routing ladder. Reads results/{config}/{rung}.csv,
writes PNG+PDF into results/figures/."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

DIS_START, DIS_END = 110, 157
RUNG_LABELS = {
    'a': '(a) baseline (HC2 equal-split)',
    'b': '(b) HC2 trust-split',
    'c': '(c) b + sharper reroute + write-off',
    'd': '(d) b + onset reroute (oracle)',
}
RUNG_COLORS = {'a': '#d62728', 'b': '#1f77b4', 'c': '#2ca02c', 'd': '#9467bd'}
HOLD, BACK = 1.0, 10.0
AGENTS = ['ds1', 'ds2', 'mn1', 'mn2', 'hc1', 'hc2']


def load(config, rungs):
    out = {}
    for r in rungs:
        out[r] = pd.read_csv(os.path.join(HERE, 'results', config, f'{r}.csv'))
    return out


def shade(ax, legend=False):
    ax.axvspan(DIS_START, DIS_END, alpha=0.12, color='red',
               label='disruption (110-157)' if legend else None)


def fig_backlog_trajectories(data, config, outdir):
    fig, axes = plt.subplots(2, 1, figsize=(11, 7.5), sharex=True)
    for ax, col, title in ((axes[0], 'ds1_backlog', 'DS_disrupted backlog'),
                           (axes[1], 'ds2_backlog', 'DS_healthy backlog')):
        for r, df in data.items():
            g = df.groupby('period')[col]
            m, s = g.mean(), g.sem().fillna(0)
            ax.plot(m.index, m.values, color=RUNG_COLORS[r], lw=1.6,
                    label=RUNG_LABELS[r])
            ax.fill_between(m.index, m - s, m + s, color=RUNG_COLORS[r], alpha=0.15)
        shade(ax, legend=(ax is axes[0]))
        ax.set_ylabel('Backlog (units)')
        ax.set_title(title, loc='left', fontsize=10)
        ax.grid(alpha=0.3)
    axes[0].legend(fontsize=8)
    axes[1].set_xlabel('Period')
    fig.suptitle(f'Routing ladder: distributor backlogs ({config}, mean +/- SE, '
                 f'reporting seeds)', fontsize=11)
    plt.tight_layout(rect=[0, 0, 1, 0.97])
    for ext in ('png', 'pdf'):
        fig.savefig(os.path.join(outdir, f'backlog_trajectories_{config}.{ext}'),
                    dpi=170, bbox_inches='tight')
    plt.close(fig)


def fig_cost_by_phase(data, config, outdir):
    phases = {'pre': (60, 109), 'during': (110, 157), 'post': (158, 300)}
    rungs = list(data)
    hold = {r: [] for r in rungs}
    back = {r: [] for r in rungs}
    for r, df in data.items():
        nseeds = df['seed'].nunique()
        for lo, hi in phases.values():
            d = df[(df['period'] >= lo) & (df['period'] <= hi)]
            hold[r].append(sum(HOLD * d[f'{a}_inventory'].sum()
                               for a in AGENTS) / nseeds)
            back[r].append(sum(BACK * d[f'{a}_backlog'].sum()
                               for a in AGENTS) / nseeds)
    x = range(len(phases))
    width = 0.8 / len(rungs)
    fig, ax = plt.subplots(figsize=(10, 5))
    for i, r in enumerate(rungs):
        pos = [xx + (i - (len(rungs) - 1) / 2) * width for xx in x]
        ax.bar(pos, back[r], width * 0.95, color=RUNG_COLORS[r],
               label=RUNG_LABELS[r])
        ax.bar(pos, hold[r], width * 0.95, bottom=back[r],
               color=RUNG_COLORS[r], alpha=0.45)
    ax.set_xticks(list(x))
    ax.set_xticklabels(list(phases))
    ax.set_ylabel('System cost per phase (units x cost)')
    ax.set_title(f'System-level cost by phase ({config}; solid = backlog cost, '
                 f'faded = holding cost; all six agents)', fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3, axis='y')
    plt.tight_layout()
    for ext in ('png', 'pdf'):
        fig.savefig(os.path.join(outdir, f'cost_by_phase_{config}.{ext}'),
                    dpi=170, bbox_inches='tight')
    plt.close(fig)


def fig_split_share(data, config, outdir):
    fig, ax = plt.subplots(figsize=(10, 4.5))
    for r, df in data.items():
        tot = df['hc2_order_to_ds1'] + df['hc2_order_to_ds2']
        share = (df['hc2_order_to_ds1'] / tot.clip(lower=1)).rename('share')
        g = pd.concat([df['period'], share], axis=1).groupby('period')['share']
        m = g.mean().rolling(5, min_periods=1).mean()
        ax.plot(m.index, m.values, color=RUNG_COLORS[r], lw=1.6, label=RUNG_LABELS[r])
    shade(ax, legend=True)
    ax.axhline(0.5, color='gray', ls=':', lw=1)
    ax.set_ylabel('HC_equal share of orders to DS_disrupted')
    ax.set_xlabel('Period')
    ax.set_title(f'How fast each rung routes HC_equal away from the dead chain '
                 f'({config}, 5-period smoothed mean)', fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    plt.tight_layout()
    for ext in ('png', 'pdf'):
        fig.savefig(os.path.join(outdir, f'split_share_{config}.{ext}'),
                    dpi=170, bbox_inches='tight')
    plt.close(fig)


def fig_hc_dispersion(data, config, outdir):
    fig, ax = plt.subplots(figsize=(10, 4.5))
    for r, df in data.items():
        gap = df['hc1_backlog'] - df['hc2_backlog']
        g = pd.concat([df['period'], gap.rename('gap')], axis=1).groupby('period')['gap']
        m = g.mean()
        ax.plot(m.index, m.values, color=RUNG_COLORS[r], lw=1.5, label=RUNG_LABELS[r])
    shade(ax, legend=True)
    ax.axhline(0, color='gray', ls=':', lw=1)
    ax.set_ylabel('HC_trust backlog - HC_equal backlog')
    ax.set_xlabel('Period')
    ax.set_title(f'HC dispersion: who bears the shortage ({config}, mean over seeds)',
                 fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    plt.tight_layout()
    for ext in ('png', 'pdf'):
        fig.savefig(os.path.join(outdir, f'hc_dispersion_{config}.{ext}'),
                    dpi=170, bbox_inches='tight')
    plt.close(fig)


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', default='urgent0')
    ap.add_argument('--rungs', default='a,b,c,d')
    args = ap.parse_args()
    outdir = os.path.join(HERE, 'results', 'figures')
    os.makedirs(outdir, exist_ok=True)
    data = load(args.config, args.rungs.split(','))
    fig_backlog_trajectories(data, args.config, outdir)
    fig_cost_by_phase(data, args.config, outdir)
    fig_split_share(data, args.config, outdir)
    fig_hc_dispersion(data, args.config, outdir)
    print(f'figures written to {outdir}')
