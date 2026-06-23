"""Analysis for the robustness sweeps (capacity x delta, shed vs baseline) + metric
definitions + rung-b 2-trust re-analysis. Reuses routing_study.metrics.seed_phase_metrics
for the system panel; adds DS1 profit-channel decomposition and HC1 trust/share/oscillation
(logic promoted from the tmp shed analysis scripts).

Run AFTER exp_robustness.py --mode sweep. Prints the meeting tables; writes a tidy CSV.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import numpy as np
import pandas as pd

from routing_study.metrics import seed_phase_metrics

AGENTS = ['ds1', 'ds2', 'mn1', 'mn2', 'hc1', 'hc2']
# DS1 channel phases (recovery/steady split the post window to expose the transient)
CH = {'during': (110, 157), 'recovery': (158, 250), 'steady': (251, 300), 'episode': (110, 300)}
TRUST_T = [109, 130, 157, 175, 200, 250, 299]


def ds1_channels(g):
    """DS1 revenue/holding/backlog/profit by phase. revenue = profit + holding + backlog."""
    out = {}
    for ph, (lo, hi) in CH.items():
        d = g[(g['period'] >= lo) & (g['period'] <= hi)]
        hold = 1.0 * d['ds1_inventory'].sum()
        bk = 10.0 * d['ds1_backlog'].sum()
        prof = d['ds1_profit'].sum()
        out[f'ds1_{ph}_profit'] = prof
        out[f'ds1_{ph}_revenue'] = prof + hold + bk
        out[f'ds1_{ph}_holding'] = hold
        out[f'ds1_{ph}_backlog'] = bk
        out[f'ds2_{ph}_profit'] = d['ds2_profit'].sum()
        out[f'sys_{ph}_profit'] = sum(d[f'{a}_profit'].sum() for a in AGENTS)
    return out


def hc1_dynamics(g):
    """HC1 order-share to DS1 by phase, trust trajectory, post-window oscillation std."""
    out = {}
    for ph, (lo, hi) in {'pre': (60, 109), 'during': (110, 157),
                         'post': (158, 300), 'late_post': (271, 300)}.items():
        d = g[(g['period'] >= lo) & (g['period'] <= hi)]
        den = d['hc1_order_to_ds1'].sum() + d['hc1_order_to_ds2'].sum()
        out[f'hc1_share_ds1_{ph}'] = d['hc1_order_to_ds1'].sum() / den if den > 0 else np.nan
    for t in TRUST_T:
        r = g[g['period'] == t]
        out[f'trust_ds1_t{t}'] = float(r['hc1_trust_ds1'].iloc[0]) if len(r) else np.nan
    post = g[(g['period'] >= 158) & (g['period'] <= 300)]
    den = post['hc1_order_to_ds1'] + post['hc1_order_to_ds2']
    share = post['hc1_order_to_ds1'] / den.replace(0, np.nan)
    out['hc1_share_osc_std'] = float(share.std())
    return out


def overshoot_glut(g):
    """Metric-definition piece: disruption-END = 157 + ttr_ds1 (NaN->censor 300); overshoot =
    DS1 inventory area over [END, END+20] above nominal (pre-disruption mean)."""
    pre = g[(g['period'] >= 60) & (g['period'] <= 109)]
    nominal = pre['ds1_inventory'].mean()
    m = seed_phase_metrics(g.sort_values('period'))
    ttr = m['ttr_ds1']
    end = 300 if (ttr is None or np.isnan(ttr)) else int(157 + ttr)
    win = g[(g['period'] >= end) & (g['period'] <= min(end + 20, 300))]
    overshoot = float((win['ds1_inventory'] - nominal).clip(lower=0).sum())
    return {'disruption_end': end, 'overshoot_glut': overshoot,
            'nominal_inv': nominal, 'aub_ds1_during_post': m['aub_ds1_during_post']}


def cell_metrics(path):
    """Per-seed metrics for one cell CSV: system panel + DS1 channels + HC1 dynamics."""
    df = pd.read_csv(path)
    rows = []
    for seed, g in df.groupby('seed'):
        g = g.sort_values('period')
        r = {'seed': seed}
        sp = seed_phase_metrics(g)
        for k in ('during_system_cost', 'post_system_cost', 'during_fill_agg',
                  'post_fill_agg', 'episode_fill_agg', 'pre_fill_agg',
                  'during_fill_hc1', 'during_fill_hc2', 'post_fill_hc1', 'post_fill_hc2',
                  'episode_fill_hc1', 'episode_fill_hc2',
                  'episode_lost_u', 'during_fill_dispersion', 'post_fill_dispersion',
                  'ttr_ds1', 'aub_ds1_during_post'):
            r[k] = sp[k]
        r.update(ds1_channels(g))
        r.update(hc1_dynamics(g))
        r.update(overshoot_glut(g))
        rows.append(r)
    return pd.DataFrame(rows).set_index('seed')


def paired(shed, base, cols):
    idx = shed.index.intersection(base.index)
    d = shed.loc[idx] - base.loc[idx]
    return {c: (d[c].mean(), d[c].sem()) for c in cols}


def P(sub, cfg, policy, n_lines, delta):
    return os.path.join(HERE, 'results', 'robustness', sub, cfg,
                        f'{policy}_lines{n_lines}_delta{int(round(delta*100)):03d}.csv')


def fmt(x, n=0):
    return f'{x:,.{n}f}' if x == x else 'nan'


# ---------------------------------------------------------------- capacity sweep

def capacity_table(cfg='urgent0'):
    print(f"\n{'='*100}\nCAPACITY SWEEP ({cfg}, delta=0.1, slack)  — MN2 lines x10 = units/period\n{'='*100}")
    none_b = cell_metrics(P('none', cfg, 'baseline', 40, 0.1))
    ceil = none_b['episode_fill_agg'].mean()
    print(f"no-disruption ceiling fill_agg = {ceil:.3f}\n")
    print("during-fill = fraction of EACH HC's during-window demand served WITHIN the window; "
          "episode-fill = whole-run (urgent0: ~1.0 = deferred not lost)")
    print(f"{'MN2 cap':>8}{'shed HC1/HC2 (dur)':>20}{'base HC1/HC2 (dur)':>20}"
          f"{'epi HC1/HC2':>14}{'DS1 d(shed-base)':>18}{'sys d':>12}{'HC1 ret':>9}")
    rows = []
    for n in [40, 24, 18, 14, 12]:
        bp, sp = P('cap_sweep', cfg, 'baseline', n, 0.1), P('cap_sweep', cfg, 'shed', n, 0.1)
        if not (os.path.exists(bp) and os.path.exists(sp)):
            print(f"{n*10:>8}  (missing)"); continue
        b, s = cell_metrics(bp), cell_metrics(sp)
        d = paired(s, b, ['ds1_episode_profit', 'ds1_episode_backlog', 'ds1_episode_revenue',
                          'sys_episode_profit'])
        s1, s2 = s['during_fill_hc1'].mean(), s['during_fill_hc2'].mean()
        b1, b2 = b['during_fill_hc1'].mean(), b['during_fill_hc2'].mean()
        e1, e2 = s['episode_fill_hc1'].mean(), s['episode_fill_hc2'].mean()
        ret = s['hc1_share_ds1_late_post'].mean()
        print(f"{n*10:>8}{s1:>9.3f}/{s2:.3f}{b1:>11.3f}/{b2:.3f}{e1:>8.3f}/{e2:.3f}"
              f"{d['ds1_episode_profit'][0]:>+18,.0f}{d['sys_episode_profit'][0]:>+12,.0f}{ret:>9.3f}")
        rows.append(dict(cfg=cfg, sweep='capacity', knob=n*10,
                         ds1_delta=d['ds1_episode_profit'][0],
                         sys_delta=d['sys_episode_profit'][0],
                         shed_fill_hc1=s1, shed_fill_hc2=s2,
                         base_fill_hc1=b1, base_fill_hc2=b2,
                         epi_fill_hc1=e1, epi_fill_hc2=e2,
                         hc1_return=ret, ceiling=ceil))
    return rows


# ---------------------------------------------------------------- delta sweep

def delta_table(cfg='urgent0'):
    print(f"\n{'='*100}\nDELTA SWEEP ({cfg}, MN2 cap=400, slack)\n{'='*100}")
    print(f"{'delta':>7}{'shed fill d/p':>16}{'DS1 d(shed-base)':>18}{'  via backlog':>14}"
          f"{'HC1 osc':>9}{'HC1 ret':>9}{'trust@175':>11}{'trust@250':>11}")
    rows = []
    for dlt in [0.05, 0.10, 0.20, 0.35, 0.50]:
        bp, sp = P('delta_sweep', cfg, 'baseline', 40, dlt), P('delta_sweep', cfg, 'shed', 40, dlt)
        if not (os.path.exists(bp) and os.path.exists(sp)):
            print(f"{dlt:>7}  (missing)"); continue
        b, s = cell_metrics(bp), cell_metrics(sp)
        d = paired(s, b, ['ds1_episode_profit', 'ds1_episode_backlog'])
        sf = (s['during_fill_agg'].mean(), s['post_fill_agg'].mean())
        osc = s['hc1_share_osc_std'].mean()
        ret = s['hc1_share_ds1_late_post'].mean()
        t175, t250 = s['trust_ds1_t175'].mean(), s['trust_ds1_t250'].mean()
        print(f"{dlt:>7}{sf[0]:>8.3f}/{sf[1]:.3f}{d['ds1_episode_profit'][0]:>+18,.0f}"
              f"{-d['ds1_episode_backlog'][0]:>+14,.0f}{osc:>9.3f}{ret:>9.3f}{t175:>11.3f}{t250:>11.3f}")
        rows.append(dict(cfg=cfg, sweep='delta', knob=dlt,
                         ds1_delta=d['ds1_episode_profit'][0],
                         shed_fill_during=sf[0], shed_fill_post=sf[1],
                         hc1_osc=osc, hc1_return=ret, trust175=t175, trust250=t250))
    return rows


# ---------------------------------------------------------------- metric definitions demo

def metric_defs(cfg='urgent0'):
    print(f"\n{'='*100}\nMETRIC DEFINITIONS (demo on anchor cap=400 delta=0.1, {cfg})\n{'='*100}")
    for pol in ('baseline', 'shed'):
        s = cell_metrics(P('cap_sweep', cfg, pol, 40, 0.1))
        ttr = s['ttr_ds1']
        nrec = int(ttr.isna().sum())
        print(f"  {pol:9}: disruption-END (=157+ttr) mean={s['disruption_end'].mean():.1f} "
              f"(ttr median={np.nanmedian(ttr):.0f}, {nrec}/20 not recovered) | "
              f"overshoot/glut(DS1 inv over nominal, [END,END+20])={s['overshoot_glut'].mean():,.0f} | "
              f"AUB(shortage side)={s['aub_ds1_during_post'].mean():,.0f}")
    print("  coverage: same-period fill rate (W=0) is reported throughout as fill_agg; exact "
          "within-W (e.g. 2-week) coverage needs an order place-time the CSV does not log — "
          "flagged as a logging gap, proxy = cumulative-served(t+W)/cumulative-demand(t).")


# ---------------------------------------------------------------- rung-b (2-trust)

def rungb_table(cfg='urgent0'):
    print(f"\n{'='*100}\nRUNG-B 2-TRUST re-analysis ({cfg}, existing data, no new runs)\n{'='*100}")
    a = cell_metrics(os.path.join(ROOT, 'routing_study', 'results', cfg, 'a.csv'))
    b = cell_metrics(os.path.join(ROOT, 'routing_study', 'results', cfg, 'b.csv'))
    for name, m in (('rung-a (1trust+1equal)', a), ('rung-b (2 trust)', b)):
        print(f"  {name:24}: DS1 episode profit {m['ds1_episode_profit'].mean():>+12,.0f} | "
              f"during fill_disp(HC1-HC2) {m['during_fill_dispersion'].mean():>+.3f} | "
              f"post fill_disp {m['post_fill_dispersion'].mean():>+.3f} | "
              f"HC1 osc {m['hc1_share_osc_std'].mean():.3f}")
    d = paired(b, a, ['ds1_episode_profit', 'ds1_during_backlog', 'during_fill_dispersion'])
    print(f"  delta (b - a): DS1 profit {d['ds1_episode_profit'][0]:>+,.0f}, "
          f"DS1 during backlog cost {d['ds1_during_backlog'][0]:>+,.0f}, "
          f"during fill-dispersion {d['during_fill_dispersion'][0]:>+.3f}")


def main():
    allrows = []
    allrows += capacity_table('urgent0')
    allrows += delta_table('urgent0')
    metric_defs('urgent0')
    rungb_table('urgent0')
    rungb_table('urgent20')
    out = os.path.join(HERE, 'results', 'robustness', 'summary_tidy.csv')
    pd.DataFrame(allrows).to_csv(out, index=False)
    print(f"\nwrote {out}")


if __name__ == '__main__':
    main()
