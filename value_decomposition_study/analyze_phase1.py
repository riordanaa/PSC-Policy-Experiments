"""Phase-1 analysis: H1 (glut fix), H2 (buffer null frontier), H3 (detect-reroute),
H4 (ceiling). Produces results/slack/phase1_summary.csv and prints the tables every
hypothesis card cites. Reference policy = the deployable compound baseline
(rung-c routing + static-priority allocation) from understanding_study.
"""
import glob
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import pandas as pd

from value_decomposition_study.metrics_vds import summarize, quick_table
from understanding_study.residual_decomposition import glut_metrics

COMPOUND = {
    'urgent0': os.path.join(ROOT, 'understanding_study', 'results', 'urgent0',
                            'alloc_prio_hc1.csv'),
    'urgent20': os.path.join(ROOT, 'understanding_study', 'results', 'urgent20',
                             'alloc_prio_hc1.csv'),
}
ORACLE_D = os.path.join(ROOT, 'routing_study', 'results', 'urgent0', 'd.csv')
SLACK = os.path.join(HERE, 'results', 'slack')


def paths_for(config, pattern):
    return sorted(glob.glob(os.path.join(SLACK, config, pattern)))


def main(config='urgent0'):
    policy_paths = {'compound_baseline': COMPOUND[config]}
    if config == 'urgent0' and os.path.exists(ORACLE_D):
        policy_paths['oracle_reroute_d(prop_alloc)'] = ORACLE_D
    for p in paths_for(config, '*.csv'):
        name = os.path.basename(p)[:-4]
        if '_tune_' in name:
            continue
        policy_paths[name] = p

    per_seed, summary = summarize(policy_paths, 'compound_baseline')
    out = os.path.join(SLACK, config)
    os.makedirs(out, exist_ok=True)
    per_seed.to_csv(os.path.join(out, 'phase1_per_seed.csv'), index=False)
    summary.to_csv(os.path.join(out, 'phase1_summary.csv'))

    print(f'\n===== PHASE 1 PANEL ({config}; reference = compound baseline) =====')
    print(quick_table(summary, config=config).round(1).to_string())

    # glut check for every policy (urgent0 only, where the H1 question lives)
    if config == 'urgent0':
        print('\n===== GLUT (system inventory; pre-mean ~332) =====')
        rows = {}
        for name, path in policy_paths.items():
            g = glut_metrics(pd.read_csv(path))
            rows[name] = {k: g[k] for k in
                          ('system_post_peak_inv', 'system_glut_peak_excess',
                           'system_glut_area', 'post_holding_cost')}
        print(pd.DataFrame(rows).T.round(0).sort_values('system_glut_peak_excess')
              .to_string())

    # tuning files use seeds 1-10; the compound reference has no overlap there, so
    # premium/coverage are undefined — report tuning dp-cost directly instead.
    tune = paths_for(config, '*_tune_*.csv')
    if tune:
        print('\n===== TUNING (seeds 1-10 only — parameter choice, not reported) =====')
        from value_decomposition_study.metrics_vds import panel_for_csv
        for p in tune:
            t = panel_for_csv(p)
            dp = (t['during_system_cost'] + t['post_system_cost']).mean()
            print(f'  {os.path.basename(p)[:-4]:40s} dp_cost={dp:,.0f}')


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', default='urgent0')
    args = ap.parse_args()
    main(args.config)
