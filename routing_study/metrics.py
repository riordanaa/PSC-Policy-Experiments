"""Phase-stratified, system-level metric panel for the routing ladder.

Reads results/{config}/{rung}.csv (from run_ladder.py), writes
results/{config}/summary.csv (per rung x phase panel, mean +/- SE over seeds) and
results/{config}/paired_vs_a.csv (per-seed paired differences vs rung a).

Scoring rules (pre-registered):
- SYSTEM-LEVEL cost: holding 1/unit x inventory + backlog 10/unit x backlog, summed over
  all six agents. Never a DS_disrupted-only ledger.
- Phases in true simulator time (1-based): warmup 1-59 (excluded from headline numbers),
  pre 60-109, during 110-157, post 158-300, plus whole-episode 60-300.
- Lost patients = urgent component of 'patient_lost' only (non-urgent unmet is backlogged,
  not lost; see routing_study_design.md section 4).
- Time-to-recovery: first period t >= 158 from which DS_disrupted backlog stays at or below
  110% of its own pre-disruption mean for 5 consecutive periods; 'did not recover' reported
  as NaN and counted.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import numpy as np
import pandas as pd

HOLD, BACK = 1.0, 10.0
AGENTS = ['ds1', 'ds2', 'mn1', 'mn2', 'hc1', 'hc2']
PHASES = {'pre': (60, 109), 'during': (110, 157), 'post': (158, 300),
          'episode': (60, 300)}


def seed_phase_metrics(df_seed):
    """All panel metrics for ONE seed of ONE rung. Returns {metric: value}."""
    out = {}
    pre_lo, pre_hi = PHASES['pre']
    pre = df_seed[(df_seed['period'] >= pre_lo) & (df_seed['period'] <= pre_hi)]

    for phase, (lo, hi) in PHASES.items():
        d = df_seed[(df_seed['period'] >= lo) & (df_seed['period'] <= hi)]
        hold_cost = sum(HOLD * d[f'{a}_inventory'].sum() for a in AGENTS)
        back_cost = sum(BACK * d[f'{a}_backlog'].sum() for a in AGENTS)
        out[f'{phase}_holding_cost'] = hold_cost
        out[f'{phase}_backlog_cost'] = back_cost
        out[f'{phase}_system_cost'] = hold_cost + back_cost
        out[f'{phase}_profit_psc'] = sum(d[f'{a}_profit'].sum() for a in AGENTS)

        for hc in ('hc1', 'hc2'):
            dem = d[f'{hc}_patient_u'].sum() + d[f'{hc}_patient_nu'].sum()
            served = d[f'{hc}_treated_u'].sum() + d[f'{hc}_treated_nu'].sum()
            out[f'{phase}_fill_{hc}'] = served / max(1, dem)
        dem = sum(d[f'{hc}_patient_u'].sum() + d[f'{hc}_patient_nu'].sum()
                  for hc in ('hc1', 'hc2'))
        served = sum(d[f'{hc}_treated_u'].sum() + d[f'{hc}_treated_nu'].sum()
                     for hc in ('hc1', 'hc2'))
        out[f'{phase}_fill_agg'] = served / max(1, dem)
        out[f'{phase}_fill_dispersion'] = (out[f'{phase}_fill_hc1']
                                           - out[f'{phase}_fill_hc2'])
        out[f'{phase}_lost_u'] = sum(d[f'{hc}_lost_u'].sum() for hc in ('hc1', 'hc2'))

    # peaks (whole episode after warmup)
    d = df_seed[df_seed['period'] >= 60]
    out['peak_backlog_ds1'] = d['ds1_backlog'].max()
    out['peak_backlog_ds2'] = d['ds2_backlog'].max()
    out['peak_backlog_system'] = (d['ds1_backlog'] + d['ds2_backlog']
                                  + d['mn1_backlog'] + d['mn2_backlog']
                                  + d['hc1_backlog'] + d['hc2_backlog']).max()

    # area under DS_disrupted backlog, during+post
    dp = df_seed[df_seed['period'] >= 110]
    out['aub_ds1_during_post'] = dp['ds1_backlog'].sum()

    # time-to-recovery for DS_disrupted
    thresh = 1.10 * max(1.0, pre['ds1_backlog'].mean())
    post = df_seed[df_seed['period'] >= 158].sort_values('period')
    bl = post['ds1_backlog'].values
    per = post['period'].values
    ttr = np.nan
    for i in range(len(bl) - 4):
        if (bl[i:i + 5] <= thresh).all():
            ttr = per[i] - 157
            break
    out['ttr_ds1'] = ttr
    return out


def summarize(config_dir, rungs):
    per_seed_rows = []
    for rung in rungs:
        path = os.path.join(config_dir, f'{rung}.csv')
        df = pd.read_csv(path)
        for seed, g in df.groupby('seed'):
            m = seed_phase_metrics(g.sort_values('period'))
            m.update(rung=rung, seed=seed)
            per_seed_rows.append(m)
    per_seed = pd.DataFrame(per_seed_rows)

    metric_cols = [c for c in per_seed.columns if c not in ('rung', 'seed')]

    # summary: mean +/- SE per rung
    summary = per_seed.groupby('rung')[metric_cols].agg(['mean', 'sem'])
    summary.columns = [f'{m}_{s}' for m, s in summary.columns]
    summary['n_did_not_recover'] = per_seed.groupby('rung')['ttr_ds1'] \
        .apply(lambda s: int(s.isna().sum()))
    summary = summary.reset_index()

    # paired differences vs rung a (same seed)
    base = per_seed[per_seed['rung'] == rungs[0]].set_index('seed')[metric_cols]
    paired_rows = []
    for rung in rungs[1:]:
        cur = per_seed[per_seed['rung'] == rung].set_index('seed')[metric_cols]
        common = cur.index.intersection(base.index)
        diff = cur.loc[common] - base.loc[common]
        row = {'rung': rung}
        for c in metric_cols:
            row[f'd_{c}_mean'] = diff[c].mean()
            row[f'd_{c}_sem'] = diff[c].sem()
        paired_rows.append(row)
    paired = pd.DataFrame(paired_rows)

    per_seed.to_csv(os.path.join(config_dir, 'per_seed_metrics.csv'), index=False)
    summary.to_csv(os.path.join(config_dir, 'summary.csv'), index=False)
    paired.to_csv(os.path.join(config_dir, 'paired_vs_a.csv'), index=False)
    return per_seed, summary, paired


def headline(config_dir):
    """Fraction of baseline during+post system cost recovered by each rung."""
    summary = pd.read_csv(os.path.join(config_dir, 'summary.csv'))
    s = summary.set_index('rung')
    base_dp = (s.loc['a', 'during_system_cost_mean']
               + s.loc['a', 'post_system_cost_mean'])
    lines = []
    for rung in s.index:
        dp = s.loc[rung, 'during_system_cost_mean'] + s.loc[rung, 'post_system_cost_mean']
        lines.append(f"rung {rung}: during+post system cost {dp:,.0f} "
                     f"({100 * (base_dp - dp) / base_dp:+.1f}% vs baseline)")
    return '\n'.join(lines)


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', default='urgent0')
    ap.add_argument('--rungs', default='a,b,c,d')
    args = ap.parse_args()
    cdir = os.path.join(HERE, 'results', args.config)
    per_seed, summary, paired = summarize(cdir, args.rungs.split(','))
    print(headline(cdir))
