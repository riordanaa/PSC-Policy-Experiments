"""Verification gates for the value-decomposition study. All must pass (and be reported)
before any number from this study is used.

G1  regression: plain rung-c policy through the new runner == routing_study c.csv (seed 11)
G2  ShapedDS with all knobs off == AllocFlexibleDS (vs understanding_study alloc_prio_hc1)
G3  determinism: a knobbed policy run twice is identical
G4  conservation: per-period demand accounting holds for knobbed policies
G5  (per regime) cross-seed demand variance > 0 (RNG-reseed fix present)
G6  (saturated regimes only) saturation sanity: during-fill < 0.995 under rung-c routing
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'Test'))
os.chdir(ROOT)

import pandas as pd

from value_decomposition_study import run_vds

TOL = 1e-9


def _args(**over):
    ns = argparse.Namespace(
        alloc_rule='prio_hc1', buffer_b=0, buffer_loc='disrupted', jit_lead=10,
        taper_thresh=0.5, taper_m=1.0, throttle_c=1.2, ss_freeze=0,
        theta_down=0.5, w_down=3, theta_up=0.6, w_up=3)
    for k, v in over.items():
        setattr(ns, k, v)
    return ns


def _compare(ref, new, label):
    num_cols = [c for c in ref.columns
                if c not in ('rung', 'config') and pd.api.types.is_numeric_dtype(ref[c])]
    bad = [(c, (ref[c] - new[c]).abs().max()) for c in num_cols
           if (ref[c] - new[c]).abs().max() > TOL]
    ok = not bad
    print(f'{label}: {"PASS" if ok else "FAIL " + str(bad[:6])}')
    return ok


def g1():
    ref = pd.read_csv(os.path.join(ROOT, 'routing_study', 'results', 'urgent0', 'c.csv'))
    ref = ref[ref['seed'] == 11].sort_values('period').reset_index(drop=True)
    a = _args(alloc_rule='proportional')
    new = run_vds.run_policy('c_plain', 'urgent0', [11], a).sort_values(
        'period').reset_index(drop=True)
    return _compare(ref, new, 'G1 (rung-c regression via new runner)')


def g2():
    ref = pd.read_csv(os.path.join(ROOT, 'understanding_study', 'results', 'urgent0',
                                   'alloc_prio_hc1.csv'))
    ref = ref[ref['seed'] == 11].sort_values('period').reset_index(drop=True)
    new = run_vds.run_policy('shaped_defaults_gate', 'urgent0', [11], _args()) \
        .sort_values('period').reset_index(drop=True)
    return _compare(ref, new, 'G2 (ShapedDS defaults == AllocFlexibleDS)')


def g3():
    a = _args()
    r1 = run_vds.run_policy('h1_recovery_writeoff', 'urgent0', [12], a)
    r2 = run_vds.run_policy('h1_recovery_writeoff', 'urgent0', [12], a)
    ok = r1.equals(r2)
    print(f'G3 (determinism, h1 twice): {"PASS" if ok else "FAIL"}')
    return ok


def conservation(df, label):
    ok_all = True
    for hc in ('hc1', 'hc2'):
        viol = 0
        for seed, g in df.groupby('seed'):
            g = g.sort_values('period')
            prev_bl = 0.0
            for _, r in g.iterrows():
                if r['period'] >= 1:
                    lhs = r[f'{hc}_patient_nu'] + prev_bl
                    rhs = r[f'{hc}_treated_nu'] + r[f'{hc}_backlog']
                    if abs(lhs - rhs) > 1.5:
                        viol += 1
                prev_bl = r[f'{hc}_backlog']
        ok = viol == 0
        ok_all &= ok
        print(f'G4 (conservation) {label} {hc}: violations={viol} '
              f'{"PASS" if ok else "FAIL"}')
    return ok_all


def g4():
    a = _args(theta_down=0.5)
    ok = True
    for pol in ('h1_recovery_writeoff', 'h3_detect_reroute'):
        df = run_vds.run_policy(pol, 'urgent20', [13], a)
        ok &= conservation(df, pol)
    return ok


def g5(regime):
    a = _args()
    d1 = run_vds.run_policy('c_plain', 'urgent0', [11], a, regime=regime)
    d2 = run_vds.run_policy('c_plain', 'urgent0', [12], a, regime=regime)
    diff = (d1['hc1_patient_nu'] - d2['hc1_patient_nu']).abs().sum()
    ok = diff > 0
    print(f'G5 (cross-seed variance, {regime}): sum|diff|={diff:.0f} '
          f'{"PASS" if ok else "FAIL"}')
    return ok


def g6(regime):
    a = _args(alloc_rule='proportional')
    df = run_vds.run_policy('c_plain', 'urgent0', [11], a, regime=regime)
    d = df[(df['period'] >= 110) & (df['period'] <= 157)]
    dem = sum(d[f'{h}_patient_u'].sum() + d[f'{h}_patient_nu'].sum()
              for h in ('hc1', 'hc2'))
    served = sum(d[f'{h}_treated_u'].sum() + d[f'{h}_treated_nu'].sum()
                 for h in ('hc1', 'hc2'))
    fill = served / max(1, dem)
    ok = fill < 0.995
    print(f'G6 (saturation sanity, {regime}): during-fill={fill:.3f} '
          f'{"PASS (scarce)" if ok else "FAIL (not saturated)"}')
    return ok


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--gates', default='1,2,3,4,5')
    ap.add_argument('--regime', default='slack')
    args = ap.parse_args()
    fns = {'1': g1, '2': g2, '3': g3, '4': g4,
           '5': lambda: g5(args.regime), '6': lambda: g6(args.regime)}
    results = {g: fns[g]() for g in args.gates.split(',')}
    print('\nSUMMARY:', {k: ('PASS' if v else 'FAIL') for k, v in results.items()})
    sys.exit(0 if all(results.values()) else 1)
