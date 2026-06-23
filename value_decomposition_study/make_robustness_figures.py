"""Figures for the robustness report (viridis, self-contained takeaway titles).
Writes PDFs to report/figures/. Also prints the DS1 channel-decomposition numbers used in
the report's body table. Run AFTER exp_robustness.py --mode sweep."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import cm

from value_decomposition_study.analyze_robustness import cell_metrics, ds1_channels, P
from routing_study.metrics import AGENTS

FIG = os.path.join(HERE, 'report', 'figures')
os.makedirs(FIG, exist_ok=True)
C_BASE, C_SHED = cm.viridis(0.18), cm.viridis(0.68)   # categorical: baseline vs shed
plt.rcParams.update({'font.size': 11, 'axes.spines.top': False, 'axes.spines.right': False,
                     'figure.autolayout': True})


def save(fig, name):
    p = os.path.join(FIG, name)
    fig.savefig(p, bbox_inches='tight')
    plt.close(fig)
    print('wrote', p)


def fig_capacity_divergence():
    """Two panels (shared x) so BOTH series are readable: the system (top) crosses into deep
    negative as capacity falls, while DS1's own gain (bottom, zoomed) stays positive throughout
    --- that gap IS the misaligned incentive. A single shared axis makes DS1 look flat."""
    caps, ds1, sysd = [], [], []
    for n in [12, 14, 18, 24, 40]:
        b, s = cell_metrics(P('cap_sweep', 'urgent0', 'baseline', n, 0.1)), \
               cell_metrics(P('cap_sweep', 'urgent0', 'shed', n, 0.1))
        idx = b.index.intersection(s.index)
        caps.append(n * 10)
        ds1.append((s.loc[idx, 'ds1_episode_profit'] - b.loc[idx, 'ds1_episode_profit']).mean() / 1e6)
        sysd.append((s.loc[idx, 'sys_episode_profit'] - b.loc[idx, 'sys_episode_profit']).mean() / 1e6)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(6.7, 5.4), sharex=True,
                                   gridspec_kw={'height_ratios': [1.45, 1]})
    # top: SYSTEM (big swing; red below zero = shed hurts the system)
    ax1.axhspan(-6.2, 0, color='#f7e0e0', alpha=0.7, zorder=0)
    ax1.axvspan(180, 240, color='0.86', alpha=0.6, zorder=0)
    ax1.axhline(0, color='0.5', lw=1)
    ax1.plot(caps, sysd, 's-', color=C_BASE, lw=2.6, ms=8)
    ax1.set_ylim(-6.0, 1.2)
    ax1.set_ylabel('SYSTEM profit Δ\n(shed−base), \\$M')
    ax1.annotate('shed now hurts\nthe system', xy=(140, -5.4), xytext=(250, -4.2),
                 fontsize=9, color='#7a2020', ha='center',
                 arrowprops=dict(arrowstyle='->', color='#7a2020'))
    ax1.set_title("Shed is win–win ONLY with spare capacity — below ~180–240 the SYSTEM\n"
                  "collapses (top) while the DISTRIBUTOR keeps gaining (bottom): misaligned incentive",
                  fontweight='bold', fontsize=10.5)
    # bottom: DS1 own (zoomed; green = always a gain)
    ax2.axhspan(0, 0.4, color='#e2f0e4', alpha=0.7, zorder=0)
    ax2.axvspan(180, 240, color='0.86', alpha=0.6, zorder=0)
    ax2.axhline(0, color='0.5', lw=1)
    ax2.plot(caps, ds1, 'o-', color=C_SHED, lw=2.6, ms=8)
    ax2.set_ylim(0, 0.32)
    ax2.set_ylabel("DS1's OWN profit Δ\n(shed−base), \\$M")
    ax2.set_xlabel('Healthy-manufacturer (MN2) capacity, units/period')
    ax2.annotate('distributor gains at every capacity', xy=(255, 0.09),
                 fontsize=9, color='#1f5a2a', ha='center')
    ax1.set_xlim(110, 300)   # plateau above ~240; cut the flat 240->400 stretch (also sets ax2)
    save(fig, 'fig1_capacity_divergence.pdf')


def fig_fill_by_capacity():
    """Per-hospital during-fill vs capacity: HC2 (captive) is consistently worse than HC1
    (trust/rerouting) under shed, UNTIL the lowest capacity, where the inversion appears
    (HC1 < HC2). Baseline (dashed) never inverts -> the inversion is shed-induced."""
    caps = []
    h1s, h2s, h1b, h2b = [], [], [], []
    for n in [12, 14, 18, 24, 40]:
        s = cell_metrics(P('cap_sweep', 'urgent0', 'shed', n, 0.1))
        b = cell_metrics(P('cap_sweep', 'urgent0', 'baseline', n, 0.1))
        caps.append(n * 10)
        h1s.append(s['during_fill_hc1'].mean()); h2s.append(s['during_fill_hc2'].mean())
        h1b.append(b['during_fill_hc1'].mean()); h2b.append(b['during_fill_hc2'].mean())
    fig, ax = plt.subplots(figsize=(6.8, 4.3))
    ax.axvspan(180, 240, color='0.9', alpha=0.6, zorder=0)
    ax.plot(caps, h1s, 'o-', color=C_SHED, lw=2.6, ms=7, label='HC1 trust/rerouting — shed')
    ax.plot(caps, h2s, 's-', color=C_BASE, lw=2.6, ms=7, label='HC2 captive — shed')
    ax.plot(caps, h1b, 'o--', color=C_SHED, lw=1.3, ms=4, alpha=0.55, label='HC1 — baseline')
    ax.plot(caps, h2b, 's--', color=C_BASE, lw=1.3, ms=4, alpha=0.55, label='HC2 — baseline')
    ax.set_xlabel('Healthy-manufacturer (MN2) capacity, units/period')
    ax.set_ylabel('During-disruption fill rate')
    ax.set_xlim(110, 300)    # plateau above ~240; cut the flat 240->400 stretch
    ax.set_title("The captive hospital (HC2) is worse — until capacity is so scarce that shed\n"
                 "pushes the rerouting hospital (HC1) below it (trust back-fires; baseline never does)",
                 fontweight='bold', fontsize=10.5)
    ax.legend(frameon=False, fontsize=8.5, loc='lower right', ncol=2)
    save(fig, 'fig7_fill_by_capacity.pdf')


def fig_channel_during():
    """Where the shed-removed backlog goes vs capacity: shed always removes a small, steady
    backlog from DS1, but at scarce capacity it creates FAR MORE on the healthy chain DS2 ---
    the disruption is amplified, not relocated. (Replaces the DS1-only channel chart.)"""
    caps, ds1, ds2 = [], [], []
    for n in [12, 14, 18, 24, 40]:
        s = pd.read_csv(P('cap_sweep', 'urgent0', 'shed', n, 0.1))
        b = pd.read_csv(P('cap_sweep', 'urgent0', 'baseline', n, 0.1))
        caps.append(n * 10)
        d1 = 10.0 * (s[s['period'] >= 110]['ds1_backlog'].sum()
                     - b[b['period'] >= 110]['ds1_backlog'].sum()) / 20 / 1e6
        d2 = 10.0 * (s[s['period'] >= 110]['ds2_backlog'].sum()
                     - b[b['period'] >= 110]['ds2_backlog'].sum()) / 20 / 1e6
        ds1.append(d1); ds2.append(d2)
    fig, ax = plt.subplots(figsize=(6.8, 4.3))
    ax.axhline(0, color='0.5', lw=1)
    ax.axvspan(180, 240, color='0.9', alpha=0.6, zorder=0)
    ax.plot(caps, ds1, 'o-', color=C_SHED, lw=2.6, ms=7, label='DS1 (disrupted) — backlog removed by shed')
    ax.plot(caps, ds2, 's-', color=C_BASE, lw=2.6, ms=7, label='DS2 (healthy) — backlog created by shed')
    ax.set_xlim(110, 300)
    ax.set_xlabel('Healthy-manufacturer (MN2) capacity, units/period')
    ax.set_ylabel('During+post backlog-cost change\n(shed − baseline), \\$M')
    ax.set_title("Shed always removes a small, steady backlog from DS1 — but at scarce capacity it\n"
                 "creates FAR MORE on the healthy chain (the disruption is amplified, not relocated)",
                 fontweight='bold', fontsize=10)
    ax.legend(frameon=False, fontsize=9, loc='upper right')
    save(fig, 'fig2_channel_during.pdf')


def fig_externality():
    b = pd.read_csv(P('cap_sweep', 'urgent0', 'baseline', 14, 0.1))
    s = pd.read_csv(P('cap_sweep', 'urgent0', 'shed', 14, 0.1))
    ag = ['ds1', 'ds2', 'mn2', 'hc1']
    bk = lambda df: [10.0 * df[df['period'] >= 110][f'{a}_backlog'].sum() / 20 / 1e6 for a in ag]
    bm, sm = bk(b), bk(s)
    x = np.arange(len(ag)); w = 0.38
    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    ax.bar(x - w / 2, bm, w, color=C_BASE, label='baseline')
    ax.bar(x + w / 2, sm, w, color=C_SHED, label='shed')
    ax.set_xticks(x); ax.set_xticklabels(['DS1\n(disrupted)', 'DS2\n(healthy)',
                                          'MN2\n(healthy mfr)', 'HC1\n(the hospital)'])
    ax.set_ylabel('During+post backlog cost ($M)')
    ax.set_title("At scarce capacity (MN2=140), shed moves backlog OFF DS1\n"
                 "onto a healthy chain that can't absorb it — and onto HC1 itself",
                 fontweight='bold', fontsize=11.5)
    ax.legend(frameon=False, fontsize=9.5)
    save(fig, 'fig3_externality.pdf')


def fig_delta():
    ds, ret = [], []
    deltas = [0.05, 0.10, 0.20, 0.35, 0.50]
    for d in deltas:
        b, s = cell_metrics(P('delta_sweep', 'urgent0', 'baseline', 40, d)), \
               cell_metrics(P('delta_sweep', 'urgent0', 'shed', 40, d))
        idx = b.index.intersection(s.index)
        ds.append((s.loc[idx, 'ds1_episode_profit'] - b.loc[idx, 'ds1_episode_profit']).mean() / 1e6)
        ret.append(s['hc1_share_ds1_late_post'].mean())
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    ax.plot(deltas, ds, 'o-', color=C_SHED, lw=2.4, ms=7)
    ax.set_xlabel('trust sensitivity  δ')
    ax.set_ylabel("DS1 profit Δ (shed−base), \\$M", color=C_SHED)
    ax.tick_params(axis='y', colors=C_SHED)
    ax2 = ax.twinx(); ax2.spines['top'].set_visible(False)
    ax2.plot(deltas, ret, 's--', color='0.45', lw=1.8, ms=6)
    ax2.set_ylabel("HC1's order-share returned to DS1\n(late-post)", color='0.45')
    ax2.set_ylim(0, 1.0); ax2.tick_params(axis='y', colors='0.45')
    ax.set_title("Higher trust sensitivity only makes shed MORE profitable;\n"
                 "no instability — HC1 always returns (~0.50)", fontweight='bold', fontsize=11.5)
    save(fig, 'fig4_delta.pdf')


def fig_trust_trajectory():
    b = pd.read_csv(P('cap_sweep', 'urgent0', 'baseline', 40, 0.1))
    s = pd.read_csv(P('cap_sweep', 'urgent0', 'shed', 40, 0.1))
    bm = b.groupby('period')['hc1_trust_ds1'].mean()
    sm = s.groupby('period')['hc1_trust_ds1'].mean()
    fig, ax = plt.subplots(figsize=(6.8, 4.0))
    ax.axvspan(110, 157, color='0.88', alpha=0.7, zorder=0)
    ax.text(133, 0.05, 'disruption', ha='center', fontsize=9, color='0.4')
    ax.plot(bm.index, bm.values, color=C_BASE, lw=2.0, label='baseline (natural reroute)')
    ax.plot(sm.index, sm.values, color=C_SHED, lw=2.0, label='shed (DS1 sheds HC1)')
    ax.set_xlabel('period'); ax.set_ylabel("HC1's trust in DS1 (disrupted distributor)")
    ax.set_xlim(60, 300); ax.set_ylim(-0.02, 1.05)
    ax.set_title("Shed destroys the hospital's trust harder during the disruption,\n"
                 "but it fully heals by ~period 250 — the customer returns",
                 fontweight='bold', fontsize=11.5)
    ax.legend(frameon=False, loc='lower right', fontsize=9.5)
    save(fig, 'fig5_trust_trajectory.pdf')


def fig_grid_heatmap():
    """System profit delta vs capacity, ONE LINE PER trust-sensitivity delta. Every delta line
    crosses zero at the same capacity (~180-240): capacity governs the flip boundary, delta does
    not move it. (Replaces the heatmap.)"""
    caps = [400, 240, 180, 140]
    colors = cm.viridis(np.linspace(0.12, 0.8, 4))
    fig, ax = plt.subplots(figsize=(6.8, 4.3))
    ax.axhspan(-1.4, 0, color='#f7e8e8', alpha=0.6, zorder=0)
    ax.axvspan(180, 240, color='0.88', alpha=0.6, zorder=0)
    ax.axhline(0, color='0.4', lw=1.2)
    for i, dlt in enumerate([0.10, 0.20, 0.35, 0.50]):
        ys = []
        for n in [40, 24, 18, 14]:
            cs = cell_metrics(P('grid2d', 'urgent0', 'shed', n, dlt))
            cb = cell_metrics(P('grid2d', 'urgent0', 'baseline', n, dlt))
            idx = cs.index.intersection(cb.index)
            ys.append((cs.loc[idx, 'sys_episode_profit'] - cb.loc[idx, 'sys_episode_profit']).mean() / 1e6)
        ax.plot(caps, ys, 'o-', color=colors[i], lw=2.3, ms=6, label=f'δ = {dlt:.2f}')
    ax.set_ylim(-1.35, 1.2)
    ax.set_xlim(150, 415)
    ax.set_xlabel('Healthy-manufacturer (MN2) capacity, units/period')
    ax.set_ylabel('System profit Δ (shed − baseline), \\$M')
    ax.text(157, -1.22, 'below ~180 every δ plunges to −3 to −6M (off scale)', fontsize=8, color='#7a2020')
    ax.set_title("Every trust-sensitivity δ flips the system at the SAME capacity (~180–240):\n"
                 "capacity governs the boundary — δ does not move it",
                 fontweight='bold', fontsize=10.5)
    ax.legend(frameon=False, fontsize=9, title='trust sensitivity', loc='lower right')
    save(fig, 'fig6_grid_heatmap.pdf')


def fig_trust_by_delta():
    """HC1's trust in DS1 over the episode, one line per trust sensitivity delta (shed policy).
    Shows the whole dynamic --- collapse depth, recovery speed, full return --- in one view;
    a clearer replacement for the noisy oscillation std + binary 'returns?' columns."""
    deltas = [0.05, 0.10, 0.20, 0.35, 0.50]
    colors = cm.viridis(np.linspace(0.12, 0.82, len(deltas)))
    fig, ax = plt.subplots(figsize=(6.9, 4.4))
    ax.axvspan(110, 157, color='0.9', alpha=0.7, zorder=0)
    ax.text(133, 0.06, 'disruption', ha='center', fontsize=8.5, color='0.4')
    for c, dlt in zip(colors, deltas):
        df = pd.read_csv(P('delta_sweep', 'urgent0', 'shed', 40, dlt))
        tr = df.groupby('period')['hc1_trust_ds1'].mean().loc[100:290]
        ax.plot(tr.index, tr.values, color=c, lw=2.1, label=f'δ = {dlt:.2f}')
    ax.set_xlabel('period')
    ax.set_ylabel("HC1's trust in DS1 (disrupted distributor)")
    ax.set_ylim(-0.03, 1.05)
    ax.set_xlim(100, 290)
    ax.set_title("Trust collapses during the disruption and fully recovers at every δ —\n"
                 "higher δ reacts faster (steeper fall, quicker rebound); the customer always returns",
                 fontweight='bold', fontsize=10.5)
    ax.legend(frameon=False, fontsize=9, title='trust sensitivity', loc='center right')
    save(fig, 'fig9_trust_by_delta.pdf')


def fig_chain_reaction():
    """Shed's recovery dynamics for DS1 (baseline vs shed): backlog and during-disruption
    ordering are lower, but the recovery inventory glut is LARGER --- shed reduces backlog by
    shedding the demand (HC1), which has not returned when supply recovers."""
    base = pd.read_csv(os.path.join(ROOT, 'routing_study', 'results', 'urgent0', 'a.csv'))
    shed = pd.read_csv(os.path.join(HERE, 'results', 'slack', 'urgent0', 'dsseat_alloc_shed_timed_rep.csv'))

    def tr(df, col):
        return df.groupby('period')[col].mean().loc[90:260]
    specs = [('ds1_backlog', 'DS1 backlog\n(unfilled orders)', 'shed lower during disruption', '#1f5a2a'),
             ('ds1_order', 'DS1 orders\nplaced to MN', 'shed orders somewhat less', '0.35'),
             ('ds1_inventory', 'DS1 inventory\non hand', 'but shed gluts MORE in recovery', '#7a2020')]
    fig, axes = plt.subplots(3, 1, figsize=(6.8, 6.6), sharex=True)
    for ax, (col, lab, note, ncol) in zip(axes, specs):
        ax.axvspan(110, 157, color='0.9', alpha=0.7, zorder=0)
        tb, ts = tr(base, col), tr(shed, col)
        ax.plot(tb.index, tb.values, color=C_BASE, lw=2.3, label='baseline (base stock)')
        ax.plot(ts.index, ts.values, color=C_SHED, lw=2.3, label='shed')
        ax.set_ylabel(lab, fontsize=9.5)
        ax.text(0.985, 0.9, note, transform=ax.transAxes, ha='right', va='top',
                fontsize=8.5, color=ncol, style='italic')
    axes[0].text(133, axes[0].get_ylim()[1] * 0.6, 'disruption', ha='center', fontsize=8, color='0.4')
    axes[0].set_title("Shed lowers DS1's backlog and during-disruption ordering — but its recovery\n"
                      "glut is LARGER: it sheds the demand that would have consumed the inventory",
                      fontweight='bold', fontsize=10)
    axes[0].legend(frameon=False, fontsize=9, loc='upper left')
    axes[2].set_xlabel('period')
    save(fig, 'fig8_chain_reaction.pdf')


def print_channel_table():
    print("\n=== DS1 channel decomposition (anchor cap=400, delta=0.1) for the body table ===")
    b = cell_metrics(P('cap_sweep', 'urgent0', 'baseline', 40, 0.1))
    s = cell_metrics(P('cap_sweep', 'urgent0', 'shed', 40, 0.1))
    for ph in ('during', 'recovery', 'steady'):
        bp = {c: b[f'ds1_{ph}_{c}'].mean() for c in ('profit', 'revenue', 'holding', 'backlog')}
        sp = {c: s[f'ds1_{ph}_{c}'].mean() for c in ('profit', 'revenue', 'holding', 'backlog')}
        print(f"  {ph:9} baseline: profit {bp['profit']:>+12,.0f}  rev {bp['revenue']:>9,.0f}  "
              f"hold {bp['holding']:>7,.0f}  backlog {bp['backlog']:>10,.0f}")
        print(f"  {'':9} shed    : profit {sp['profit']:>+12,.0f}  rev {sp['revenue']:>9,.0f}  "
              f"hold {sp['holding']:>7,.0f}  backlog {sp['backlog']:>10,.0f}")
    # episode channel split of the gain
    idx = b.index.intersection(s.index)
    d = s.loc[idx] - b.loc[idx]
    print(f"  EPISODE gain {d['ds1_episode_profit'].mean():>+,.0f} = "
          f"revenue {d['ds1_episode_revenue'].mean():>+,.0f} + "
          f"holding(avoided) {-d['ds1_episode_holding'].mean():>+,.0f} + "
          f"backlog(avoided) {-d['ds1_episode_backlog'].mean():>+,.0f}")


if __name__ == '__main__':
    fig_capacity_divergence()
    fig_channel_during()
    fig_externality()
    fig_delta()
    fig_trust_trajectory()
    fig_grid_heatmap()
    fig_fill_by_capacity()
    fig_trust_by_delta()
    fig_chain_reaction()
    print_channel_table()
