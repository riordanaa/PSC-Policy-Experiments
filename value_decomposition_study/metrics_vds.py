"""Metric panel for the value-decomposition study.

Wraps routing_study.metrics.seed_phase_metrics and adds:
  - bullwhip: var(orders placed) / var(demand) per DS per phase (NEW panel metric)
  - premium / coverage axes vs a named reference policy:
      premium  = pre-phase system cost minus reference pre-phase system cost
      coverage = reference during+post system cost minus policy during+post system cost
Outputs a per-seed table and a mean +/- SE summary for a list of policy CSVs.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import numpy as np
import pandas as pd

from routing_study.metrics import seed_phase_metrics, PHASES


def bullwhip(df_seed):
    out = {}
    for phase, (lo, hi) in PHASES.items():
        d = df_seed[(df_seed['period'] >= lo) & (df_seed['period'] <= hi)]
        for ds in ('ds1', 'ds2'):
            dem_var = d[f'{ds}_demand'].var()
            out[f'{phase}_bullwhip_{ds}'] = (
                d[f'{ds}_order'].var() / dem_var if dem_var and dem_var > 0 else np.nan)
    return out


def dual_accounting(df_seed):
    """A1 amendment: system cost per phase EXCLUDING manufacturer backlog cost
    (the dead-factory queue is an accounting convention, not a physical loss)."""
    out = {}
    for phase, (lo, hi) in PHASES.items():
        d = df_seed[(df_seed['period'] >= lo) & (df_seed['period'] <= hi)]
        mn_backlog_cost = 10.0 * (d['mn1_backlog'].sum() + d['mn2_backlog'].sum())
        out[f'{phase}_mn_backlog_cost'] = mn_backlog_cost
    return out


def panel_for_csv(path):
    df = pd.read_csv(path)
    rows = []
    for seed, g in df.groupby('seed'):
        g = g.sort_values('period')
        m = seed_phase_metrics(g)
        m.update(bullwhip(g))
        m.update(dual_accounting(g))
        m['seed'] = seed
        rows.append(m)
    return pd.DataFrame(rows)


def summarize(policy_paths, reference_name):
    """policy_paths: {name: csv_path}. Returns (per_seed_df, summary_df) with premium/
    coverage computed per seed against the reference policy (paired)."""
    per = {}
    for name, path in policy_paths.items():
        p = panel_for_csv(path)
        p['policy'] = name
        per[name] = p.set_index('seed')
    ref = per[reference_name]
    frames = []
    for name, p in per.items():
        common = p.index.intersection(ref.index)
        p = p.loc[common].copy()
        r = ref.loc[common]
        p['premium'] = p['pre_system_cost'] - r['pre_system_cost']
        p['coverage'] = ((r['during_system_cost'] + r['post_system_cost'])
                         - (p['during_system_cost'] + p['post_system_cost']))
        p['dp_cost'] = p['during_system_cost'] + p['post_system_cost']
        frames.append(p.reset_index())
    per_seed = pd.concat(frames, ignore_index=True)
    metric_cols = [c for c in per_seed.columns if c not in ('policy', 'seed')]
    summary = per_seed.groupby('policy')[metric_cols].agg(['mean', 'sem'])
    summary.columns = [f'{a}_{b}' for a, b in summary.columns]
    return per_seed, summary


def quick_table(summary, extra_cols=(), config='urgent0'):
    cols = ['dp_cost_mean', 'dp_cost_sem', 'premium_mean', 'coverage_mean',
            'during_fill_agg_mean', 'peak_backlog_ds1_mean',
            'aub_ds1_during_post_mean', 'post_holding_cost_mean']
    if config == 'urgent20':
        cols += ['episode_lost_u_mean']
    cols += list(extra_cols)
    cols = [c for c in cols if c in summary.columns]
    return summary[cols].sort_values('dp_cost_mean')
