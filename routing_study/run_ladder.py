"""Routing-ladder runner: all-rule-based simulations with varied HC routing rules.

Rungs (HC_trust = hc_1 always 'bytrust'; the rung changes HC_equal = hc_2 and extras):
  a: baseline                hc_2 'equally'                       (repo config as-is)
  b: trust-split             hc_2 'bytrust'
  c: b + sharper reroute     hc_2 'bytrust', delta', trust**p, stale write-off k
  d: b + onset reroute       oracle step-split toward DS_healthy during the disruption

Demand configs (never pooled):
  const    : ConstantPatientModel urgent=0, non-urgent=120  (verification only — zero noise)
  urgent0  : Normal non-urgent N(120,5), urgent 0           (PRIMARY)
  urgent20 : Normal non-urgent N(120,5), urgent 20          (SECONDARY)

Usage:
  python routing_study/run_ladder.py --rungs a,b,c,d --config urgent0 --seeds 11-30
  python routing_study/run_ladder.py --rungs c --config urgent0 --seeds 1-10 \
      --delta 0.5 --sharp-p 4 --writeoff-k 3 --tag tune_d05_p4_k3

Output: results/{config}/{rung}{tag}.csv — one row per (seed, period) with per-agent columns.
"""
import argparse
import os
import sys
import warnings

warnings.filterwarnings('ignore')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'Test'))
os.chdir(ROOT)

import pandas as pd

import config
import simulator.simulation_runner as sim_runner
import simulator.decision_maker as dmaker
from drl_simulation_profile_config import ConfigDrivenProfile
from routing_study.policies import FlexibleHCDecisionMaker, LoggingSimpleDS

DIS_START, DIS_END = 110, 157
PERIODS = 300

DEMAND_CONFIGS = {
    'const':    dict(PATIENT_MODEL_TYPE='constant', PATIENT_URGENT=0,
                     PATIENT_NON_URGENT=120),
    'urgent0':  dict(PATIENT_MODEL_TYPE='normal',
                     PATIENT_NORMAL_URGENT_MEAN=0, PATIENT_NORMAL_URGENT_STDEV=0,
                     PATIENT_NORMAL_NON_URGENT_MEAN=120, PATIENT_NORMAL_NON_URGENT_STDEV=5),
    'urgent20': dict(PATIENT_MODEL_TYPE='normal',
                     PATIENT_NORMAL_URGENT_MEAN=20, PATIENT_NORMAL_URGENT_STDEV=0,
                     PATIENT_NORMAL_NON_URGENT_MEAN=120, PATIENT_NORMAL_NON_URGENT_STDEV=5),
}


def rung_params(rung, args):
    """HC decision-maker parameters per rung. hc index 0 = HC_trust, 1 = HC_equal."""
    base = {
        'a': [dict(split_recipe='bytrust'), dict(split_recipe='equally')],
        'b': [dict(split_recipe='bytrust'), dict(split_recipe='bytrust')],
        'c': [dict(split_recipe='bytrust', sharp_p=args.sharp_p, writeoff_k=args.writeoff_k),
              dict(split_recipe='bytrust', sharp_p=args.sharp_p, writeoff_k=args.writeoff_k)],
        'd': [dict(split_recipe='bytrust',
                   onset_window=(DIS_START, DIS_END), onset_disrupted_ds=None,
                   onset_disrupted_share=args.onset_share),
              dict(split_recipe='bytrust',
                   onset_window=(DIS_START, DIS_END), onset_disrupted_ds=None,
                   onset_disrupted_share=args.onset_share)],
    }
    return base[rung]


def apply_demand_config(name):
    for k, v in DEMAND_CONFIGS[name].items():
        setattr(config, k, v)


def build_sim(hc_params, delta_override=None):
    profile = ConfigDrivenProfile()
    dm = dmaker.PerAgentDecisionMaker()
    hc_dms = []
    # agent names are global-id based (e.g. distributors are 'ds_2','ds_3' in 2x2x2);
    # resolve the disrupted DS name dynamically instead of hardcoding it
    disrupted_ds_name = profile.distributors[0].name()
    for i, hc in enumerate(profile.health_centers):
        hc_dm = FlexibleHCDecisionMaker(hc, **hc_params[i])
        if hc_dm.onset_window is not None and hc_dm.onset_disrupted_ds is None:
            hc_dm.onset_disrupted_ds = disrupted_ds_name
        dm.add_decision_maker(hc_dm)
        hc_dms.append(hc_dm)
        if delta_override is not None:
            hc.delta = delta_override   # config.HC_TRUST_DELTA is dead; agent.py:581 hard-codes 0.1
    for mn in profile.manufacturers:
        dm.add_decision_maker(dmaker.SimpleMNDecisionMaker(mn))
    ds_dms = []
    for ds in profile.distributors:
        ds_dm = LoggingSimpleDS(ds)
        dm.add_decision_maker(ds_dm)
        ds_dms.append(ds_dm)
    runner = sim_runner.SimulationRunner(
        profile.simulation, dm, profile.agent_builder,
        profile.parameterize_sim_agents, profile.add_patient_model,
        profile.add_disruptions)
    return profile.simulation, runner, hc_dms, ds_dms


def profit_of(agent, period):
    for row in agent.collect_data(period):
        if row[2] == 'profit':
            return float(row[3])
    return 0.0


def hist(agent, period, key, default=None):
    item = agent.get_history_item(period)
    return item.get(key, default)


def run_one(rung, demand_config, seed, args):
    """Run one (rung, config, seed) episode; return a per-period DataFrame."""
    apply_demand_config(demand_config)
    config.set_global_seeds(seed)
    sim, runner, hc_dms, ds_dms = build_sim(
        rung_params(rung, args),
        delta_override=(args.delta if rung == 'c' else None))
    # CRITICAL: NormalDistPatientModel.__init__ hard-resets the global RNG with
    # np.random.seed(0) (simulator/patient_model.py:28), defeating set_global_seeds and
    # making every "seed" produce the identical demand path. Re-seed AFTER construction
    # so seeds genuinely vary. (Documented as a finding in routing_study_design.md.)
    config.set_global_seeds(seed)
    runner._update_patient(0)
    runner._update_agents(0)

    ds1, ds2 = sim.distributors[0], sim.distributors[1]
    mn1, mn2 = sim.manufacturers[0], sim.manufacturers[1]
    hc1, hc2 = sim.health_centers[0], sim.health_centers[1]
    ds_names = [d.name() for d in sim.distributors]

    rows = []
    for _ in range(PERIODS):
        runner.next_cycle(False)
        # next_cycle increments now FIRST (simulation_runner.py:43), so the cycle just
        # processed t = sim.now; all history reads must use t (true simulator time, 1-based)
        t = sim.now
        row = {'rung': rung, 'config': demand_config, 'seed': seed, 'period': t}

        for label, ds, dm in (('ds1', ds1, ds_dms[0]), ('ds2', ds2, ds_dms[1])):
            row[f'{label}_backlog'] = ds.backlog_level()
            row[f'{label}_inventory'] = ds.inventory_level()
            row[f'{label}_on_order'] = ds.on_order_level()
            row[f'{label}_demand'] = ds.demand(t)
            row[f'{label}_order'] = dm.last_order_amount
            row[f'{label}_up_to'] = float(ds.up_to_level)
            row[f'{label}_profit'] = profit_of(ds, t)

        for label, mn in (('mn1', mn1), ('mn2', mn2)):
            row[f'{label}_inventory'] = mn.inventory_level()
            row[f'{label}_backlog'] = mn.backlog_level()
            row[f'{label}_profit'] = profit_of(mn, t)

        for label, hc, dm in (('hc1', hc1, hc_dms[0]), ('hc2', hc2, hc_dms[1])):
            row[f'{label}_inventory'] = hc.inventory_level()
            row[f'{label}_backlog'] = hc.backlog_non_urgent
            patient = hist(hc, t, 'patient', (0, 0))
            lost = hist(hc, t, 'patient_lost', (0, 0))
            row[f'{label}_patient_u'] = patient[0]
            row[f'{label}_patient_nu'] = patient[1]
            row[f'{label}_lost_u'] = lost[0]          # unmet urgent from period t-1
            row[f'{label}_treated_u'] = hc.satisfied_urgent
            row[f'{label}_treated_nu'] = hc.satisfied_non_urgent
            row[f'{label}_profit'] = profit_of(hc, t)
            row[f'{label}_on_order_raw'] = dm.last_raw_on_order
            row[f'{label}_on_order_counted'] = dm.last_counted_on_order
            row[f'{label}_order_total'] = dm.last_order_amount
            for j, dname in enumerate(ds_names, start=1):
                row[f'{label}_order_to_ds{j}'] = dm.last_split.get(dname, 0)
                row[f'{label}_trust_ds{j}'] = hc.trust.get(dname, 1.0)
                row[f'{label}_on_order_ds{j}'] = sum(
                    o.amount for o in hc.on_order if o.dst == dname)
                row[f'{label}_deliv_from_ds{j}'] = sum(
                    d['item'].amount for d in hist(hc, t, 'delivery', [])
                    if d['src'] == dname)
        rows.append(row)
    return pd.DataFrame(rows)


def parse_seeds(spec):
    out = []
    for part in spec.split(','):
        if '-' in part:
            lo, hi = part.split('-')
            out.extend(range(int(lo), int(hi) + 1))
        else:
            out.append(int(part))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rungs', default='a')
    ap.add_argument('--config', default='urgent0', choices=list(DEMAND_CONFIGS))
    ap.add_argument('--seeds', default='11-30')
    ap.add_argument('--delta', type=float, default=0.3)
    ap.add_argument('--sharp-p', type=float, default=2.0)
    ap.add_argument('--writeoff-k', type=float, default=3.0)
    ap.add_argument('--onset-share', type=float, default=0.1)
    ap.add_argument('--tag', default='')
    ap.add_argument('--out', default=None)
    args = ap.parse_args()

    seeds = parse_seeds(args.seeds)
    out_dir = args.out or os.path.join(HERE, 'results', args.config)
    os.makedirs(out_dir, exist_ok=True)

    for rung in args.rungs.split(','):
        frames = []
        for seed in seeds:
            frames.append(run_one(rung, args.config, seed, args))
            print(f'rung {rung} config {args.config} seed {seed}: done', flush=True)
        df = pd.concat(frames, ignore_index=True)
        path = os.path.join(out_dir, f'{rung}{args.tag}.csv')
        df.to_csv(path, index=False)
        print(f'wrote {path} ({len(df)} rows)', flush=True)


if __name__ == '__main__':
    main()
