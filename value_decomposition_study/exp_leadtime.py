"""Lead-time x capacity sweep (Phase 1). Wraps exp_robustness.run_cell with a lead-time config
mutation (PHYSICAL_LEAD_TIME = AGENT_LEAD_TIME = lt), set before build_sim so the network
connectivity and the base-stock up-to-level both use it. At lt=2 this is a no-op and reproduces
the existing cap_sweep CSVs bit-exactly (the gate). No edits to exp_robustness.py / the runners.

  python value_decomposition_study/exp_leadtime.py --mode gate    # LT=2 reproduction gate
  python value_decomposition_study/exp_leadtime.py --mode sweep   # the lead-time x capacity grid
  python value_decomposition_study/exp_leadtime.py --mode all     # gate then sweep (default)
"""
import argparse
import copy
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'Test'))

import pandas as pd

import config
import value_decomposition_study.exp_robustness as er

LEAD_TIMES = [2, 3, 4, 6, 8]
CAP_LINES = [40, 24, 18, 14, 12]      # 400,240,180,140,120 /period
ANCHOR_LT = 2


def run_lt_cell(policy, cfg, n_lines, lt, regime='slack'):
    """Set lead time on config (read at build_sim), run one cell via exp_robustness, restore."""
    op, oa = config.PHYSICAL_LEAD_TIME, config.AGENT_LEAD_TIME
    config.PHYSICAL_LEAD_TIME = lt
    config.AGENT_LEAD_TIME = lt
    try:
        return er.run_cell(policy, cfg, er.ANCHOR_DELTA, n_lines, regime)
    finally:
        config.PHYSICAL_LEAD_TIME, config.AGENT_LEAD_TIME = op, oa


def _path(lt, regime, cfg, policy, n_lines):
    d = os.path.join(HERE, 'results', 'robustness', 'leadtime', f'lt{lt}', regime, cfg)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f'{policy}_lines{n_lines}.csv')


# ---------------------------------------------------------------- Phase 2: severity

SEVERITIES = [0.35, 0.50, 0.65, 0.80, 0.95]   # decrease_factor on MN1 (disrupted)


def run_sev_cell(policy, cfg, n_lines, severity, lt=2, regime='slack'):
    """Set MN1 disruption severity (decrease_factor_1) + lead time, run one cell, restore.
    set_regime (inside run_cell) preserves decrease_factor_1 from config.DISRUPTIONS[0]."""
    op, oa = config.PHYSICAL_LEAD_TIME, config.AGENT_LEAD_TIME
    od = copy.deepcopy(config.DISRUPTIONS)
    config.PHYSICAL_LEAD_TIME = lt
    config.AGENT_LEAD_TIME = lt
    config.DISRUPTIONS[0]['decrease_factor_1'] = severity
    try:
        return er.run_cell(policy, cfg, er.ANCHOR_DELTA, n_lines, regime)
    finally:
        config.PHYSICAL_LEAD_TIME, config.AGENT_LEAD_TIME = op, oa
        config.DISRUPTIONS = od


def _spath(sev, cfg, policy, n_lines):
    d = os.path.join(HERE, 'results', 'robustness', 'severity', f'sev{int(round(sev*100)):02d}', cfg)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f'{policy}_lines{n_lines}.csv')


def severity_sweep(force=False):
    cells = []
    for sev in SEVERITIES:
        for pol in ('baseline', 'shed'):
            for n in CAP_LINES:
                cells.append((sev, 'urgent0', pol, n))
            for n in (40, 18):      # urgent20 for the lost-patient component
                cells.append((sev, 'urgent20', pol, n))
    for sev, cfg, pol, n in cells:
        p = _spath(sev, cfg, pol, n)
        if os.path.exists(p) and not force:
            print(f'skip (exists): {p}'); continue
        df = run_sev_cell(pol, cfg, n, sev, lt=ANCHOR_LT, regime='slack')
        df.to_csv(p, index=False)
        print(f'wrote {p} ({len(df)} rows)', flush=True)


def severity_gate():
    print("=== SEVERITY GATE: sev=0.95, lt=2 reproduces cap_sweep ===")
    ok = True
    for cfg in ('urgent0', 'urgent20'):
        for pol in ('baseline', 'shed'):
            ref = pd.read_csv(er._path('cap_sweep', cfg, pol, 40, 0.1))
            new = run_sev_cell(pol, cfg, 40, 0.95, lt=ANCHOR_LT)
            ok &= er._numeric_equal(new, ref, f'{pol}/{cfg} sev95 vs cap_sweep')
    print(f"=== SEVERITY GATE {'PASSED' if ok else 'FAILED'} ===")
    return ok


def gate():
    print("=== LT=2 REPRODUCTION GATE (vs existing cap_sweep, delta=0.1) ===")
    ok = True
    for cfg in ('urgent0', 'urgent20'):
        for pol in ('baseline', 'shed'):
            ref = pd.read_csv(er._path('cap_sweep', cfg, pol, 40, 0.1))
            new = run_lt_cell(pol, cfg, 40, ANCHOR_LT, 'slack')
            ok &= er._numeric_equal(new, ref, f'{pol}/{cfg} lt2 vs cap_sweep')
    print(f"=== GATE {'PASSED' if ok else 'FAILED'} ===")
    return ok


def sweep(force=False):
    cells = []
    # slack urgent0: full lead x capacity grid, both policies
    for lt in LEAD_TIMES:
        for pol in ('baseline', 'shed'):
            for n in CAP_LINES:
                cells.append((lt, 'slack', 'urgent0', pol, n))
            # urgent20 at cap {400,180} for the lost-patient ("unfulfilled") component
            for n in (40, 18):
                cells.append((lt, 'slack', 'urgent20', pol, n))
    # no-disruption floor guard at the capacity floor for the longer lead times
    for lt in (4, 6, 8):
        cells.append((lt, 'none', 'urgent0', 'baseline', 12))
        cells.append((lt, 'none', 'urgent0', 'baseline', 40))
    seen = set()
    for lt, regime, cfg, pol, n in cells:
        p = _path(lt, regime, cfg, pol, n)
        if p in seen:
            continue
        seen.add(p)
        if os.path.exists(p) and not force:
            print(f'skip (exists): {p}'); continue
        df = run_lt_cell(pol, cfg, n, lt, regime)
        df.to_csv(p, index=False)
        print(f'wrote {p} ({len(df)} rows)', flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', default='all',
                    choices=['gate', 'sweep', 'all', 'sevgate', 'severity'])
    ap.add_argument('--force', action='store_true')
    args = ap.parse_args()
    if args.mode in ('gate', 'all'):
        if not gate() and args.mode == 'all':
            print('GATE FAILED — aborting sweep.')
            sys.exit(1)
    if args.mode in ('sweep', 'all'):
        sweep(args.force)
    if args.mode == 'sevgate':
        severity_gate()
    if args.mode == 'severity':
        if not severity_gate():
            print('SEVERITY GATE FAILED — aborting.')
            sys.exit(1)
        severity_sweep(args.force)


if __name__ == '__main__':
    main()
