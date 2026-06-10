"""Phase-2 analysis: H5 (routing under scarcity), H6 (the real frontier at the primary
cell), H7 (severity x duration lever-flip map).

All tables carry BOTH baselines (A3): fairness-neutral (rung-c ladder = proportional) and
fairness-costed (rung-c + static priority). Dual accounting (A1) reported alongside.
"""
import glob
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import pandas as pd

AGENTS = ['ds1', 'ds2', 'mn1', 'mn2', 'hc1', 'hc2']


def seed_stats(df, dis_end=157):
    """Per-seed dp-cost (full + ex-MN), pre cost, during fill, lost, peaks."""
    rows = []
    for seed, g in df.groupby('seed'):
        pre = g[(g['period'] >= 60) & (g['period'] <= 109)]
        dp = g[g['period'] >= 110]
        dur = g[(g['period'] >= 110) & (g['period'] <= dis_end)]
        cost = lambda d: sum(1.0 * d[f'{a}_inventory'].sum()
                             + 10.0 * d[f'{a}_backlog'].sum() for a in AGENTS)
        mnb = 10.0 * (dp['mn1_backlog'].sum() + dp['mn2_backlog'].sum())
        dem = sum(dur[f'{h}_patient_u'].sum() + dur[f'{h}_patient_nu'].sum()
                  for h in ('hc1', 'hc2'))
        srv = sum(dur[f'{h}_treated_u'].sum() + dur[f'{h}_treated_nu'].sum()
                  for h in ('hc1', 'hc2'))
        lost = sum(g[g['period'] >= 60][f'{h}_lost_u'].sum() for h in ('hc1', 'hc2'))
        rows.append(dict(seed=seed, pre_cost=cost(pre), dp_cost=cost(dp),
                         dp_cost_ex_mn=cost(dp) - mnb,
                         during_fill=srv / max(1, dem), lost_u=lost,
                         peak_ds1=dp['ds1_backlog'].max(),
                         peak_ds2=dp['ds2_backlog'].max()))
    return pd.DataFrame(rows)


def table(files, dis_end=157):
    """files: {label: path}. Returns mean table sorted by dp_cost."""
    rows = []
    for label, path in files.items():
        if not os.path.exists(path):
            continue
        s = seed_stats(pd.read_csv(path), dis_end)
        m = s.mean(numeric_only=True)
        m['dp_sem'] = s['dp_cost'].sem()
        m['n_seeds'] = s['seed'].nunique()
        m['policy'] = label
        rows.append(m)
    t = pd.DataFrame(rows).set_index('policy').sort_values('dp_cost')
    return t.drop(columns=['seed'])


def cell_dir(regime, duration, config):
    rd = regime if duration == 48 else f'{regime}_d{duration}'
    return os.path.join(HERE, 'results', rd, config)


def h5_ladder(config='urgent0'):
    d = cell_dir('sat50', 48, config)
    files = {f'ladder_{r}': os.path.join(d, f'ladder_{r}.csv') for r in 'abcd'}
    print(f'\n===== H5: routing ladder under scarcity (sat50,d48,{config}) =====')
    print(table(files).round(1).to_string())


def h6_screen(config='urgent0'):
    d = cell_dir('sat50', 48, config)
    files = {os.path.basename(p)[:-4]: p
             for p in glob.glob(os.path.join(d, '*_tune*.csv'))}
    files['ladder_c (neutral baseline)'] = os.path.join(d, 'ladder_c.csv')
    print(f'\n===== H6 SCREEN (sat50,d48,{config}; tuning rows are seeds 1-10) =====')
    print(table(files).round(1).to_string())


def h6_frontier(config='urgent0'):
    d = cell_dir('sat50', 48, config)
    files = {os.path.basename(p)[:-4]: p
             for p in glob.glob(os.path.join(d, '*.csv'))
             if '_tune' not in p and 'ladder_' not in os.path.basename(p)}
    files['neutral baseline (ladder c)'] = os.path.join(d, 'ladder_c.csv')
    print(f'\n===== H6 FRONTIER (sat50,d48,{config}; reporting seeds) =====')
    print(table(files).round(1).to_string())


def h7_map(config='urgent0'):
    print(f'\n===== H7 severity x duration map ({config}) =====')
    for regime in ('sat70', 'sat50', 'sat30'):
        for dur in (5, 17, 48):
            d = cell_dir(regime, dur, config)
            if not os.path.isdir(d):
                continue
            files = {os.path.basename(p)[:-4]: p
                     for p in glob.glob(os.path.join(d, '*.csv'))}
            if not files:
                continue
            dis_end = 109 + dur
            t = table(files, dis_end)
            print(f'\n--- {regime}, duration {dur} ---')
            print(t[['dp_cost', 'dp_cost_ex_mn', 'pre_cost', 'during_fill',
                     'lost_u']].round(1).to_string())


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--what', default='h5,h6screen')
    ap.add_argument('--config', default='urgent0')
    args = ap.parse_args()
    for w in args.what.split(','):
        {'h5': h5_ladder, 'h6screen': h6_screen,
         'h6frontier': h6_frontier, 'h7': h7_map}[w](args.config)
