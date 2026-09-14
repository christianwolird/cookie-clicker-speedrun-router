"""ctypes adapter for optional compiled experiments; Python replay is authoritative."""
import ctypes as C
import json
import os
from pathlib import Path
from ccsr.routes import RouteAction

DATA=json.loads(Path(__file__).with_name('native_names.json').read_text())
BUILDINGS=DATA['buildings'];UPGRADES=DATA['upgrades'];MAX_ACTIONS=16
class State(C.Structure):
    _fields_=[('buildings',C.c_int32*len(BUILDINGS)),('upgrades',C.c_uint32),('age',C.c_double),
              ('baked',C.c_double),('handmade',C.c_double),('bank',C.c_double)]

def pack_state(s):
    if (s.version,s.click_rate,s.errand_delay,s.action_delay,s.bulk_size,s.selling_allowed,s.legacy_errands,s.achievement_curve)!=('2.031',250,.4,.1,10,False,False,None):
        raise ValueError('Native prototype supports only the trained 250 CPS v2 fixed x10 no-selling setup')
    if any(q for n,q in s.building_counts.items() if n not in BUILDINGS):raise ValueError('Unrepresented building')
    if any(n not in UPGRADES for n in s.purchased_upgrades):raise ValueError('Unrepresented upgrade')
    return State((C.c_int32*len(BUILDINGS))(*(s.building_counts[n] for n in BUILDINGS)),
                 sum(1<<UPGRADES.index(n) for n in s.purchased_upgrades),s.age,s.lifetime_cookies,s.handmade_cookies,s.bank)

def unpack_state(s,ancestor):
    child=ancestor.copy()
    for i,n in enumerate(BUILDINGS):child.building_counts[n]=s.buildings[i]
    child.purchased_upgrades={n for i,n in enumerate(UPGRADES) if s.upgrades&(1<<i)}
    child.age=s.age;child.lifetime_cookies=s.baked;child.handmade_cookies=s.handmade;child.bank=s.bank
    child._automatic_cps_cache=None;child._automatic_cps_cache_achievement_count=None
    return child

def pack_actions(actions):
    result=[]
    for a in actions:
        if a.operation=='buy': result.append(BUILDINGS.index(a.item)*16+a.quantity)
        elif a.operation=='upgrade':result.append(256+UPGRADES.index(a.item))
        else:raise ValueError('Native prototype does not support sales')
    return (C.c_uint16*len(result))(*result)

def unpack_actions(codes):
    return tuple(RouteAction('upgrade',UPGRADES[c-256]) if c>=256 else RouteAction('buy',BUILDINGS[c//16],c%16) for c in codes)

LIB=C.CDLL(str(Path(os.environ.get('CCSR_EXPERIMENT_DIRECTORY','/tmp/ccsr-trained-12h-20260914'))/'native_search.so'))
LIB.native_evaluate.argtypes=[C.POINTER(State),C.POINTER(C.c_uint16),C.c_int,C.POINTER(State),C.c_double,C.c_double]
LIB.native_evaluate.restype=C.c_int
LIB.native_rates.argtypes=[C.POINTER(State),C.POINTER(C.c_double)]
LIB.native_rates.restype=None

def evaluate(state,actions,target=1e6,horizon=16):
    packed=pack_state(state);codes=pack_actions(actions);out=State()
    if not LIB.native_evaluate(C.byref(packed),codes,len(codes),C.byref(out),target,horizon or 0):return None
    return unpack_state(out,state)

class NativeOptions(C.Structure):
    _fields_=[(n,C.c_int) for n in ('width','search_width','pops','max_actions','canonical','early_stop','all_evaluated','queue_diversity','result_diversity','seed_reserve','anchor_all','two_step_pool','upgrade_macros','expand_seeds','future_upgrade_mask','three_step','lookahead_branches','strategy_bins','canonical_partial','quantity_children')]+[(n,C.c_double) for n in ('horizon','upgrade_bonus','expansion_balance','two_step_weight','future_weight')]+[('future_counts',C.c_int*len(BUILDINGS))]
class NativeNeighbor(C.Structure):
    _fields_=[('state',State),('actions',C.c_uint16*MAX_ACTIONS),('action_count',C.c_int32),('raw_score',C.c_double),('score',C.c_double)]
LIB.native_generate.argtypes=[C.POINTER(State),C.POINTER(NativeOptions),C.POINTER(NativeNeighbor),C.c_int]
LIB.native_generate.restype=C.c_int
assert LIB.native_options_size()==C.sizeof(NativeOptions)
assert LIB.native_neighbor_size()==C.sizeof(NativeNeighbor)

def generate_neighbors(ancestor,target,width=20,price_horizon_multiplier=16,singleton_only=False,search_width=None,queue_expansions=100,max_errand_actions=12,options=None):
    from ccsr.routes.replay import apply_errand
    from ccsr.errands.models import Errand,ErrandNeighbor
    from ccsr.errands.scoring import age_score
    if target!=1_000_000 or singleton_only:raise ValueError('Native generator currently supports only one million human mode')
    if max_errand_actions>MAX_ACTIONS:max_errand_actions=MAX_ACTIONS
    opts=NativeOptions(width,search_width or width,queue_expansions,max_errand_actions,
                       options.canonical_full_core,options.early_stop,options.all_evaluated,
                       options.diverse_queue,options.diverse_results,options.seed_reserve,
                       options.native_anchor_all,options.two_step_pool,options.upgrade_macros,options.expand_seeds,options.future_upgrade_mask,options.three_step,options.lookahead_branches,options.strategy_bins,options.canonical_partial,options.quantity_children,
                       price_horizon_multiplier or 0,options.upgrade_bonus,options.expansion_balance,options.two_step_weight,options.future_weight,
                       (C.c_int*len(BUILDINGS))(*(options.future_counts or [0]*len(BUILDINGS))))
    state=pack_state(ancestor);out=(NativeNeighbor*width)()
    count=LIB.native_generate(C.byref(state),C.byref(opts),out,width)
    result=[]
    for i in range(count):
        n=out[i];actions=unpack_actions(n.actions[:n.action_count])
        # Only candidate selection is native. Every returned neighbor is
        # executed with the unchanged Python simulator before entering a beam.
        child,purchases=apply_errand(ancestor,actions)
        expected=unpack_state(n.state,ancestor)
        for field in ('age','bank','lifetime_cookies','handmade_cookies'):
            if abs(getattr(child,field)-getattr(expected,field))>1e-7:
                raise AssertionError((field,getattr(child,field),getattr(expected,field),actions))
        if child.building_counts!=expected.building_counts or child.purchased_upgrades!=expected.purchased_upgrades:raise AssertionError(actions)
        quantities=tuple(child.building_counts[b]-ancestor.building_counts[b] for b in ancestor.building_catalog)
        errand=Errand(quantities,frozenset(child.purchased_upgrades-ancestor.purchased_upgrades),purchase_order=actions)
        result.append(ErrandNeighbor(errand,child,purchases,age_score(ancestor,child),child.age-ancestor.age))
    return tuple(result)

class NativeErrand(C.Structure):
    _fields_=[('actions',C.c_uint16*MAX_ACTIONS),('action_count',C.c_int32)]

def canonical_actions(state,actions,*,partial=True):
    function=LIB.native_canonicalize
    function.argtypes=[C.POINTER(State),C.POINTER(C.c_uint16),C.c_int,C.POINTER(C.c_uint16),C.c_int]
    function.restype=C.c_int
    packed=pack_state(state);codes=pack_actions(actions);out=(C.c_uint16*MAX_ACTIONS)()
    count=function(C.byref(packed),codes,len(codes),out,int(partial))
    if count<0:raise ValueError('Invalid actions for native normalization')
    return unpack_actions(out[:count])
# Resolve this optional entry point lazily, so older running builds stay usable.
def partition_actions(actions,*,width=2,max_size=16,expand=False):
    function=LIB.native_partition
    function.argtypes=[C.POINTER(C.c_uint16),C.c_int,C.c_int,C.c_int,C.c_int,C.POINTER(NativeErrand),C.c_int,C.POINTER(C.c_double)]
    function.restype=C.c_int
    codes=pack_actions(actions);out=(NativeErrand*256)();score=C.c_double()
    count=function(codes,len(codes),width,max_size,int(expand),out,len(out),C.byref(score))
    if count<0:raise ValueError(f'Native partition rejected input ({count})')
    return tuple(unpack_actions(out[i].actions[:out[i].action_count]) for i in range(count)),score.value
