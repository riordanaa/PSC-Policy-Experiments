"""
Study 1: GRU vs Dense  --  Automated comparison runner.

Trains both architectures under identical config, then prints a side-by-side
comparison table (profit, backlog, learning curve).

Usage:
  # Quick smoke (few episodes, short horizon)
  python study_gru_vs_dense.py --fast

  # Full run (longer training)
  python study_gru_vs_dense.py --episodes 100 --periods 300

  # Multi-seed for statistical confidence
  python study_gru_vs_dense.py --episodes 80 --seeds 42,123,256
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


def _run_drl(episodes, periods, layer_type, seed):
    """Train DRL with given layer_type, return per-episode metrics + learning curve."""
    config.DRL_LAYER_TYPE = layer_type
    config.set_global_seeds(seed)
    tf.keras.backend.clear_session()

    profile = ConfigDrivenProfile(f'study1_{layer_type}')
    for d in profile.simulation.disruptions:
        d.happen_day_1 = config.DISRUPTIONS[0]['happen_day_1']
        d.end_day_1 = config.DISRUPTIONS[0]['end_day_1']

    dm = dmaker.PerAgentDecisionMaker()
    hc_dms = []
    for i, hc in enumerate(profile.health_centers):
        recipe = config.HC_ORDER_SPLIT[i] if i < len(config.HC_ORDER_SPLIT) else 'equally'
        hc_dm = dmaker.SimpleHCDecisionMaker(hc, recipe)
        dm.add_decision_maker(hc_dm)
        hc_dms.append(hc_dm)
    mn_dms = []
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
        print(f'    [{layer_type}] Ep {eps:3d}/{episodes}: '
              f'bklg={ds_bklg:7.1f}  profit={ds_profit:9.1f}  ({elapsed:.1f}s)')

    return all_episodes, learning_curve


def _run_baseline(periods, seed):
    """Run deterministic baseline (base-stock DS) for one episode."""
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


def _evaluate_window(drl_data, baseline_data, start, end, label):
    b = summarize_period_range(baseline_data, start, end, 'b')
    d = summarize_period_range(drl_data, start, end, 'd')
    return print_comparison(b, d, label)


def run_study(episodes, periods, seeds):
    """Run GRU and Dense under each seed, collect results, print summary."""
    dis_start = config.DISRUPTIONS[0]['happen_day_1']
    dis_end = config.DISRUPTIONS[0]['end_day_1']
    warmup = getattr(config, 'WARMUP_PERIODS', 0)

    original_layer_type = config.DRL_LAYER_TYPE

    all_results = {}

    for seed in seeds:
        print(f'\n{"="*90}')
        print(f'  SEED = {seed}')
        print(f'{"="*90}')

        print(f'\n  --- Baseline (seed {seed}) ---')
        baseline = _run_baseline(periods, seed)

        for layer_type in ['GRU', 'Dense']:
            tag = f'{layer_type}_seed{seed}'
            print(f'\n  --- {layer_type} training (seed {seed}) ---')
            drl_eps, curve = _run_drl(episodes, periods, layer_type, seed)

            last_ep = episodes - 1
            drl_data = drl_eps[last_ep]

            pre = (max(1, warmup), max(warmup, dis_start - 1))
            during = (max(warmup + 1, dis_start), dis_end)
            post = (dis_end + 1, periods)

            print(f'\n  Results: {layer_type} (ep {last_ep}) vs Baseline  [seed={seed}]')
            r_pre = _evaluate_window(
                drl_data, baseline, pre[0], pre[1],
                f'{layer_type} PRE-DISRUPTION ({pre[0]}-{pre[1]})')
            r_dur = _evaluate_window(
                drl_data, baseline, during[0], during[1],
                f'{layer_type} DURING DISRUPTION ({during[0]}-{during[1]})')
            r_post = _evaluate_window(
                drl_data, baseline, post[0], post[1],
                f'{layer_type} POST-DISRUPTION ({post[0]}-{post[1]})')

            all_results[tag] = {
                'layer_type': layer_type,
                'seed': seed,
                'episodes': episodes,
                'periods': periods,
                'pre': {k: float(v) for k, v in r_pre.items()},
                'during': {k: float(v) for k, v in r_dur.items()},
                'post': {k: float(v) for k, v in r_post.items()},
                'learning_curve': curve,
            }

    config.DRL_LAYER_TYPE = original_layer_type

    # ---- Aggregate across seeds ----
    print(f'\n{"="*90}')
    print(f'  STUDY 1 SUMMARY: GRU vs Dense')
    print(f'  {len(seeds)} seed(s): {seeds}')
    print(f'  {episodes} episodes x {periods} periods')
    print(f'  Disruption MN1: {dis_start}-{dis_end}')
    print(f'{"="*90}')

    for phase in ['pre', 'during', 'post']:
        print(f'\n  --- {phase.upper()} ---')
        header = (f'  {"Arch":<8} | {"Profit Diff":>12} | {"DS Bklg Diff":>12} | '
                  f'{"Sys Bklg Diff":>13} | {"Verdict":>8}')
        print(header)
        print(f'  {"-"*8}-+-{"-"*12}-+-{"-"*12}-+-{"-"*13}-+-{"-"*8}')

        for layer_type in ['GRU', 'Dense']:
            pd_vals = []
            bd_vals = []
            sb_vals = []
            for seed in seeds:
                tag = f'{layer_type}_seed{seed}'
                r = all_results[tag][phase]
                pd_vals.append(r['profit_diff'])
                bd_vals.append(r['bklg_diff'])
                sb_vals.append(r['sys_bklg_diff'])
            pd_mean = np.mean(pd_vals)
            bd_mean = np.mean(bd_vals)
            sb_mean = np.mean(sb_vals)
            verdict = ('PASS' if pd_mean > 0 and sb_mean < 0
                       else 'PARTIAL' if pd_mean > 0 or sb_mean < 0
                       else 'FAIL')
            if len(seeds) > 1:
                pd_str = f'{pd_mean:+7.1f}+/-{np.std(pd_vals):5.1f}'
                bd_str = f'{bd_mean:+7.1f}+/-{np.std(bd_vals):5.1f}'
                sb_str = f'{sb_mean:+7.1f}+/-{np.std(sb_vals):5.1f}'
            else:
                pd_str = f'{pd_mean:+12.1f}'
                bd_str = f'{bd_mean:+12.1f}'
                sb_str = f'{sb_mean:+13.1f}'
            print(f'  {layer_type:<8} | {pd_str:>12} | {bd_str:>12} | {sb_str:>13} | {verdict:>8}')

    # ---- Learning curve comparison (last 10% mean) ----
    print(f'\n  --- LEARNING EFFICIENCY ---')
    print(f'  {"Arch":<8} | {"Final Profit":>13} | {"Final Bklg":>11} | '
          f'{"Avg Time/Ep":>12}')
    print(f'  {"-"*8}-+-{"-"*13}-+-{"-"*11}-+-{"-"*12}')
    for layer_type in ['GRU', 'Dense']:
        final_profits = []
        final_bklgs = []
        avg_times = []
        for seed in seeds:
            tag = f'{layer_type}_seed{seed}'
            curve = all_results[tag]['learning_curve']
            tail = curve[max(0, len(curve) - len(curve) // 10):]
            if tail:
                final_profits.append(np.mean([c['profit'] for c in tail]))
                final_bklgs.append(np.mean([c['ds_bklg'] for c in tail]))
                avg_times.append(np.mean([c['time_s'] for c in curve]))
        fp = np.mean(final_profits)
        fb = np.mean(final_bklgs)
        at = np.mean(avg_times)
        print(f'  {layer_type:<8} | {fp:13.1f} | {fb:11.1f} | {at:10.1f}s')

    # ---- Save JSON ----
    out_dir = os.path.join('checkpoints', 'study1_gru_vs_dense')
    os.makedirs(out_dir, exist_ok=True)
    summary_path = os.path.join(out_dir, 'results.json')
    with open(summary_path, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    config.save_config_snapshot(out_dir)
    print(f'\n  Full results saved to {summary_path}')

    # ---- Verdict ----
    gru_dur = np.mean([
        all_results[f'GRU_seed{s}']['during']['profit_diff'] for s in seeds])
    dense_dur = np.mean([
        all_results[f'Dense_seed{s}']['during']['profit_diff'] for s in seeds])
    winner = 'GRU' if gru_dur > dense_dur else 'Dense'
    margin = abs(gru_dur - dense_dur)
    print(f'\n  VERDICT: {winner} has higher profit during disruption '
          f'(margin={margin:.1f})')
    print(f'  GRU uses recurrent gates for temporal state encoding.\n')

    return all_results


def main():
    p = argparse.ArgumentParser(description='Study 1: GRU vs Dense comparison')
    p.add_argument('--fast', action='store_true',
                   help='Quick run: 12 episodes, 120 periods')
    p.add_argument('--episodes', type=int, default=None)
    p.add_argument('--periods', type=int, default=None)
    p.add_argument('--seeds', type=str, default=None,
                   help='Comma-separated seeds (default: config.RANDOM_SEED)')
    args = p.parse_args()

    if args.fast:
        episodes = 50
        periods = 200
    else:
        episodes = args.episodes or getattr(config, 'EVAL_TRAIN_EPISODES', 45)
        periods = args.periods or min(config.TOTAL_PERIODS, 300)

    if args.seeds:
        seeds = [int(s.strip()) for s in args.seeds.split(',')]
    else:
        seeds = [config.RANDOM_SEED]

    dis_end = config.DISRUPTIONS[0]['end_day_1']
    if dis_end >= periods:
        periods = dis_end + 30

    print('=' * 90)
    print('  STUDY 1: GRU vs Dense Architecture Comparison')
    print(f'  Topology: {config.N_MN}x{config.N_DS}x{config.N_HC}')
    print(f'  Episodes: {episodes}  Periods: {periods}')
    print(f'  Seeds: {seeds}')
    print(f'  Disruption: MN1 {config.DISRUPTIONS[0]["happen_day_1"]}'
          f'-{config.DISRUPTIONS[0]["end_day_1"]}')
    print('=' * 90)

    run_study(episodes, periods, seeds)
    return 0


if __name__ == '__main__':
    sys.exit(main())
