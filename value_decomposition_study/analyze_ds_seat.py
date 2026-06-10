"""Part B analysis: DS-seat ladder in the thesis (rung-a) world.

Headline: whole-episode cumulative PSC profit (sum of the six *_profit columns), the thesis
Table 3.9 metric, with share-of-base-stock-loss-removed for direct comparison to the thesis
claim (GRU-A2C removed ~89% of BS's long-disruption loss). Panel columns + dual accounting
alongside. Reference = routing_study rung a (base stock, thesis world, on disk).

Checked outputs:
  --check elevated   inventory trajectory vs window on elevated runs (does it climb? where?)
  --check shed       per-HC fill/backlog trajectories on shed runs (demand-dumping guard)
"""
import glob
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import pandas as pd

AGENTS = ['ds1', 'ds2', 'mn1', 'mn2', 'hc1', 'hc2']
REF = {c: os.path.join(ROOT, 'routing_study', 'results', c, 'a.csv')
       for c in ('urgent0', 'urgent20')}


def seed_rows(df):
    rows = []
    for seed, g in df.groupby('seed'):
        psc = sum(g[f'{a}_profit'].sum() for a in AGENTS)
        dp = g[g['period'] >= 110]
        dp_cost = sum(1.0 * dp[f'{a}_inventory'].sum()
                      + 10.0 * dp[f'{a}_backlog'].sum() for a in AGENTS)
        mnb = 10.0 * (dp['mn1_backlog'].sum() + dp['mn2_backlog'].sum())
        pre = g[(g['period'] >= 60) & (g['period'] <= 109)]
        pre_cost = sum(1.0 * pre[f'{a}_inventory'].sum()
                       + 10.0 * pre[f'{a}_backlog'].sum() for a in AGENTS)
        dur = g[(g['period'] >= 110) & (g['period'] <= 157)]
        dem = sum(dur[f'{h}_patient_u'].sum() + dur[f'{h}_patient_nu'].sum()
                  for h in ('hc1', 'hc2'))
        srv = sum(dur[f'{h}_treated_u'].sum() + dur[f'{h}_treated_nu'].sum()
                  for h in ('hc1', 'hc2'))
        f1 = (dur['hc1_treated_u'].sum() + dur['hc1_treated_nu'].sum()) / max(
            1, dur['hc1_patient_u'].sum() + dur['hc1_patient_nu'].sum())
        f2 = (dur['hc2_treated_u'].sum() + dur['hc2_treated_nu'].sum()) / max(
            1, dur['hc2_patient_u'].sum() + dur['hc2_patient_nu'].sum())
        lost = sum(g[g['period'] >= 60][f'{h}_lost_u'].sum() for h in ('hc1', 'hc2'))
        rows.append(dict(seed=seed, psc_profit=psc, dp_cost=dp_cost,
                         dp_cost_ex_mn=dp_cost - mnb, pre_cost=pre_cost,
                         during_fill=srv / max(1, dem), fill_hc1=f1, fill_hc2=f2,
                         lost_u=lost))
    return pd.DataFrame(rows)


def table(config='urgent0', pattern='dsseat_*'):
    d = os.path.join(HERE, 'results', 'slack', config)
    files = {os.path.basename(p)[:-4]: p
             for p in glob.glob(os.path.join(d, f'{pattern}.csv'))}
    files['BASE STOCK (rung-a)'] = REF[config]
    out = []
    bs_psc = None
    per = {}
    for name, p in sorted(files.items()):
        s = seed_rows(pd.read_csv(p))
        per[name] = s
        m = s.mean(numeric_only=True)
        m['psc_sem'] = s['psc_profit'].sem()
        m['policy'] = name
        out.append(m)
        if name.startswith('BASE STOCK'):
            bs_psc = m['psc_profit']
    t = pd.DataFrame(out).set_index('policy').drop(columns=['seed'])
    if bs_psc is not None and bs_psc < 0:
        t['share_of_BS_loss_removed'] = (t['psc_profit'] - bs_psc) / (-bs_psc)
    t = t.sort_values('psc_profit', ascending=False)
    return t, per


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', default='urgent0')
    ap.add_argument('--pattern', default='dsseat_*')
    args = ap.parse_args()
    pd.set_option('display.width', 250)
    t, _ = table(args.config, args.pattern)
    print(f'===== DS-SEAT LADDER, thesis world ({args.config}) — '
          f'headline: episode PSC profit =====')
    print(t.round(3).to_string())
