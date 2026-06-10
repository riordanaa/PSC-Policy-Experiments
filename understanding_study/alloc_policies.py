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


def flexible_allocate(agent, rule, now):
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
