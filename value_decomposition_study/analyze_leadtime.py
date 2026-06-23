"""Analysis for the lead-time x capacity sweep (Phase 1). Per-phase cost breakdown at DS1 and
system (holding / backlog / unfulfilled), the capacity-flip threshold, and the recovery glut as
functions of lead time. Reuses routing_study.metrics.seed_phase_metrics. Writes figures + tidy CSV
and prints the meeting tables. Run AFTER exp_leadtime.py --mode sweep."""
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

from routing_study.metrics import seed_phase_metrics, AGENTS

LEAD_TIMES = [2, 3, 4, 6, 8]
CAPS = [40, 24, 18, 14, 12]                  # line counts; capacity = x10
FIG = os.path.join(HERE, 'report', 'figures')
os.makedirs(FIG, exist_ok=True)
plt.rcParams.update({'font.size': 11, 'axes.spines.top': False, 'axes.spines.right': False,
                     'figure.autolayout': True})


def LP(lt, regime, cfg, pol, n):
    return os.path.join(HERE, 'results', 'robustness', 'leadtime', f'lt{lt}', regime, cfg,
                        f'{pol}_lines{n}.csv')


def metrics(path):
    """Per-seed: DS1 + system holding/backlog (during/post), episode profits, glut, lost_u, fill."""
    df = pd.read_csv(path)
    rows = []
    for s, g in df.groupby('seed'):
        g = g.sort_values('period')
        sp = seed_phase_metrics(g)
        r = dict(seed=s, ttr=sp['ttr_ds1'], aub=sp['aub_ds1_during_post'],
                 episode_lost_u=sp['episode_lost_u'], during_fill=sp['during_fill_agg'],
                 post_fill=sp['post_fill_agg'])
        for ph in ('during', 'post'):
            r[f'sys_{ph}_holding'] = sp[f'{ph}_holding_cost']
            r[f'sys_{ph}_backlog'] = sp[f'{ph}_backlog_cost']
        for ph, (lo, hi) in (('during', (110, 157)), ('post', (158, 300))):
            d = g[(g['period'] >= lo) & (g['period'] <= hi)]
            r[f'ds1_{ph}_holding'] = 1.0 * d['ds1_inventory'].sum()
            r[f'ds1_{ph}_backlog'] = 10.0 * d['ds1_backlog'].sum()
        ep = g[(g['period'] >= 110) & (g['period'] <= 300)]
        r['ds1_episode_profit'] = ep['ds1_profit'].sum()
        r['sys_episode_profit'] = sum(ep[f'{a}_profit'].sum() for a in AGENTS)
        pre = g[(g['period'] >= 60) & (g['period'] <= 109)]
        nom = pre['ds1_inventory'].mean()
        ttr = sp['ttr_ds1']
        end = 300 if (ttr is None or np.isnan(ttr)) else int(157 + ttr)
        win = g[(g['period'] >= end) & (g['period'] <= min(end + 20, 300))]
        r['overshoot'] = float((win['ds1_inventory'] - nom).clip(lower=0).sum())
        rows.append(r)
    return pd.DataFrame(rows).set_index('seed')


def cell(lt, cfg, pol, n, regime='slack'):
    return metrics(LP(lt, regime, cfg, pol, n))


def pdelta(shed, base, col):
    idx = shed.index.intersection(base.index)
    return (shed.loc[idx, col] - base.loc[idx, col]).mean()


def flip_capacity(lt, cfg='urgent0'):
    """Linear-interp capacity (units/period) where system profit delta (shed-base) crosses 0."""
    caps_u, sysd = [], []
    for n in CAPS:
        b, s = cell(lt, cfg, 'baseline', n), cell(lt, cfg, 'shed', n)
        caps_u.append(n * 10)
        sysd.append(pdelta(s, b, 'sys_episode_profit') / 1e6)
    # caps_u descending; find first sign change from + to -
    for i in range(len(caps_u) - 1):
        if sysd[i] > 0 >= sysd[i + 1]:
            x0, x1, y0, y1 = caps_u[i], caps_u[i + 1], sysd[i], sysd[i + 1]
            return x1 + (x0 - x1) * (0 - y1) / (y0 - y1), list(zip(caps_u, sysd))
    return (np.nan, list(zip(caps_u, sysd)))


# ---------------------------------------------------------------- tables

def table_flip():
    print("\n" + "=" * 96)
    print("CAPACITY-FLIP THRESHOLD vs LEAD TIME (urgent0): system profit Delta (shed-base), $M, by cap")
    print("=" * 96)
    print(f"{'lead time':>10}" + "".join(f"{c*10:>9}" for c in CAPS) + f"{'flip cap':>11}")
    rows = []
    for lt in LEAD_TIMES:
        flip, pts = flip_capacity(lt)
        print(f"{lt:>10}" + "".join(f"{v:>9.2f}" for _, v in pts) + f"{flip:>11.0f}")
        rows.append(dict(lt=lt, flip_cap=flip, **{f'sysd_{c*10}': v for (c, (_, v)) in zip(CAPS, pts)}))
    return rows


def table_cost_vs_lt(n=40, cfg='urgent0'):
    print("\n" + "=" * 96)
    print(f"COST & GLUT vs LEAD TIME at MN2 cap {n*10} ({cfg}), shed policy "
          "(during backlog/holding, recovery glut)")
    print("=" * 96)
    print(f"{'lead time':>10}{'DS1 dur backlog':>17}{'sys dur backlog':>17}{'DS1 dur holding':>17}"
          f"{'DS1 glut(overshoot)':>21}{'recov time':>12}")
    rows = []
    for lt in LEAD_TIMES:
        s = cell(lt, cfg, 'shed', n)
        m = s.mean()
        print(f"{lt:>10}{m['ds1_during_backlog']:>17,.0f}{m['sys_during_backlog']:>17,.0f}"
              f"{m['ds1_during_holding']:>17,.0f}{m['overshoot']:>21,.0f}{np.nanmean(s['ttr']):>12.0f}")
        rows.append(dict(lt=lt, cap=n * 10, ds1_during_backlog=m['ds1_during_backlog'],
                         sys_during_backlog=m['sys_during_backlog'], ds1_during_holding=m['ds1_during_holding'],
                         glut=m['overshoot'], ttr=np.nanmean(s['ttr'])))
    return rows


def table_lost_vs_lt():
    print("\n" + "=" * 96)
    print("UNFULFILLED (lost urgent patients) vs LEAD TIME (urgent20), at cap 400 and 180")
    print("=" * 96)
    print(f"{'lead time':>10}{'cap400 base':>14}{'cap400 shed':>14}{'cap180 base':>14}{'cap180 shed':>14}")
    rows = []
    for lt in LEAD_TIMES:
        vals = {}
        for n in (40, 18):
            for pol in ('baseline', 'shed'):
                vals[(n, pol)] = cell(lt, 'urgent20', pol, n)['episode_lost_u'].mean()
        print(f"{lt:>10}{vals[(40,'baseline')]:>14,.0f}{vals[(40,'shed')]:>14,.0f}"
              f"{vals[(18,'baseline')]:>14,.0f}{vals[(18,'shed')]:>14,.0f}")
        rows.append(dict(lt=lt, cap400_base=vals[(40, 'baseline')], cap400_shed=vals[(40, 'shed')],
                         cap180_base=vals[(18, 'baseline')], cap180_shed=vals[(18, 'shed')]))
    return rows


def floor_guard():
    print("\nFLOOR GUARD (no-disruption fill at cap 120 and 400, longer lead times):")
    for lt in (4, 6, 8):
        for n in (12, 40):
            p = LP(lt, 'none', 'urgent0', 'baseline', n)
            if os.path.exists(p):
                m = cell(lt, 'urgent0', 'baseline', n, 'none')
                print(f"  lt{lt} cap{n*10}: during_fill={m['during_fill'].mean():.4f}  "
                      f"post_fill={m['post_fill'].mean():.4f}")


# ---------------------------------------------------------------- figures

def fig_flip_vs_lt():
    fig, ax = plt.subplots(figsize=(6.8, 4.3))
    colors = cm.viridis(np.linspace(0.1, 0.82, len(LEAD_TIMES)))
    ax.axhspan(-1.4, 0, color='#f7e8e8', alpha=0.5, zorder=0)
    ax.axhline(0, color='0.4', lw=1.2)
    for c, lt in zip(colors, LEAD_TIMES):
        _, pts = flip_capacity(lt)
        caps_u = [x for x, _ in pts]
        ys = [y for _, y in pts]
        ax.plot(caps_u, ys, 'o-', color=c, lw=2.2, ms=6, label=f'LT = {lt}')
    ax.set_ylim(-1.4, 1.3)
    ax.set_xlim(150, 410)
    ax.set_xlabel('Healthy-manufacturer (MN2) capacity, units/period')
    ax.set_ylabel('System profit Δ (shed − baseline), \\$M')
    ax.text(157, -1.28, 'below the flip every LT plunges to several −$M (off scale)', fontsize=8, color='#7a2020')
    ax.set_title("Does the capacity flip move with lead time?\n"
                 "(each line crosses zero at its flip capacity)", fontweight='bold', fontsize=11)
    ax.legend(frameon=False, fontsize=9, title='lead time', loc='lower right')
    fig.savefig(os.path.join(FIG, 'lt_fig1_flip_vs_leadtime.pdf'), bbox_inches='tight')
    plt.close(fig)


def fig_cost_vs_lt(n=40):
    rows = [cell(lt, 'urgent0', 'shed', n).mean() for lt in LEAD_TIMES]
    ds1_bk = [r['ds1_during_backlog'] / 1e3 for r in rows]
    glut = [r['overshoot'] for r in rows]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.2, 3.9))
    ax1.plot(LEAD_TIMES, ds1_bk, 'o-', color=cm.viridis(0.3), lw=2.4, ms=7)
    ax1.set_xlabel('lead time (periods)'); ax1.set_ylabel('DS1 during-disruption backlog cost (\\$k)')
    ax1.set_title('During-disruption backlog vs lead time', fontweight='bold', fontsize=10.5)
    ax2.plot(LEAD_TIMES, glut, 's-', color=cm.viridis(0.65), lw=2.4, ms=7)
    ax2.set_xlabel('lead time (periods)'); ax2.set_ylabel('DS1 recovery glut (overshoot, units)')
    ax2.set_title('Recovery glut vs lead time', fontweight='bold', fontsize=10.5)
    fig.suptitle(f'Ergun\'s prediction: do backlog & glut grow nonlinearly with lead time? (MN2={n*10})',
                 fontweight='bold', fontsize=10.5)
    fig.savefig(os.path.join(FIG, 'lt_fig2_cost_vs_leadtime.pdf'), bbox_inches='tight')
    plt.close(fig)


def fig_lost_vs_lt():
    fig, ax = plt.subplots(figsize=(6.8, 4.2))
    for pol, mk, col in [('baseline', 'o', cm.viridis(0.22)), ('shed', 's', cm.viridis(0.66))]:
        ys = [cell(lt, 'urgent20', pol, 40)['episode_lost_u'].mean() for lt in LEAD_TIMES]
        ax.plot(LEAD_TIMES, ys, mk + '-', color=col, lw=2.4, ms=7, label=pol)
    ax.axvspan(4, 6, color='0.92', alpha=0.8, zorder=0)
    ax.set_xlabel('lead time (periods)')
    ax.set_ylabel('lost urgent patients (whole episode, MN2 = 400)')
    ax.set_title("Lost patients jump ~2.5× past lead time ~5 — the nonlinear\n"
                 "welfare cost Ergun predicted, on PATIENTS (not backlog/cost)",
                 fontweight='bold', fontsize=10.5)
    ax.legend(frameon=False, fontsize=9)
    fig.savefig(os.path.join(FIG, 'lt_fig2b_lost_vs_leadtime.pdf'), bbox_inches='tight')
    plt.close(fig)


# ---------------------------------------------------------------- Phase 2: severity (LT=2)

SEV = [35, 50, 65, 80, 95]                    # decrease_factor as int percent


def SP(sev, cfg, pol, n):
    return os.path.join(HERE, 'results', 'robustness', 'severity', f'sev{sev:02d}', cfg,
                        f'{pol}_lines{n}.csv')


def scell(sev, cfg, pol, n):
    return metrics(SP(sev, cfg, pol, n))


def flip_capacity_sev(sev, cfg='urgent0'):
    caps_u, sysd = [], []
    for n in CAPS:
        b, s = scell(sev, cfg, 'baseline', n), scell(sev, cfg, 'shed', n)
        caps_u.append(n * 10)
        sysd.append(pdelta(s, b, 'sys_episode_profit') / 1e6)
    for i in range(len(caps_u) - 1):
        if sysd[i] > 0 >= sysd[i + 1]:
            x0, x1, y0, y1 = caps_u[i], caps_u[i + 1], sysd[i], sysd[i + 1]
            return x1 + (x0 - x1) * (0 - y1) / (y0 - y1), list(zip(caps_u, sysd))
    return (np.nan, list(zip(caps_u, sysd)))


def table_sev_flip():
    print("\n" + "=" * 96)
    print("CAPACITY-FLIP vs DISRUPTION SEVERITY (LT=2, urgent0): system Delta (shed-base), $M, by cap")
    print("=" * 96)
    print(f"{'severity':>10}" + "".join(f"{c*10:>9}" for c in CAPS) + f"{'flip cap':>11}")
    rows = []
    for sev in SEV:
        flip, pts = flip_capacity_sev(sev)
        print(f"{f'{sev}%':>10}" + "".join(f"{v:>9.2f}" for _, v in pts) + f"{flip:>11.0f}")
        rows.append(dict(severity=sev, flip_cap=flip, **{f'sysd_{c*10}': v for (c, (_, v)) in zip(CAPS, pts)}))
    return rows


def table_sev_cost(n=40):
    print("\n" + "=" * 96)
    print(f"COST / SHED-BENEFIT / LOST vs SEVERITY at MN2 cap {n*10} (LT=2)")
    print("=" * 96)
    print(f"{'severity':>10}{'base sys backlog':>18}{'DS1 d(shed-base) $M':>21}{'sys d(shed-base) $M':>21}"
          f"{'lost u20 base':>15}{'lost u20 shed':>15}")
    rows = []
    for sev in SEV:
        b0, s0 = scell(sev, 'urgent0', 'baseline', n), scell(sev, 'urgent0', 'shed', n)
        try:
            b2, s2 = scell(sev, 'urgent20', 'baseline', n), scell(sev, 'urgent20', 'shed', n)
            lb, ls = b2['episode_lost_u'].mean(), s2['episode_lost_u'].mean()
        except FileNotFoundError:
            lb = ls = float('nan')
        d1 = pdelta(s0, b0, 'ds1_episode_profit') / 1e6
        ds = pdelta(s0, b0, 'sys_episode_profit') / 1e6
        sysbk = (b0['sys_during_backlog'].mean()) / 1e3
        print(f"{f'{sev}%':>10}{sysbk:>16,.0f}k{d1:>+21.3f}{ds:>+21.3f}{lb:>15,.0f}{ls:>15,.0f}")
        rows.append(dict(severity=sev, base_sys_backlog=sysbk * 1e3, ds1_delta=d1, sys_delta=ds,
                         lost_base=lb, lost_shed=ls))
    return rows


def fig_sev_flip():
    fig, ax = plt.subplots(figsize=(6.8, 4.3))
    colors = cm.plasma(np.linspace(0.1, 0.85, len(SEV)))
    ax.axhspan(-1.4, 0, color='#f7e8e8', alpha=0.5, zorder=0)
    ax.axhline(0, color='0.4', lw=1.2)
    for c, sev in zip(colors, SEV):
        _, pts = flip_capacity_sev(sev)
        ax.plot([x for x, _ in pts], [y for _, y in pts], 'o-', color=c, lw=2.2, ms=6, label=f'{sev}% cut')
    ax.set_ylim(-1.4, 1.3); ax.set_xlim(150, 410)
    ax.set_xlabel('Healthy-manufacturer (MN2) capacity, units/period')
    ax.set_ylabel('System profit Δ (shed − baseline), \\$M')
    ax.set_title("Does the capacity flip move with disruption severity? (LT=2)\n"
                 "milder disruptions → smaller shed effect, flip shifts", fontweight='bold', fontsize=11)
    ax.legend(frameon=False, fontsize=9, title='MN1 severity', loc='lower right')
    fig.savefig(os.path.join(FIG, 'lt_fig3_flip_vs_severity.pdf'), bbox_inches='tight')
    plt.close(fig)


def severity_main():
    allrows = {}
    allrows['sevflip'] = table_sev_flip()
    allrows['sevcost'] = table_sev_cost(40)
    fig_sev_flip()
    print('\nwrote figure: lt_fig3_flip_vs_severity.pdf')
    for k, rows in allrows.items():
        pd.DataFrame(rows).to_csv(os.path.join(HERE, 'results', 'robustness', 'severity',
                                               f'summary_{k}.csv'), index=False)


def main():
    allrows = {}
    allrows['flip'] = table_flip()
    allrows['cost400'] = table_cost_vs_lt(40)
    allrows['cost180'] = table_cost_vs_lt(18)
    allrows['lost'] = table_lost_vs_lt()
    floor_guard()
    fig_flip_vs_lt()
    fig_cost_vs_lt(40)
    fig_lost_vs_lt()
    print('\nwrote figures: lt_fig1, lt_fig2, lt_fig2b')
    for k, rows in allrows.items():
        pd.DataFrame(rows).to_csv(os.path.join(HERE, 'results', 'robustness', 'leadtime',
                                               f'summary_{k}.csv'), index=False)


if __name__ == '__main__':
    main()
