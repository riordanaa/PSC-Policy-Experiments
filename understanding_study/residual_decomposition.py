"""E2: what is rung (c)'s remaining during+post system cost made of?

Pure analysis of routing_study/results/urgent0/{a,c,d}.csv (no new simulation).
Decomposes system cost by agent x phase x (holding | backlog), quantifies the
post-disruption glut, and cross-checks totals against routing_study summary.csv.

Outputs (understanding_study/results/):
  residual_decomposition.csv   per rung x agent x phase x component, mean over seeds
  glut_metrics.csv             per rung glut quantification
  figures/residual_breakdown.{png,pdf}
  figures/glut_trajectories.{png,pdf}
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

HOLD, BACK = 1.0, 10.0
AGENTS = ['ds1', 'ds2', 'mn1', 'mn2', 'hc1', 'hc2']
AGENT_LABELS = {'ds1': 'DS_disrupted', 'ds2': 'DS_healthy',
                'mn1': 'MN_disrupted', 'mn2': 'MN_healthy',
                'hc1': 'HC_trust', 'hc2': 'HC_equal'}
PHASES = {'pre': (60, 109), 'during': (110, 157), 'post': (158, 300)}
RUNGS = {'a': 'baseline', 'c': 'routing-fixed', 'd': 'onset reroute'}
RDIR = os.path.join(ROOT, 'routing_study', 'results', 'urgent0')


def load(rung):
    return pd.read_csv(os.path.join(RDIR, f'{rung}.csv'))


def decompose(df):
    nseeds = df['seed'].nunique()
    rows = []
    for phase, (lo, hi) in PHASES.items():
        d = df[(df['period'] >= lo) & (df['period'] <= hi)]
        for a in AGENTS:
            rows.append(dict(phase=phase, agent=a,
                             holding=HOLD * d[f'{a}_inventory'].sum() / nseeds,
                             backlog=BACK * d[f'{a}_backlog'].sum() / nseeds))
    return pd.DataFrame(rows)


def glut_metrics(df):
    """Post-disruption excess inventory vs the pre-disruption mean, system + per agent."""
    nseeds = df['seed'].nunique()
    pre = df[(df['period'] >= 60) & (df['period'] <= 109)]
    post = df[df['period'] >= 158]
    out = {}
    sys_pre = sum(pre[f'{a}_inventory'].mean() for a in AGENTS)
    sys_inv = post.groupby('period')[[f'{a}_inventory' for a in AGENTS]].mean().sum(axis=1)
    out['system_pre_mean_inv'] = sys_pre
    out['system_post_peak_inv'] = sys_inv.max()
    out['system_glut_peak_excess'] = sys_inv.max() - sys_pre
    out['system_glut_area'] = (sys_inv - sys_pre).clip(lower=0).sum()
    for a in AGENTS:
        a_pre = pre[f'{a}_inventory'].mean()
        a_inv = post.groupby('period')[f'{a}_inventory'].mean()
        out[f'{a}_glut_peak_excess'] = a_inv.max() - a_pre
    out['post_holding_cost'] = HOLD * sum(
        post[f'{a}_inventory'].sum() for a in AGENTS) / nseeds
    return out


def main():
    os.makedirs(os.path.join(HERE, 'results', 'figures'), exist_ok=True)
    dec_rows, glut_rows = [], []
    trajs = {}
    for rung in RUNGS:
        df = load(rung)
        dec = decompose(df)
        dec['rung'] = rung
        dec_rows.append(dec)
        g = glut_metrics(df)
        g['rung'] = rung
        glut_rows.append(g)
        trajs[rung] = df

    dec = pd.concat(dec_rows, ignore_index=True)
    dec.to_csv(os.path.join(HERE, 'results', 'residual_decomposition.csv'), index=False)
    glut = pd.DataFrame(glut_rows).set_index('rung')
    glut.to_csv(os.path.join(HERE, 'results', 'glut_metrics.csv'))

    # cross-check vs routing_study summary
    summ = pd.read_csv(os.path.join(RDIR, 'summary.csv')).set_index('rung')
    for rung in RUNGS:
        d = dec[dec['rung'] == rung]
        dp = d[d['phase'].isin(['during', 'post'])]
        mine = dp['holding'].sum() + dp['backlog'].sum()
        ref = (summ.loc[rung, 'during_system_cost_mean']
               + summ.loc[rung, 'post_system_cost_mean'])
        assert abs(mine - ref) / ref < 1e-6, (rung, mine, ref)
    print('cross-check vs routing_study summary.csv: PASS')

    # ---- print the rung-c story ----
    c = dec[dec['rung'] == 'c']
    print('\n=== rung (c) residual, during+post, by agent (mean over seeds) ===')
    for a in AGENTS:
        dur = c[(c['agent'] == a) & (c['phase'] == 'during')].iloc[0]
        pos = c[(c['agent'] == a) & (c['phase'] == 'post')].iloc[0]
        tot = dur['holding'] + dur['backlog'] + pos['holding'] + pos['backlog']
        print(f"  {AGENT_LABELS[a]:13s}: total {tot:>12,.0f}   "
              f"during(b/h) {dur['backlog']:>10,.0f}/{dur['holding']:>8,.0f}   "
              f"post(b/h) {pos['backlog']:>10,.0f}/{pos['holding']:>8,.0f}")
    print('\n=== glut ===')
    print(glut[['system_pre_mean_inv', 'system_post_peak_inv',
                'system_glut_peak_excess', 'system_glut_area',
                'post_holding_cost']].round(0).to_string())

    # ---- figure: stacked residual breakdown ----
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.6), sharey=True)
    for ax, rung in zip(axes, RUNGS):
        d = dec[(dec['rung'] == rung) & (dec['phase'].isin(['during', 'post']))]
        agg = d.groupby('agent')[['backlog', 'holding']].sum().reindex(AGENTS)
        x = range(len(AGENTS))
        ax.bar(x, agg['backlog'], color='#d62728', label='backlog cost')
        ax.bar(x, agg['holding'], bottom=agg['backlog'], color='#1f77b4',
               alpha=0.65, label='holding cost')
        ax.set_xticks(list(x))
        ax.set_xticklabels([AGENT_LABELS[a] for a in AGENTS], rotation=40,
                           ha='right', fontsize=8)
        ax.set_title(f'rung ({rung}) {RUNGS[rung]}\n'
                     f'total {agg.values.sum():,.0f}', fontsize=10)
        ax.grid(alpha=0.3, axis='y')
    axes[0].set_ylabel('during+post cost (mean over seeds)')
    axes[0].legend(fontsize=8)
    fig.suptitle('Where the remaining cost lives, by agent (urgent0)', fontsize=11)
    plt.tight_layout(rect=[0, 0, 1, 0.94])
    for ext in ('png', 'pdf'):
        fig.savefig(os.path.join(HERE, 'results', 'figures',
                                 f'residual_breakdown.{ext}'),
                    dpi=170, bbox_inches='tight')
    plt.close(fig)

    # ---- figure: system inventory trajectories (the glut, or its absence) ----
    fig, ax = plt.subplots(figsize=(10, 4.5))
    colors = {'a': '#d62728', 'c': '#2ca02c', 'd': '#9467bd'}
    for rung, df in trajs.items():
        inv = df.groupby('period')[[f'{a}_inventory' for a in AGENTS]].mean().sum(axis=1)
        ax.plot(inv.index, inv.values, color=colors[rung], lw=1.6,
                label=f'({rung}) {RUNGS[rung]}')
    ax.axvspan(110, 157, alpha=0.12, color='red', label='disruption')
    ax.set_xlabel('Period')
    ax.set_ylabel('System inventory (all six agents, mean over seeds)')
    ax.set_title('Post-disruption glut check: system inventory over time (urgent0)',
                 fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    plt.tight_layout()
    for ext in ('png', 'pdf'):
        fig.savefig(os.path.join(HERE, 'results', 'figures',
                                 f'glut_trajectories.{ext}'),
                    dpi=170, bbox_inches='tight')
    plt.close(fig)
    print('\nfigures written')


if __name__ == '__main__':
    main()
