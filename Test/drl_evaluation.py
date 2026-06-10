"""
Train DRL for N episodes, then compare
LAST trained episode vs baseline using profit metric.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
import warnings; warnings.filterwarnings('ignore')

import numpy as np
import tensorflow as tf
import simulator.simulation_runner as sim_runner
import simulator.decision_maker as dmaker
from drl_simulation_profile_config import ConfigDrivenProfile
import config

TRAIN_EPISODES = getattr(config, 'EVAL_TRAIN_EPISODES', 45)
PERIODS = min(getattr(config, 'TOTAL_PERIODS', 300), 300)

_d0 = config.DISRUPTIONS[0] if config.DISRUPTIONS else {}
DISRUPTION_START = int(_d0.get('happen_day_1', 110))
DISRUPTION_END = int(_d0.get('end_day_1', 157))

f_profit = config.PROFIT_PER_UNIT
c_hold = config.INVENTORY_HOLDING_COST
h_bklg = config.BACKLOG_COST


def compute_agent_metrics(sim, period):
    """Compute profit + metrics for every agent at this period."""
    metrics = {}
    for ag in sim.agents:
        name = ag.name()
        hist = ag.get_history_item(period)
        allocated = sum(a['item'].amount for a in hist.get('allocate', []))
        inv = ag.inventory_level()
        if ag.agent_type == 'hc':
            bklg = getattr(ag, 'backlog_non_urgent', 0)
        else:
            bklg = ag.backlog_level() if hasattr(ag, 'backlog_level') else 0
        profit = f_profit * allocated - (c_hold * inv + h_bklg * bklg)
        metrics[name] = {'profit': profit, 'allocated': allocated, 'inv': inv, 'bklg': bklg}
    return metrics


def run_baseline():
    """Run baseline (base-stock DS) for 1 episode."""
    profile = ConfigDrivenProfile('baseline')
    for d in profile.simulation.disruptions:
        d.happen_day_1 = DISRUPTION_START
        d.end_day_1 = DISRUPTION_END
    dm = dmaker.PerAgentDecisionMaker()
    for i, hc in enumerate(profile.health_centers):
        recipe = config.HC_ORDER_SPLIT[i] if i < len(config.HC_ORDER_SPLIT) else 'equally'
        dm.add_decision_maker(dmaker.SimpleHCDecisionMaker(hc, recipe))
    for mn in profile.manufacturers:
        dm.add_decision_maker(dmaker.SimpleMNDecisionMaker(mn))
    for ds in profile.distributors:
        dm.add_decision_maker(dmaker.SimpleDSDecisionMaker(ds))
    runner = sim_runner.SimulationRunner(profile.simulation, dm, profile.agent_builder,
        profile.parameterize_sim_agents, profile.add_patient_model, profile.add_disruptions)
    runner._update_patient(0)
    runner._update_agents(0)

    data = []
    for pr in range(PERIODS):
        runner.next_cycle(False)
        if pr > 0:
            data.append(compute_agent_metrics(profile.simulation, profile.simulation.now))
    return data


def run_drl():
    """Train DRL for TRAIN_EPISODES, return per-period data for EACH episode."""
    profile = ConfigDrivenProfile('drl')
    for d in profile.simulation.disruptions:
        d.happen_day_1 = DISRUPTION_START
        d.end_day_1 = DISRUPTION_END
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
    tf.keras.backend.clear_session()
    drl_dms = []
    for i, ds in enumerate(profile.distributors):
        ds_dm = dmaker.DRLDSDecisionMaker(ds, mn_dms, hc_dms, PERIODS, f'DS {i+1}', TRAIN_EPISODES)
        dm.add_decision_maker(ds_dm)
        drl_dms.append(ds_dm)
    runner = sim_runner.SimulationRunner(profile.simulation, dm, profile.agent_builder,
        profile.parameterize_sim_agents, profile.add_patient_model, profile.add_disruptions)
    runner._update_patient(0)
    runner._update_agents(0)

    all_episodes = {}
    do_reset = False
    for eps in range(TRAIN_EPISODES):
        for d in drl_dms:
            d.ds_env.reset()
            d.episode = eps
        ep_data = []
        for pr in range(PERIODS):
            runner.next_cycle(do_reset)
            do_reset = False
            if pr > 0:
                ep_data.append(compute_agent_metrics(profile.simulation, profile.simulation.now))
        do_reset = True
        all_episodes[eps] = ep_data
    return all_episodes


def summarize_period_range(data, start, end, label):
    """Average metrics over a period range from a list of period-data dicts."""
    slice_data = data[max(0, start-1):min(len(data), end)]
    if not slice_data:
        return {}
    agents = sorted(slice_data[0].keys())
    totals = {}
    for ag in agents:
        vals = [d[ag] for d in slice_data if ag in d]
        totals[ag] = {
            'profit': np.mean([v['profit'] for v in vals]),
            'allocated': np.mean([v['allocated'] for v in vals]),
            'inv': np.mean([v['inv'] for v in vals]),
            'bklg': np.mean([v['bklg'] for v in vals]),
        }
    return totals


def print_comparison(baseline_metrics, drl_metrics, period_label):
    """Print side-by-side comparison for a period window."""
    agents = sorted(set(list(baseline_metrics.keys()) + list(drl_metrics.keys())))
    ds_agents = [a for a in agents if a.startswith('ds_')]
    hc_agents = [a for a in agents if a.startswith('hc_')]

    b_profit = sum(baseline_metrics.get(a, {}).get('profit', 0) for a in agents)
    d_profit = sum(drl_metrics.get(a, {}).get('profit', 0) for a in agents)
    b_bklg = sum(baseline_metrics.get(a, {}).get('bklg', 0) for a in ds_agents)
    d_bklg = sum(drl_metrics.get(a, {}).get('bklg', 0) for a in ds_agents)
    b_hc_b = sum(baseline_metrics.get(a, {}).get('bklg', 0) for a in hc_agents)
    d_hc_b = sum(drl_metrics.get(a, {}).get('bklg', 0) for a in hc_agents)
    b_sys_b = b_bklg + b_hc_b
    d_sys_b = d_bklg + d_hc_b

    print(f"\n  {period_label}:")
    print(f"    {'':10} | {'Baseline':>12} | {'DRL':>12} | {'Diff':>10} | {'Winner':>10}")
    print(f"    {'-'*10}-+-{'-'*12}-+-{'-'*12}-+-{'-'*10}-+-{'-'*10}")
    pw = 'DRL' if d_profit > b_profit else 'Baseline'
    bw = 'DRL' if d_bklg < b_bklg else 'Baseline'
    sw = 'DRL' if d_sys_b < b_sys_b else 'Baseline'
    print(f"    {'Profit':10} | {b_profit:12.1f} | {d_profit:12.1f} | {d_profit-b_profit:+10.1f} | {pw:>10}")
    print(f"    {'DS Backlog':10} | {b_bklg:12.1f} | {d_bklg:12.1f} | {d_bklg-b_bklg:+10.1f} | {bw:>10}")
    print(f"    {'HC Backlog':10} | {b_hc_b:12.1f} | {d_hc_b:12.1f} | {d_hc_b-b_hc_b:+10.1f} | "
          f"{'DRL' if d_hc_b < b_hc_b else 'Baseline':>10}")
    print(f"    {'DS+HC Bklg':10} | {b_sys_b:12.1f} | {d_sys_b:12.1f} | {d_sys_b-b_sys_b:+10.1f} | {sw:>10}")

    for ag in ds_agents:
        bm = baseline_metrics.get(ag, {'profit':0,'bklg':0,'inv':0,'allocated':0})
        dm = drl_metrics.get(ag, {'profit':0,'bklg':0,'inv':0,'allocated':0})
        print(f"    {ag:10} | P:{bm['profit']:7.0f} B:{bm['bklg']:5.0f} | P:{dm['profit']:7.0f} B:{dm['bklg']:5.0f} |")

    return {
        'profit_diff': d_profit - b_profit,
        'bklg_diff': d_bklg - b_bklg,
        'sys_bklg_diff': d_sys_b - b_sys_b,
    }


if __name__ == '__main__':
    config.set_global_seeds()
    print("=" * 80)
    print(f"  DRL vs BASELINE Comparison")
    print(f"  {config.N_MN}MN x {config.N_DS}DS x {config.N_HC}HC")
    print(f"  Train: {TRAIN_EPISODES} eps x {PERIODS} periods")
    print(f"  Disruption: MN1 days {DISRUPTION_START}-{DISRUPTION_END} (95% capacity loss)")
    print(f"  Profit: f={f_profit} c={c_hold} h={h_bklg}")
    print(f"  Random seed: {config.RANDOM_SEED}")
    print("=" * 80)

    _snap = os.path.join('checkpoints', 'drl_vs_baseline')
    config.save_config_snapshot(_snap)
    config.save_run_seed_metadata(_snap, None)

    print("\n--- Training DRL ---")
    drl_episodes = run_drl()

    print("\n--- Running Baseline ---")
    baseline_data = run_baseline()

    pre_dis = (1, DISRUPTION_START - 1)
    during_dis = (DISRUPTION_START, DISRUPTION_END)
    post_dis = (DISRUPTION_END + 1, PERIODS)

    baseline_pre = summarize_period_range(baseline_data, *pre_dis, "pre")
    baseline_dur = summarize_period_range(baseline_data, *during_dis, "dur")
    baseline_post = summarize_period_range(baseline_data, *post_dis, "post")

    last_ep = TRAIN_EPISODES - 1
    drl_data = drl_episodes[last_ep]
    drl_pre = summarize_period_range(drl_data, *pre_dis, "pre")
    drl_dur = summarize_period_range(drl_data, *during_dis, "dur")
    drl_post = summarize_period_range(drl_data, *post_dis, "post")

    print(f"\n{'='*80}")
    print(f"  RESULTS: DRL (episode {last_ep}) vs Baseline")
    print(f"{'='*80}")

    r1 = print_comparison(baseline_pre, drl_pre, f"PRE-DISRUPTION (periods 1-{DISRUPTION_START-1})")
    r2 = print_comparison(baseline_dur, drl_dur, f"DURING DISRUPTION (periods {DISRUPTION_START}-{DISRUPTION_END})")
    r3 = print_comparison(baseline_post, drl_post, f"POST-DISRUPTION (periods {DISRUPTION_END+1}-{PERIODS})")
    r_all = print_comparison(
        summarize_period_range(baseline_data, 1, PERIODS, "all"),
        summarize_period_range(drl_data, 1, PERIODS, "all"),
        f"OVERALL (periods 1-{PERIODS})")

    # Learning curve
    print(f"\n  LEARNING CURVE (total DS backlog per episode):")
    for eps in range(TRAIN_EPISODES):
        ep_data = drl_episodes[eps]
        ds_bklg = np.mean([sum(d[a]['bklg'] for a in d if a.startswith('ds_')) for d in ep_data])
        ds_profit = np.mean([sum(d[a]['profit'] for a in d) for d in ep_data])
        bar = '#' * max(0, int(50 - ds_bklg / 20))
        print(f"    Ep {eps:2d}: bklg={ds_bklg:6.0f} profit={ds_profit:8.0f} {bar}")

    print(f"\n{'='*80}")
    print(f"  Expected: DRL BETTER during/after disruption")
    print(f"  Profit during disruption: {'DRL BETTER' if r2['profit_diff'] > 0 else 'BASELINE BETTER'}")
    print(f"  DS backlog during disruption: {'DRL BETTER' if r2['bklg_diff'] < 0 else 'BASELINE BETTER'}")
    print(f"  System backlog (DS+HC): {'DRL BETTER' if r2['sys_bklg_diff'] < 0 else 'BASELINE BETTER'}")
    print(f"{'='*80}")
