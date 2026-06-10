"""Figures for the value-decomposition report:
  1. premium-coverage frontier at the primary cell (sat50, d48)
  2. lever-flip map (severity x duration heat grid of best-policy cost ratios)
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from value_decomposition_study.analyze_phase2 import seed_stats, cell_dir

FDIR = os.path.join(HERE, 'results', 'figures')


def mean_stats(path, dis_end=157):
    s = seed_stats(pd.read_csv(path), dis_end)
    return s.mean(numeric_only=True)


def fig_frontier():
    d = cell_dir('sat50', 48, 'urgent0')
    base = mean_stats(os.path.join(d, 'ladder_a.csv'))
    series = {
        'buffer-only (at healthy DS)': [f'sat_buffer_B{b}_healthy.csv'
                                        for b in (240, 480, 960, 1440)],
        'compound (buffer+reroute+taper)': [f'sat_full_compound_B{b}.csv'
                                            for b in (960, 1440)],
    }
    points = {
        'no action (baseline a)': 'ladder_a.csv',
        'trust routing (c)': 'ladder_c.csv',
        'oracle reroute (d)': 'ladder_d.csv',
        'reroute+taper (no buffer)': 'h5_compound_full.csv',
    }
    fig, ax = plt.subplots(figsize=(9, 6))
    for label, files in series.items():
        xs, ys = [], []
        for f in files:
            p = os.path.join(d, f)
            if os.path.exists(p):
                m = mean_stats(p)
                xs.append(m['pre_cost'] - base['pre_cost'])
                ys.append(base['dp_cost'] - m['dp_cost'])
        ax.plot(xs, ys, 'o-', lw=1.8, ms=7, label=label)
    markers = ['s', '^', 'D', 'v']
    for (label, f), mk in zip(points.items(), markers):
        p = os.path.join(d, f)
        if os.path.exists(p):
            m = mean_stats(p)
            ax.scatter([m['pre_cost'] - base['pre_cost']],
                       [base['dp_cost'] - m['dp_cost']], marker=mk, s=90,
                       label=label, zorder=5)
    ax.set_xlabel('Premium (extra normal-times cost vs no action)')
    ax.set_ylabel('Coverage (during+post cost reduction vs no action)')
    ax.set_title('Premium-coverage frontier under scarcity (sat50, d48, urgent0, '
                 'reporting seeds)', fontsize=11)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    plt.tight_layout()
    for ext in ('png', 'pdf'):
        fig.savefig(os.path.join(FDIR, f'frontier_sat50_d48.{ext}'),
                    dpi=170, bbox_inches='tight')
    plt.close(fig)


def fig_flip_map():
    """Categorical map: cell color = WHICH lever wins (the message); numbers in text.
    Redesigned 2026-06-11: the earlier continuous red-green ratio shading conflated
    'which lever' with 'how much' and read poorly."""
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch
    regimes = ['sat70', 'sat50', 'sat30']
    durations = [5, 17, 48]
    LEVERS = ['no action', 'routing', 'compound', 'buffer']
    COLORS = {'no action': '#d9d9d9', 'routing': '#aec7e8',
              'compound': '#98df8a', 'buffer': '#ffbb78'}
    cat = np.zeros((3, 3), dtype=int)
    label = np.empty((3, 3), dtype=object)
    for i, reg in enumerate(regimes):
        for j, dur in enumerate(durations):
            d = cell_dir(reg, dur, 'urgent0')
            dis_end = 109 + dur
            cands = {}
            for f in os.listdir(d) if os.path.isdir(d) else []:
                if f.endswith('.csv') and '_tune' not in f:
                    cands[f[:-4]] = mean_stats(os.path.join(d, f), dis_end)['dp_cost']
            if not cands:
                continue
            base = cands.get('ladder_a', np.nan)
            best = min(cands, key=cands.get)
            if best == 'ladder_a':
                lab = 'no action'
            elif best.startswith('ladder'):
                lab = 'routing'
            elif best.startswith('sat_full'):
                lab = 'compound'
            else:
                lab = 'buffer'
            cat[i, j] = LEVERS.index(lab)
            saving = 1 - cands[best] / base
            label[i, j] = (f'{lab.upper()}\ncost {cands[best]/1e3:,.0f}k\n'
                           f'saves {saving:.0%}' if saving > 0.005
                           else f'{lab.upper()}\ncost {cands[best]/1e3:,.0f}k\n(nothing helps)')
    fig, ax = plt.subplots(figsize=(8.2, 5.2))
    ax.imshow(cat, cmap=ListedColormap([COLORS[l] for l in LEVERS]),
              vmin=0, vmax=3)
    for i in range(3):
        for j in range(3):
            if label[i, j]:
                ax.text(j, i, label[i, j], ha='center', va='center', fontsize=9.5)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_xticks(np.arange(-0.5, 3), minor=True)
    ax.set_yticks(np.arange(-0.5, 3), minor=True)
    ax.grid(which='minor', color='white', linewidth=2.5)
    ax.tick_params(which='both', length=0)
    ax.set_xticks(range(3))
    ax.set_xticklabels(['short (5 periods)', 'moderate (17)', 'long (48)'], fontsize=10)
    ax.set_yticks(range(3))
    ax.set_yticklabels(['mild\n(surviving chain\nhas headroom)',
                        'moderate\n(supply 220 vs\ndemand 240)',
                        'severe\n(supply 140 vs\ndemand 240)'], fontsize=9)
    ax.set_xlabel('disruption duration')
    ax.set_ylabel('scarcity severity')
    ax.set_title('Which lever wins, by regime (urgent0, reporting seeds)\n'
                 'cell: best policy, its during+post cost, saving vs doing nothing',
                 fontsize=11)
    ax.legend(handles=[Patch(facecolor=COLORS[l], label=l) for l in LEVERS],
              loc='upper left', bbox_to_anchor=(1.01, 1.0), fontsize=9,
              title='best lever', title_fontsize=9)
    plt.tight_layout()
    for ext in ('png', 'pdf'):
        fig.savefig(os.path.join(FDIR, f'lever_flip_map.{ext}'),
                    dpi=170, bbox_inches='tight')
    plt.close(fig)


def fig_ds_seat():
    """H8: share of base stock's PSC-profit loss removed by simple DS-seat rules,
    thesis world. Values from analyze_ds_seat (reporting seeds for finalists)."""
    rows = [
        ('shed x taper x standing (compound)', 0.491, '#2ca02c'),
        ('shed x taper', 0.466, '#2ca02c'),
        ('taper alone*', 0.249, '#ff7f0e'),
        ('shed alone (demand-shaping)', 0.218, '#1f77b4'),
        ('standing buffer B480', 0.052, '#1f77b4'),
        ('shed_inverse (direction control)', -0.143, '#d62728'),
    ]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    labels = [r[0] for r in rows]
    vals = [r[1] for r in rows]
    cols = [r[2] for r in rows]
    y = range(len(rows))
    ax.barh(list(y), vals, color=cols)
    ax.axvline(0, color='gray', lw=1)
    ax.axvline(0.89, color='black', ls='--', lw=1.4,
               label='thesis RL claim (~89%, Table 3.9 — unreplicated)')
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("share of base stock's episode-PSC-profit loss removed (thesis world)")
    ax.set_title('Simple DS-seat rules vs base stock vs the thesis RL claim\n'
                 '(*taper: gain is dead-factory bookkeeping; +9% lost patients alone '
                 'under urgent20)', fontsize=10)
    ax.legend(fontsize=8, loc='lower right')
    ax.grid(alpha=0.3, axis='x')
    plt.tight_layout()
    for ext in ('png', 'pdf'):
        fig.savefig(os.path.join(FDIR, f'ds_seat_shares.{ext}'),
                    dpi=170, bbox_inches='tight')
    plt.close(fig)


if __name__ == '__main__':
    os.makedirs(FDIR, exist_ok=True)
    fig_frontier()
    fig_flip_map()
    fig_ds_seat()
    print('figures written to', FDIR)
