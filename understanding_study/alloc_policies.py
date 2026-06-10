"""DS allocation-rule variants for the allocation bound (E1).

`flexible_allocate` is a faithful copy of `allocate_proportional`
(simulator/decision_maker.py:411-463) with ONE pluggable step: how the per-destination
allocation caps (`allocate_to`) are computed. The FIFO backlog walk that converts caps into
AllocateDecisions is copied verbatim. rule='proportional' reproduces the original arithmetic
exactly (verified bit-for-bit by verify_alloc.py against the routing study's rung-c output).

Rules:
  proportional     original: cap_i = min(demand_i, demand_i * inventory / backlog)
  equal            cap_i = min(demand_i, inventory / n_downstream)
  prio_hc1 / prio_hc2   fill that HC's backlog first, remainder to the other
  backlog_priority fill the larger-backlog HC first (dynamic)
  serve_captive    fill first the HC with the larger recent incoming-order volume at this DS
                   (the customer whose demand is still routed here), 5-period window
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import simulator.decision_maker as dmaker
from simulator.decision import AllocateDecision, OrderDecision


def _priority_caps(agent, demand_of, inventory, order):
    """Fill destinations in `order`; each gets min(its demand, remaining inventory)."""
    caps = {a: 0 for a in demand_of}
    remaining = inventory
    for a in order:
        give = int(min(demand_of.get(a, 0), remaining))
        caps[a] = give
        remaining -= give
    return caps


def _recent_incoming_by_src(agent, now, window=5):
    vol = {}
    for t in range(max(1, now - window), now + 1):
        if agent.is_history_available(t):
            for order in agent.get_history_item(t).get('incoming_order', []):
                vol[order.src] = vol.get(order.src, 0) + order.amount
    return vol


def flexible_allocate(agent, rule, now, ctx=None):
    """ctx: optional decision-maker instance carrying state for the stateful rules
    (mn_down flag, EMA weights, cumulative fill counters). Stateless rules ignore it."""
    backlog = agent.backlog_level()
    inventory = agent.inventory_level()
    if inventory == 0 or backlog == 0:
        return 0

    demand_of = {}
    for a in agent.downstream_nodes:
        demand_of[a] = 0
    for bl in agent.backlog:
        if bl.src not in demand_of:
            demand_of[bl.src] = 0
        demand_of[bl.src] += bl.amount

    if rule == 'proportional':
        allocate_to = {}
        for ag in agent.downstream_nodes:
            allocate_to[ag] = int(min(demand_of[ag],
                                      (float(demand_of[ag] * inventory) / backlog)))
    elif rule == 'equal':
        n = len(agent.downstream_nodes)
        allocate_to = {ag: int(min(demand_of[ag], float(inventory) / n))
                       for ag in agent.downstream_nodes}
    elif rule in ('prio_hc1', 'prio_hc2'):
        hcs = sorted(a for a in demand_of if a.startswith('hc_'))
        first = hcs[0] if rule == 'prio_hc1' else hcs[-1]
        order = [first] + [a for a in demand_of if a != first]
        allocate_to = _priority_caps(agent, demand_of, inventory, order)
    elif rule == 'backlog_priority':
        order = sorted(demand_of, key=lambda a: demand_of[a], reverse=True)
        allocate_to = _priority_caps(agent, demand_of, inventory, order)
    elif rule == 'serve_captive':
        vol = _recent_incoming_by_src(agent, now)
        order = sorted(demand_of, key=lambda a: vol.get(a, 0), reverse=True)
        allocate_to = _priority_caps(agent, demand_of, inventory, order)
    elif rule == 'rotating_priority':
        # fairness-neutral variant of strict priority: the prioritized HC alternates
        # by period parity, so neither HC is systematically starved
        hcs = sorted(a for a in demand_of if a.startswith('hc_'))
        first = hcs[now % len(hcs)] if hcs else None
        order = ([first] if first else []) + [a for a in demand_of if a != first]
        allocate_to = _priority_caps(agent, demand_of, inventory, order)
    elif rule in ('shed_timed', 'shed_inverse'):
        # DS-seat demand-shaping (rung-a world): while this DS's MN is down (ctx.mn_down,
        # wired from the shared upstream signal), strict priority to ONE HC:
        #   shed_timed   -> the captive HC (equal-split, sorted last): serve the customer
        #                   whose demand is stuck here; let the trust-routed HC leave faster
        #   shed_inverse -> the trust-routed HC (control: protect the footloose customer)
        # Outside the down window: plain proportional.
        down = bool(getattr(ctx, 'mn_down', False)) if ctx is not None else False
        if down:
            hcs = sorted(a for a in demand_of if a.startswith('hc_'))
            first = hcs[-1] if rule == 'shed_timed' else hcs[0]
            order = [first] + [a for a in demand_of if a != first]
            allocate_to = _priority_caps(agent, demand_of, inventory, order)
        else:
            allocate_to = {ag: int(min(demand_of[ag],
                                       (float(demand_of[ag] * inventory) / backlog)))
                           for ag in agent.downstream_nodes}
    elif rule == 'smoothed_backlog':
        # backlog-leaning split with EMA smoothing: tests whether SHARPNESS (not direction)
        # is what the trust loop punishes. alpha from ctx.alloc_alpha (default 0.2).
        alpha = float(getattr(ctx, 'alloc_alpha', 0.2)) if ctx is not None else 0.2
        ema = getattr(ctx, '_alloc_ema', None)
        if ema is None:
            ema = {a: 1.0 / max(1, len(agent.downstream_nodes))
                   for a in agent.downstream_nodes}
        tot_b = sum(demand_of.values())
        for a in agent.downstream_nodes:
            share = demand_of[a] / tot_b if tot_b > 0 else 1.0 / len(demand_of)
            ema[a] = (1 - alpha) * ema.get(a, 0.5) + alpha * share
        if ctx is not None:
            ctx._alloc_ema = ema
        sum_w = sum(ema.values()) or 1.0
        allocate_to = {a: int(min(demand_of[a], inventory * ema[a] / sum_w))
                       for a in agent.downstream_nodes}
    elif rule == 'fill_equalize':
        # allocate to equalize cumulative planned-fill across HCs: weights ~ (1 - fill_i)
        cd = getattr(ctx, '_cum_dem', {}) if ctx is not None else {}
        ca = getattr(ctx, '_cum_alloc', {}) if ctx is not None else {}
        w = {}
        for a in agent.downstream_nodes:
            fill_i = (ca.get(a, 0.0) / cd[a]) if cd.get(a, 0) > 0 else 0.0
            w[a] = max(0.05, 1.0 - fill_i)
        sum_w = sum(w.values()) or 1.0
        allocate_to = {a: int(min(demand_of[a], inventory * w[a] / sum_w))
                       for a in agent.downstream_nodes}
    elif rule == 'smoothed_captive_gated':
        # the trust-aware cell: while down, EMA-smoothed lean toward the captive HC
        # (target weight 0.75) instead of a hard cutover; reverts smoothly after recovery
        alpha = float(getattr(ctx, 'alloc_alpha', 0.2)) if ctx is not None else 0.2
        down = bool(getattr(ctx, 'mn_down', False)) if ctx is not None else False
        hcs = sorted(a for a in demand_of if a.startswith('hc_'))
        captive = hcs[-1]
        target = {a: (0.75 if a == captive else 0.25 / max(1, len(hcs) - 1))
                  for a in agent.downstream_nodes} if down else \
                 {a: 1.0 / max(1, len(agent.downstream_nodes))
                  for a in agent.downstream_nodes}
        ema = getattr(ctx, '_alloc_ema', None)
        if ema is None:
            ema = dict(target)
        for a in agent.downstream_nodes:
            ema[a] = (1 - alpha) * ema.get(a, target[a]) + alpha * target[a]
        if ctx is not None:
            ctx._alloc_ema = ema
        sum_w = sum(ema.values()) or 1.0
        allocate_to = {a: int(min(demand_of[a], inventory * ema[a] / sum_w))
                       for a in agent.downstream_nodes}
    elif rule == 'prio_floor':
        # strict priority to hc-first, but the other HC is guaranteed a floor of 25%
        # of available inventory first (fairness floor under scarcity)
        hcs = sorted(a for a in demand_of if a.startswith('hc_'))
        first, second = hcs[0], hcs[-1]
        floor_amt = int(min(demand_of.get(second, 0), 0.25 * inventory))
        allocate_to = {a: 0 for a in demand_of}
        allocate_to[second] = floor_amt
        remaining = inventory - floor_amt
        give_first = int(min(demand_of.get(first, 0), remaining))
        allocate_to[first] = give_first
        remaining -= give_first
        allocate_to[second] += int(min(demand_of.get(second, 0) - floor_amt,
                                       max(0, remaining)))
    else:
        raise ValueError(f'unknown allocation rule: {rule}')

    allocated = sum(allocate_to.values())

    if ctx is not None:   # cumulative counters for fill_equalize
        cd = getattr(ctx, '_cum_dem', {})
        ca = getattr(ctx, '_cum_alloc', {})
        for a in agent.downstream_nodes:
            cd[a] = cd.get(a, 0.0) + demand_of[a]
            ca[a] = ca.get(a, 0.0) + allocate_to.get(a, 0)
        ctx._cum_dem, ctx._cum_alloc = cd, ca

    # FIFO backlog walk — verbatim from allocate_proportional (decision_maker.py:434-461)
    inv_ptr = 0
    inv_left = agent.inventory[0].amount
    for bl in agent.backlog:
        bl_left = bl.amount
        while allocate_to[bl.src] > 0 and bl_left > 0:
            if inv_ptr >= len(agent.inventory):
                break
            if min(allocate_to[bl.src], bl_left) <= inv_left:
                decision_al = AllocateDecision()
                decision_al.amount = min(allocate_to[bl.src], bl_left)
                allocate_to[bl.src] -= decision_al.amount
                bl_left -= decision_al.amount
                inv_left -= decision_al.amount
                decision_al.item = agent.inventory[inv_ptr]
                decision_al.order = bl
                agent.decisions.append(decision_al)
            else:
                decision_al = AllocateDecision()
                decision_al.amount = inv_left
                allocate_to[bl.src] -= decision_al.amount
                bl_left -= decision_al.amount
                decision_al.item = agent.inventory[inv_ptr]
                decision_al.order = bl
                agent.decisions.append(decision_al)
                inv_ptr += 1
                if inv_ptr >= len(agent.inventory):
                    break
                inv_left = agent.inventory[inv_ptr].amount

    return allocated


class AllocFlexibleDS(dmaker.SimpleDSDecisionMaker):
    """SimpleDSDecisionMaker ordering logic (verbatim) with a pluggable allocation rule.
    rule='proportional' must be indistinguishable from the original class."""

    def __init__(self, ds, rule='proportional'):
        super().__init__(ds)
        self.rule = rule
        self.last_order_amount = 0

    def make_decision(self, now):
        inventory = self.ds.inventory_level()
        allocated = flexible_allocate(self.ds, self.rule, now)
        inventory -= allocated
        on_order = sum(o.amount for o in self.ds.on_order)
        backlog = self.ds.backlog_level()
        backlog -= allocated
        order_amount = max(self.ds.up_to_level + backlog - on_order - inventory, 0)
        max_order = max(2.0 * self.ds.predicted_demand, 120)
        order_amount = min(order_amount, max_order)
        self.last_order_amount = order_amount
        num_upstream_nodes = len(self.ds.upstream_nodes)
        for agent in self.ds.upstream_nodes:
            per_up_order = int(float(order_amount) / num_upstream_nodes)
            decision = OrderDecision()
            decision.upstream = agent
            decision.amount = per_up_order
            self.ds.decisions.append(decision)
