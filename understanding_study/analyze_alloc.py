"""E1 analysis: the allocation bound.

Scores every allocation variant with the routing study's phase-stratified panel
(routing_study.metrics.seed_phase_metrics) and reports the max-over-family spread —
the value of the entire allocation channel on the routing-fixed baseline.
Proportional (= rung c) is read from routing_study/results.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import pandas as pd

from routing_study.metrics import seed_phase_metrics

RULES = ['proportional', 'equal', 'prio_hc1', 'prio_hc2',
         'backlog_priority', 'serve_captive']


def load(config, rule):
    if rule == 'proportional':
        path = os.path.join(ROOT, 'routing_study', 'results', config, 'c.csv')
    else:
        path = os.path.join(HERE, 'results', config, f'alloc_{rule}.csv')
    return pd.read_csv(path)


def main(config):
    rows = []
    for rule in RULES:
        df = load(config, rule)
        for seed, g in df.groupby('seed'):
            m = seed_phase_metrics(g.sort_values('period'))
            m.update(rule=rule, seed=seed)
            rows.append(m)
    per_seed = pd.DataFrame(rows)
    metric_cols = [c for c in per_seed.columns if c not in ('rule', 'seed')]
    summary = per_seed.groupby('rule')[metric_cols].agg(['mean', 'sem'])
    summary.columns = [f'{a}_{b}' for a, b in summary.columns]
    out = os.path.join(HERE, 'results', config)
    os.makedirs(out, exist_ok=True)
    per_seed.to_csv(os.path.join(out, 'alloc_per_seed.csv'), index=False)
    summary.to_csv(os.path.join(out, 'alloc_summary.csv'))

    s = summary
    key = ['during_system_cost_mean', 'post_system_cost_mean',
           'during_fill_agg_mean', 'during_fill_hc1_mean', 'during_fill_hc2_mean',
           'during_fill_dispersion_mean', 'aub_ds1_during_post_mean']
    if config == 'urgent20':
        key += ['during_lost_u_mean', 'post_lost_u_mean', 'episode_lost_u_mean']
    print(f'\n=== allocation family, {config}, reporting seeds (means) ===')
    view = s[key].copy()
    view['dp_cost'] = view['during_system_cost_mean'] + view['post_system_cost_mean']
    print(view.round(3).to_string())

    dp = view['dp_cost']
    base = dp.loc['proportional']
    print(f'\nBOUND: during+post system cost — best {dp.min():,.0f} ({dp.idxmin()}), '
          f'worst {dp.max():,.0f} ({dp.idxmax()})')
    print(f'  spread (worst-best)          = {dp.max() - dp.min():,.0f} '
          f'({100 * (dp.max() - dp.min()) / base:.1f}% of proportional baseline)')
    print(f'  best improvement vs propor.  = {base - dp.min():,.0f} '
          f'({100 * (base - dp.min()) / base:.1f}%)')
    if config == 'urgent20':
        lost = s['episode_lost_u_mean']
        print(f'  lost patients: best {lost.min():,.0f} ({lost.idxmin()}), '
              f'worst {lost.max():,.0f} ({lost.idxmax()}), '
              f'proportional {lost.loc["proportional"]:,.0f}')


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', default='urgent0')
    args = ap.parse_args()
    main(args.config)
