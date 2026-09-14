"""Anytime reference-guided searches with configurable experimental neighbors."""
from dataclasses import dataclass
from functools import partial
from heapq import heappop, heappush, nsmallest
from itertools import count
from time import monotonic

from ccsr.routes import action_errands, apply_errand
from ccsr.routing_algorithms.beam_search_router import BeamSearchResult, BeamSearchStats
from ccsr.routing_algorithms.route_ruler import RouteRuler
from ccsr.routing_algorithms.parallel_neighbors import NeighborExecutor
import ccsr.routing_algorithms.parallel_neighbors as parallel_module
from generator_variants import generate_neighbors, Options


@dataclass(frozen=True)
class SearchOptions:
    seconds: float = 300
    width: int = 20
    inner_width: int = 40
    queue_expansions: int = 100
    horizon: float = 16
    max_actions: int = 12
    max_expansions: int = 10000000
    order_scale: float = 1.01
    prune_scale: float = .94
    prune_slack: float = 0
    handmade_cap: bool = True
    seed_prefixes: bool = True
    workers: int = 4
    heap_limit: int = 200000


def find_route(initial,target,ruler_route,options=SearchOptions(),generator_options=Options(),on_progress=None,on_improvement=None,extra_seeds=()):
    initial=initial.copy()
    ruler=RouteRuler(ruler_route,options.order_scale)
    prune=RouteRuler(ruler_route,options.prune_scale)
    cap=max((u.handmade_required for u in initial.upgrade_catalog.values() if u.price<target),default=0)
    if options.handmade_cap:
        if initial.selling_allowed: raise ValueError('Handmade cap experiment only supports no selling')
        if initial.lifetime_cookies or initial.bank: raise ValueError('Handmade cap requires fresh state')
    def key(s):
        return (tuple(s.building_counts.values()),frozenset(s.purchased_upgrades),s.bank,s.lifetime_cookies,
                min(s.handmade_cookies,cap) if options.handmade_cap else s.handmade_cookies)
    parents={};best_states={key(initial):initial};serial=count();queue=[]
    heappush(queue,(initial.age+ruler(initial),next(serial),initial))
    best_finish=ruler_route.final_gamestate;best_goal=None
    generated=expanded=relaxed=stale=heuristics=0; maximum=1; dropped=0
    def reconstruct(state):
        errands=[]
        while state in parents:
            state,errand=parents[state];errands.append(errand)
        return tuple(reversed(errands))
    def emit_candidate(state,finish):
        if on_improvement is not None:
            on_improvement(finish,reconstruct(state))
    if options.seed_prefixes:
        for seed in (ruler_route,)+tuple(extra_seeds):
            state=initial
            for actions in action_errands(seed):
                child,purchases=apply_errand(state,actions)
                k=key(child);previous=best_states.get(k)
                if previous is not None and previous.age<=child.age:
                    state=previous;continue
                parents[child]=(state,purchases);best_states[k]=child
                heappush(queue,(child.age+ruler(child),next(serial),child));state=child
                finish=child.finish(target)
                if finish.age<best_finish.age:
                    best_goal=child;best_finish=finish;emit_candidate(child,finish)
    parallel_module.generate_neighbors=partial(generate_neighbors,options=generator_options)
    started=monotonic();next_progress=started+30;termination='queue_exhausted'
    with NeighborExecutor(options.workers,target,dict(width=options.width,
            search_width=options.inner_width,queue_expansions=options.queue_expansions,
            price_horizon_multiplier=options.horizon,max_errand_actions=options.max_actions)) as executor:
        while queue:
            now=monotonic()
            if now-started>=options.seconds: termination='wall_time_limit';break
            if expanded>=options.max_expansions: termination='expansion_limit';break
            if now>=next_progress:
                if on_progress:
                    on_progress(dict(elapsed=now-started,expanded=expanded,generated=generated,queue=len(queue),
                                     best_finish=best_finish.age,stale=stale,dropped=dropped))
                next_progress=now+30
            executor.prefetch(queue,lambda s:best_states.get(key(s)) is s,float('inf'))
            _,_,state=heappop(queue)
            if best_states.get(key(state)) is not state:stale+=1;continue
            if state.age+prune(state)>=best_finish.age+options.prune_slack:continue
            expanded+=1
            neighbors=executor.neighbors(state);generated+=len(neighbors)
            for n in neighbors:
                child=n.gamestate
                if child.cps()<=0:continue
                k=key(child);previous=best_states.get(k)
                if previous is not None and previous.age<=child.age:continue
                best_states[k]=child;parents[child]=(state,n.purchases);relaxed+=1
                finish=child.finish(target)
                if finish.age<best_finish.age-1e-10:
                    best_finish=finish;best_goal=child;emit_candidate(child,finish)
                priority=child.age+ruler(child);heuristics+=1
                heappush(queue,(priority,next(serial),child))
            maximum=max(maximum,len(queue))
            if options.heap_limit and len(queue)>options.heap_limit*1.2:
                live=[e for e in queue if best_states.get(key(e[2])) is e[2]]
                kept=nsmallest(options.heap_limit,live)
                dropped+=len(queue)-len(kept)
                queue=kept
                # Pruned states remain in the dominance map and ancestry.
                # This is a heuristic beam bound, not an exhaustive search.
    errands=ruler_route.errands if best_goal is None else reconstruct(best_goal)
    stats=BeamSearchStats(monotonic()-started,expanded,generated,relaxed,stale,heuristics,maximum,False,ruler_route.final_gamestate.age,termination)
    return BeamSearchResult(initial,best_finish,errands,stats,ruler_route)
