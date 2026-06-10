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
    regimes = ['sat70', 'sat50', 'sat30']
    durations = [5, 17, 48]
    best_label = np.empty((3, 3), dtype=object)
    ratio = np.zeros((3, 3))
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
            ratio[i, j] = cands[best] / base
            if best == 'ladder_a':
                lab = 'no action'
            elif best.startswith('ladder'):
                lab = 'routing'
            elif best.startswith('sat_full'):
                lab = 'compound'
            else:
                lab = 'buffer'
            best_label[i, j] = f'{lab}\n{cands[best]/1e3:,.0f}k ({ratio[i,j]:.2f}x)'
    fig, ax = plt.subplots(figsize=(8.5, 5.5))
    im = ax.imshow(ratio, cmap='RdYlGn_r', vmin=0.2, vmax=1.1)
    for i in range(3):
        for j in range(3):
            if best_label[i, j]:
                ax.text(j, i, best_label[i, j], ha='center', va='center', fontsize=9)
    ax.set_xticks(range(3))
    ax.set_xticklabels([f'duration {d}' for d in durations])
    ax.set_yticks(range(3))
    ax.set_yticklabels(['sat70 (no scarcity)', 'sat50 (mild)', 'sat30 (severe)'])
    ax.set_title('Lever-flip map: best measured policy per cell\n'
                 '(cell text: lever, its dp-cost, ratio vs no-action; urgent0)',
                 fontsize=10)
    fig.colorbar(im, label='best dp-cost / no-action dp-cost')
    plt.tight_layout()
    for ext in ('png', 'pdf'):
        fig.savefig(os.path.join(FDIR, f'lever_flip_map.{ext}'),
                    dpi=170, bbox_inches='tight')
    plt.close(fig)


if __name__ == '__main__':
    os.makedirs(FDIR, exist_ok=True)
    fig_frontier()
    fig_flip_map()
    print('figures written to', FDIR)
