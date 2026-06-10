"""Verification gates for the routing study. All must pass before any reported number.

Gate 1: rung (a), constant demand, seed 42 EXACTLY reproduces the reference base-stock
        trajectory (r5_test_results_basestock_ds1_disrupted/basestock_ds1_log.csv).
        This simultaneously proves FlexibleHCDecisionMaker(default) == SimpleHCDecisionMaker,
        because the reference run used the original class.
Gate 2: determinism — same (rung, config, seed) twice gives identical trajectories.
Gate 3: rung (b) actually shifts HC_equal's split away from DS_disrupted during disruption.
Gate 4: rung (c) write-off reduces the counted on-order below raw on-order during/after
        disruption at HC_equal.
Gate 5: conservation, every period, both HCs:
        non-urgent: patient_nu(t) + backlog(t-1) = treated_nu(t) + backlog(t)
        urgent:     patient_u(t) - treated_u(t) = lost_u(recorded at t+1)
"""
import os
import sys
import argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'Test'))
os.chdir(ROOT)

import pandas as pd

from routing_study import run_ladder

REF_CSV = os.path.join(ROOT, 'r5_test_results_basestock_ds1_disrupted',
                       'basestock_ds1_log.csv')


def default_args(**over):
    ns = argparse.Namespace(delta=0.3, sharp_p=2.0, writeoff_k=3.0, onset_share=0.1)
    for k, v in over.items():
        setattr(ns, k, v)
    return ns


def gate1():
    ref = pd.read_csv(REF_CSV)
    ref42 = ref[ref['seed'] == 42].sort_values('period').reset_index(drop=True)
    # the reference script logged row k under period=k (0-based); run_one logs true
    # simulator time (1-based). Shift the reference to align like-for-like.
    ref42 = ref42.assign(period=ref42['period'] + 1)
    df = run_ladder.run_one('a', 'const', 42, default_args())
    merged = ref42[['period', 'ds1_backlog', 'ds1_inventory', 'ds1_on_order']].merge(
        df[['period', 'ds1_backlog', 'ds1_inventory', 'ds1_on_order']],
        on='period', suffixes=('_ref', '_new'))
    diffs = {c: (merged[f'{c}_ref'] - merged[f'{c}_new']).abs().max()
             for c in ('ds1_backlog', 'ds1_inventory', 'ds1_on_order')}
    ok = all(v == 0 for v in diffs.values())
    print(f'GATE 1 (exact baseline reproduction, const demand, seed 42): '
          f'{"PASS" if ok else "FAIL"}  max|diff|={diffs}')
    return ok


def gate2():
    a = run_ladder.run_one('b', 'urgent0', 11, default_args())
    b = run_ladder.run_one('b', 'urgent0', 11, default_args())
    same = a.equals(b)
    print(f'GATE 2 (determinism, rung b, urgent0, seed 11 twice): '
          f'{"PASS" if same else "FAIL"}')
    return same


def gate3():
    a = run_ladder.run_one('a', 'urgent0', 11, default_args())
    b = run_ladder.run_one('b', 'urgent0', 11, default_args())

    def hc2_share_to_ds1(df):
        d = df[(df['period'] >= 110) & (df['period'] <= 157)]
        tot = d['hc2_order_to_ds1'].sum() + d['hc2_order_to_ds2'].sum()
        return d['hc2_order_to_ds1'].sum() / max(1, tot)

    sa, sb = hc2_share_to_ds1(a), hc2_share_to_ds1(b)
    ok = sb < sa - 0.02
    print(f'GATE 3 (rung b shifts HC_equal split): share-to-DS_disrupted during '
          f'disruption a={sa:.3f} -> b={sb:.3f}  {"PASS" if ok else "FAIL"}')
    return ok


def gate4():
    c = run_ladder.run_one('c', 'urgent0', 11, default_args())
    d = c[c['period'] >= 110]
    gap = (d['hc2_on_order_raw'] - d['hc2_on_order_counted']).max()
    ok = gap > 0
    print(f'GATE 4 (rung c write-off active): max raw-counted on-order gap at HC_equal '
          f'from period 110 = {gap:.0f}  {"PASS" if ok else "FAIL"}')
    return ok


def gate5():
    ok_all = True
    for rung in ('a', 'c'):
        for cfg in ('urgent0', 'urgent20'):
            df = run_ladder.run_one(rung, cfg, 12, default_args()).sort_values('period')
            for hc in ('hc1', 'hc2'):
                nu_viol = u_viol = 0
                prev_bl = 0.0
                lost_next = df[f'{hc}_lost_u'].shift(-1)
                for i, r in df.iterrows():
                    t = r['period']
                    if t >= 1:
                        lhs = r[f'{hc}_patient_nu'] + prev_bl
                        rhs = r[f'{hc}_treated_nu'] + r[f'{hc}_backlog']
                        if abs(lhs - rhs) > 1.5:   # round() in treat decision => <=1 ok
                            nu_viol += 1
                        unmet_u = r[f'{hc}_patient_u'] - r[f'{hc}_treated_u']
                        ln = lost_next.loc[i]
                        if pd.notna(ln) and abs(unmet_u - ln) > 1.5:
                            u_viol += 1
                    prev_bl = r[f'{hc}_backlog']
                ok = (nu_viol == 0 and u_viol == 0)
                ok_all &= ok
                print(f'GATE 5 (conservation) rung {rung} {cfg} {hc}: '
                      f'nu_violations={nu_viol} u_violations={u_viol} '
                      f'{"PASS" if ok else "FAIL"}')
    return ok_all


def gate6():
    """Cross-seed variance must be nonzero under the normal demand model.
    (Catches NormalDistPatientModel's np.random.seed(0) constructor reset,
    patient_model.py:28 — see routing_study_design.md section 7.)"""
    a = run_ladder.run_one('a', 'urgent0', 11, default_args())
    b = run_ladder.run_one('a', 'urgent0', 12, default_args())
    diff = (a['hc1_patient_nu'] - b['hc1_patient_nu']).abs().sum()
    ok = diff > 0
    print(f'GATE 6 (cross-seed demand variation, seeds 11 vs 12): '
          f'sum|demand diff|={diff:.0f}  {"PASS" if ok else "FAIL"}')
    return ok


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--gates', default='1,2,3,4,5,6')
    args = ap.parse_args()
    gates = {'1': gate1, '2': gate2, '3': gate3, '4': gate4, '5': gate5, '6': gate6}
    results = {}
    for g in args.gates.split(','):
        results[g] = gates[g]()
    print('\nSUMMARY:', {k: ('PASS' if v else 'FAIL') for k, v in results.items()})
    sys.exit(0 if all(results.values()) else 1)
