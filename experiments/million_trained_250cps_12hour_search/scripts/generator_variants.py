"""Explicit experimental errand selection; the production generator is untouched."""
from dataclasses import dataclass, replace
from heapq import heapify, heappop, heappush
from itertools import count
from math import inf, log2

from ccsr.errands.generator import (_evaluate, initial_errands, added_purchase_errands,
                                    errand_price, price_horizon, generate_neighbors as original_neighbors)


@dataclass(frozen=True)
class Options:
    upgrade_bonus: float = 0.0
    distinct_results: bool = False
    diverse_queue: int = 0
    diverse_results: int = 0
    early_stop: bool = True
    strategy: str = 'upgrade_building'
    finite_horizon: float = 0.0
    safe_price_filter: bool = True
    all_evaluated: bool = False
    expansion_balance: float = 0.0
    seed_reserve: int = 0
    canonical_full_core: bool = False
    fast_evaluation: bool = False
    projection_budget: float = 0.0
    projection_weight: float = 0.0
    native_backend: bool = False
    native_anchor_all: bool = False
    two_step_pool: int = 0
    two_step_weight: float = 0.0
    upgrade_macros: bool = False
    expand_seeds: bool = False
    future_upgrade_mask: int = 0
    future_weight: float = 1.0
    future_counts: tuple = ()
    three_step: bool = False
    lookahead_branches: int = 6
    strategy_bins: int = 0
    canonical_partial: bool = False
    quantity_children: int = 0


def canonical_full_core(ancestor,errand):
    """Remove equivalent full-batch permutations, retaining partial-click order.

    Restricted to purchase-only x10 errands. Moving a full batch before a
    partial click reduces the latter's bank without changing its affordability:
    the remaining total still covers every recorded purchase. A full batch of
    the same building cannot legally follow a partial click of that building.
    Upgrades move only when their requirements are met by the full-batch core.
    """
    if ancestor.bulk_size!=10 or errand.sales: return errand
    full=[];partial=[];upgrades=[];counts=dict(ancestor.building_counts)
    for action in errand.purchase_order:
        if action.operation=='upgrade': upgrades.append(action)
        elif action.quantity==10:
            full.append(action);counts[action.item]+=10
        else: partial.append(action)
    if any(any(counts[b]<required for b,required in ancestor.upgrade_catalog[a.item].requirements) for a in upgrades):
        return errand
    order=tuple(sorted(full,key=lambda a:a.item)+sorted(upgrades,key=lambda a:a.item)+partial)
    return replace(errand,purchase_order=order)


def state_key(state):
    # Exact equivalence at a common starting state. Do not bucket quantities.
    return (tuple(state.building_counts.values()),frozenset(state.purchased_upgrades),
            state.bank,state.lifetime_cookies,state.handmade_cookies)


def strategy_key(neighbor, ancestor, kind):
    errand=neighbor.errand
    upgrades=tuple(sorted(errand.upgrades))
    if kind=='upgrades': return upgrades
    bought=tuple(i for i,n in enumerate(errand.building_quantities) if n)
    if kind=='upgrade_building': return upgrades,bought
    if kind=='dominant':
        dominant=max(range(len(errand.building_quantities)),key=lambda i:errand.building_quantities[i])
        return upgrades,dominant
    if kind=='size':
        return upgrades,bought,int(log2(max(1,sum(errand.building_quantities))))
    raise ValueError(kind)


def generate_neighbors(ancestor,target,width=10,price_horizon_multiplier=2,
                       singleton_only=False,search_width=None,queue_expansions=100,
                       max_errand_actions=100,options=Options(),trace=None):
    if options.native_backend:
        from native_bridge import generate_neighbors as native_generate
        return native_generate(ancestor,target,width,price_horizon_multiplier,singleton_only,
                               search_width,queue_expansions,max_errand_actions,options)
    if singleton_only:
        return original_neighbors(ancestor,target,width,price_horizon_multiplier,
                                  singleton_only,search_width,queue_expansions,max_errand_actions)
    search_width=width if search_width is None else search_width
    if min(width,search_width,queue_expansions,max_errand_actions)<=0:
        raise ValueError('Search limits must be positive')
    seen=set(); serial=count(); queue=[]; roster=[]; evaluated=[]; seeds=[]; expanded_groups={}
    ceiling=min(price_horizon(ancestor,price_horizon_multiplier),
                target-ancestor.lifetime_cookies+ancestor.bank)
    names=tuple(ancestor.building_catalog)
    if options.fast_evaluation:
        from fast_evaluator import Evaluator
        evaluate_raw=Evaluator(ancestor,target,price_horizon_multiplier)
    else:
        evaluate_raw=lambda errand:_evaluate(ancestor,target,errand,price_horizon_multiplier)
    price_cache={}
    score_cache={}
    future_additions={}
    future_gain=0.0
    if options.projection_budget and options.projection_weight:
        # Allocate a modest hypothetical future building budget using current
        # marginal production/price. Compare upgrades on this shared future
        # inventory; hypothetical buildings never enter the actual game state.
        budget=min(options.projection_budget,(target-ancestor.lifetime_cookies)*.25)
        virtual=ancestor.copy()
        affordable=[name for name in names if ancestor.building_price(name)<=budget]
        for _ in range(80):
            current_rate=virtual.cps();choices=[]
            for name in affordable:
                price=virtual.building_price(name)
                if price>budget:continue
                child=virtual.copy();child.building_counts[name]+=1
                child._automatic_cps_cache=None;child._automatic_cps_cache_achievement_count=None
                choices.append(((child.cps()-current_rate)/price,name,price,child))
            if not choices:break
            _,name,price,virtual=max(choices,key=lambda c:c[0])
            budget-=price;future_additions[name]=future_additions.get(name,0)+1
        future_gain=virtual.cps()-ancestor.cps()
    def building_cost(index,count_before,quantity):
        key=(index,count_before,quantity)
        if key not in price_cache:
            name=names[index]
            price_cache[key]=sum(ancestor.building_price(name,additional_owned=count_before+k)
                                 for k in range(quantity))
        return price_cache[key]
    def score(neighbor):
        if neighbor.errand in score_cache:return score_cache[neighbor.errand]
        value=neighbor.score
        if future_additions:
            projected=neighbor.gamestate.copy()
            for name,q in future_additions.items():projected.building_counts[name]+=q
            projected._automatic_cps_cache=None;projected._automatic_cps_cache_achievement_count=None
            current=neighbor.gamestate.cps()
            unseen=max(0,projected.cps()-current-future_gain)
            gain=current-ancestor.cps()+options.projection_weight*unseen
            if gain>0:value=neighbor.acquisition_time*current/gain
        if neighbor.errand.upgrades:
            value*=1-options.upgrade_bonus
        if options.finite_horizon:
            # Smoothly mixes local repayment time with finishing immediately;
            # this is deliberately heuristic, never a dominance assertion.
            finish=neighbor.gamestate.finish(target).age-ancestor.age
            value=(1-options.finite_horizon)*value+options.finite_horizon*finish
        score_cache[neighbor.errand]=value
        return value
    def order(n): return score(n),n.errand.action_count(ancestor.bulk_size)
    def evaluate(errand):
        if options.canonical_full_core: errand=canonical_full_core(ancestor,errand)
        if errand in seen or errand.action_count(ancestor.bulk_size)>max_errand_actions: return None
        seen.add(errand)
        neighbor=evaluate_raw(errand)
        if neighbor is not None and trace is not None: trace.append(neighbor)
        if neighbor is not None and options.all_evaluated: evaluated.append(neighbor)
        return neighbor
    def select(items,limit,cap):
        items=sorted(items,key=order)
        if not cap: return items[:limit]
        chosen=[]; left=[]; groups={}
        for n in items:
            key=strategy_key(n,ancestor,options.strategy)
            if groups.get(key,0)<cap:
                chosen.append(n); groups[key]=groups.get(key,0)+1
            else: left.append(n)
        # Reserve distinct strategies first, fill remaining capacity by score.
        return sorted((chosen[:limit]+left[:max(0,limit-len(chosen))]),key=order)
    def push(neighbor):
        if not options.diverse_queue:
            entry=(*order(neighbor),next(serial),neighbor)
            if len(queue)<search_width: heappush(queue,entry);return
            worst=max(range(len(queue)),key=lambda i:queue[i][:3])
            if entry[:2]<queue[worst][:2]: queue[worst]=entry;heapify(queue)
        else:
            candidates=[n[3] for n in queue]+[neighbor]
            selected=select(candidates,search_width,options.diverse_queue)
            queue[:]=[(*order(n),next(serial),n) for n in selected];heapify(queue)
    def children(parent):
        if not options.safe_price_filter or ancestor.selling_allowed:
            yield from added_purchase_errands(ancestor,parent);return
        # Costs only increase on purchase-only paths. Filter unaffordable
        # additions before replay; this changes no reachable child candidate.
        parent_price=errand_price(ancestor,parent)
        budget=ceiling-parent_price
        for child in added_purchase_errands(ancestor,parent):
            if child.upgrades!=parent.upgrades:
                extra=sum(ancestor.upgrade_catalog[n].price for n in child.upgrades-parent.upgrades)
            else:
                index=next(i for i,(a,b) in enumerate(zip(child.building_quantities,parent.building_quantities)) if a!=b)
                extra=building_cost(index,parent.building_quantities[index],child.building_quantities[index]-parent.building_quantities[index])
            if extra<=budget: yield child
    for errand in initial_errands(ancestor):
        n=evaluate(errand)
        if n is not None:
            seeds.append(n)
            push(n)
    for _ in range(queue_expansions):
        if not queue: break
        if options.early_stop and not ancestor.selling_allowed and len(roster)==width and queue[0][0]>order(roster[-1])[0]: break
        if options.expansion_balance:
            selected=min(range(len(queue)),key=lambda i:queue[i][0]*(1+options.expansion_balance*expanded_groups.get(strategy_key(queue[i][3],ancestor,options.strategy),0)))
            entry=queue[selected];queue[selected]=queue[-1];queue.pop();heapify(queue)
            n=entry[3]
        else: n=heappop(queue)[3]
        group=strategy_key(n,ancestor,options.strategy)
        expanded_groups[group]=expanded_groups.get(group,0)+1
        if options.distinct_results:
            key=state_key(n.gamestate)
            old=next((r for r in roster if state_key(r.gamestate)==key),None)
            if old is None: roster.append(n)
            elif (n.gamestate.age,order(n))<(old.gamestate.age,order(old)):
                roster.remove(old);roster.append(n)
        else: roster.append(n)
        roster=select(roster,width,options.diverse_results)
        for errand in children(n.errand):
            child=evaluate(errand)
            if child is not None: push(child)
    if options.all_evaluated:
        if options.distinct_results:
            by_state={}
            for n in evaluated:
                key=state_key(n.gamestate)
                old=by_state.get(key)
                if old is None or (n.gamestate.age,order(n))<(old.gamestate.age,order(old)):
                    by_state[key]=n
            evaluated=list(by_state.values())
        roster=select(evaluated,width,options.diverse_results)
    if options.seed_reserve:
        # Preserve the best standalone option for each upgrade or building
        # family, even when its local repayment score is poor.
        by_strategy={}
        for n in sorted(seeds,key=order):
            key=strategy_key(n,ancestor,'upgrade_building')
            by_strategy.setdefault(key,n)
        anchors=sorted(by_strategy.values(),key=order)[:options.seed_reserve]
        anchor_keys={state_key(n.gamestate) for n in anchors}
        roster=sorted(anchors+[n for n in roster if state_key(n.gamestate) not in anchor_keys][:max(0,width-len(anchors))],key=order)
    return tuple(roster)
