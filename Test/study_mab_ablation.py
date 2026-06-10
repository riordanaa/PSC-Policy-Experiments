"""
Study 3: Fixed vs adaptive (MAB) reward ablation.

Compares the full UCB-P 8-arm bandit reward weighting against a single
fixed equal-weight arm to evaluate adaptive reward weighting.

Usage:
  python study_mab_ablation.py --fast
  python study_mab_ablation.py --episodes 80 --periods 300
  python study_mab_ablation.py --episodes 80 --seeds 42,123,256
"""
from __future__ import print_function

import argparse
import json
import os
import sys
import time
import warnings

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
warnings.filterwarnings('ignore')

import numpy as np
import tensorflow as tf

import config
import simulator.simulation_runner as sim_runner
import simulator.decision_maker as dmaker
from drl_simulation_profile_config import ConfigDrivenProfile
from drl_evaluation import compute_agent_metrics, summarize_period_range, print_comparison

ORIGINAL_ARMS = None

MAB_CONFIGS = {
    'adaptive_8arm': None,
    'fixed_equal': [[1.0, 1.0, 1.0, 1.0, 1.0, 1.0]],
    'fixed_backlog_heavy': [[1.0, 1.0, 1.0, 2.0, 1.0, 1.0]],
}


def _apply_mab_config(name):
    global ORIGINAL_ARMS
    if ORIGINAL_ARMS is None:
        ORIGINAL_ARMS = list(config.MAB_REWARD_ARMS)
    if MAB_CONFIGS[name] is None:
        config.MAB_REWARD_ARMS = list(ORIGINAL_ARMS)
    else:
        config.MAB_REWARD_ARMS = [list(a) for a in MAB_CONFIGS[name]]


def _run_drl(episodes, periods, mab_name, seed):
    _apply_mab_config(mab_name)
    config.set_global_seeds(seed)
    tf.keras.backend.clear_session()

    profile = ConfigDrivenProfile(f'study3_{mab_name}')
    for d in profile.simulation.disruptions:
        d.happen_day_1 = config.DISRUPTIONS[0]['happen_day_1']
        d.end_day_1 = config.DISRUPTIONS[0]['end_day_1']

    dm = dmaker.PerAgentDecisionMaker()
    hc_dms, mn_dms = [], []
    for i, hc in enumerate(profile.health_centers):
        recipe = config.HC_ORDER_SPLIT[i] if i < len(config.HC_ORDER_SPLIT) else 'equally'
        hc_dm = dmaker.SimpleHCDecisionMaker(hc, recipe)
        dm.add_decision_maker(hc_dm)
        hc_dms.append(hc_dm)
    for mn in profile.manufacturers:
        mn_dm = dmaker.SimpleMNDecisionMaker(mn)
        dm.add_decision_maker(mn_dm)
        mn_dms.append(mn_dm)

    drl_dms = []
    for i, ds in enumerate(profile.distributors):
        ds_dm = dmaker.DRLDSDecisionMaker(
            ds, mn_dms, hc_dms, periods, f'DS {i+1}', episodes)
        dm.add_decision_maker(ds_dm)
        drl_dms.append(ds_dm)

    n_arms = len(drl_dms[0].ds_env.bandit.arms) if drl_dms else 0
    print(f'    [{mab_name}] MAB arms={n_arms}')

    runner = sim_runner.SimulationRunner(
        profile.simulation, dm, profile.agent_builder,
        profile.parameterize_sim_agents, profile.add_patient_model,
        profile.add_disruptions)
    runner._update_patient(0)
    runner._update_agents(0)

    all_episodes = {}
    learning_curve = []
    do_reset = False

    for eps in range(episodes):
        t0 = time.time()
        for d in drl_dms:
            d.ds_env.reset()
            d.episode = eps
        ep_data = []
        for pr in range(periods):
            runner.next_cycle(do_reset)
            do_reset = False
            if pr > 0:
                ep_data.append(compute_agent_metrics(
                    profile.simulation, profile.simulation.now))
        do_reset = True
        all_episodes[eps] = ep_data

        ds_bklg = np.mean([
            sum(d[a]['bklg'] for a in d if a.startswith('ds_'))
            for d in ep_data]) if ep_data else 0
        ds_profit = np.mean([
            sum(d[a]['profit'] for a in d) for d in ep_data]) if ep_data else 0
        elapsed = time.time() - t0
        learning_curve.append({
            'episode': eps, 'ds_bklg': float(ds_bklg),
            'profit': float(ds_profit), 'time_s': elapsed,
        })
        print(f'    [{mab_name}] Ep {eps:3d}/{episodes}: '
              f'bklg={ds_bklg:7.1f}  profit={ds_profit:9.1f}  ({elapsed:.1f}s)')

    return all_episodes, learning_curve


def _run_baseline(periods, seed):
    config.set_global_seeds(seed)
    profile = ConfigDrivenProfile('baseline')
    for d in profile.simulation.disruptions:
        d.happen_day_1 = config.DISRUPTIONS[0]['happen_day_1']
        d.end_day_1 = config.DISRUPTIONS[0]['end_day_1']
    dm = dmaker.PerAgentDecisionMaker()
    for i, hc in enumerate(profile.health_centers):
        recipe = config.HC_ORDER_SPLIT[i] if i < len(config.HC_ORDER_SPLIT) else 'equally'
        dm.add_decision_maker(dmaker.SimpleHCDecisionMaker(hc, recipe))
    for mn in profile.manufacturers:
        dm.add_decision_maker(dmaker.SimpleMNDecisionMaker(mn))
    for ds in profile.distributors:
        dm.add_decision_maker(dmaker.SimpleDSDecisionMaker(ds))
    runner = sim_runner.SimulationRunner(
        profile.simulation, dm, profile.agent_builder,
        profile.parameterize_sim_agents, profile.add_patient_model,
        profile.add_disruptions)
    runner._update_patient(0)
    runner._update_agents(0)
    data = []
    for pr in range(periods):
        runner.next_cycle(False)
        if pr > 0:
            data.append(compute_agent_metrics(
                profile.simulation, profile.simulation.now))
    return data


def run_study(episodes, periods, seeds):
    dis_start = config.DISRUPTIONS[0]['happen_day_1']
    dis_end = config.DISRUPTIONS[0]['end_day_1']
    warmup = getattr(config, 'WARMUP_PERIODS', 0)

    all_results = {}
    for seed in seeds:
        print(f'\n{"="*90}')
        print(f'  SEED = {seed}')
        print(f'{"="*90}')

        baseline = _run_baseline(periods, seed)

        for mab_name in MAB_CONFIGS:
            tag = f'{mab_name}_seed{seed}'
            print(f'\n  --- {mab_name} (seed {seed}) ---')
            drl_eps, curve = _run_drl(episodes, periods, mab_name, seed)
            last_ep = episodes - 1
            drl_data = drl_eps[last_ep]

            pre = (max(1, warmup), max(warmup, dis_start - 1))
            during = (max(warmup + 1, dis_start), dis_end)
            post = (dis_end + 1, periods)

            print(f'\n  Results: {mab_name} (ep {last_ep}) vs Baseline')
            results = {}
            for phase, (s, e) in [('pre', pre), ('during', during), ('post', post)]:
                b = summarize_period_range(baseline, s, e, 'b')
                d = summarize_period_range(drl_data, s, e, 'd')
                r = print_comparison(b, d, f'{mab_name} {phase.upper()} ({s}-{e})')
                results[phase] = {k: float(v) for k, v in r.items()}

            all_results[tag] = {
                'mab_config': mab_name,
                'seed': seed,
                'results': results,
                'learning_curve': curve,
            }

    # Summary
    print(f'\n{"="*90}')
    print(f'  STUDY 3 SUMMARY: MAB Ablation (Fixed vs Adaptive)')
    print(f'  {len(seeds)} seed(s), {episodes} eps x {periods} periods')
    print(f'{"="*90}')

    for phase in ['pre', 'during', 'post']:
        print(f'\n  --- {phase.upper()} ---')
        print(f'  {"Config":<20} | {"Profit Diff":>12} | {"Sys Bklg Diff":>13} | {"Verdict":>8}')
        print(f'  {"-"*20}-+-{"-"*12}-+-{"-"*13}-+-{"-"*8}')
        for mab_name in MAB_CONFIGS:
            pd_vals = [all_results[f'{mab_name}_seed{s}']['results'][phase]['profit_diff']
                       for s in seeds]
            sb_vals = [all_results[f'{mab_name}_seed{s}']['results'][phase]['sys_bklg_diff']
                       for s in seeds]
            pd_m, sb_m = np.mean(pd_vals), np.mean(sb_vals)
            verdict = ('PASS' if pd_m > 0 and sb_m < 0
                       else 'PARTIAL' if pd_m > 0 or sb_m < 0 else 'FAIL')
            print(f'  {mab_name:<20} | {pd_m:+12.1f} | {sb_m:+13.1f} | {verdict:>8}')

    out_dir = os.path.join('checkpoints', 'study3_mab_ablation')
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, 'results.json'), 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    config.save_config_snapshot(out_dir)
    print(f'\n  Results saved to {out_dir}/results.json')


def main():
    p = argparse.ArgumentParser(description='Study 3: MAB ablation')
    p.add_argument('--fast', action='store_true')
    p.add_argument('--episodes', type=int, default=None)
    p.add_argument('--periods', type=int, default=None)
    p.add_argument('--seeds', type=str, default=None)
    args = p.parse_args()

    if args.fast:
        episodes, periods = 50, 200
    else:
        episodes = args.episodes or getattr(config, 'EVAL_TRAIN_EPISODES', 45)
        periods = args.periods or min(config.TOTAL_PERIODS, 300)
    seeds = [int(s) for s in args.seeds.split(',')] if args.seeds else [config.RANDOM_SEED]

    dis_end = config.DISRUPTIONS[0]['end_day_1']
    if dis_end >= periods:
        periods = dis_end + 30

    print('=' * 90)
    print('  STUDY 3: MAB Ablation (Fixed vs Adaptive Reward)')
    print(f'  Episodes: {episodes}  Periods: {periods}  Seeds: {seeds}')
    print(f'  Configs: {list(MAB_CONFIGS.keys())}')
    print('=' * 90)

    run_study(episodes, periods, seeds)


if __name__ == '__main__':
    main()
