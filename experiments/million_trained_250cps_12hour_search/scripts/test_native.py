"""Focused optional native regressions; run after build_native.py."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'src'))
from ccsr.config import load_route_profile,create_initial_gamestate
from ccsr.routes import RouteAction,RoutePlan,load_route,execute_route
from ccsr.routes.replay import apply_errand
from ccsr.errands.models import Errand
from generator_variants import Options,canonical_full_core,generate_neighbors
from native_bridge import evaluate,pack_state,pack_actions,unpack_actions,canonical_actions

WORK=Path(os.environ.get('CCSR_EXPERIMENT_DIRECTORY','/tmp/ccsr-trained-12h-20260914'))
class NativeTests(unittest.TestCase):
    def setUp(self):self.state=create_initial_gamestate(load_route_profile('million-250cps'))
    def test_rejects_other_player_timing(self):
        self.state.action_delay=.2
        with self.assertRaises(ValueError):pack_state(self.state)
    def test_partial_click_order_is_preserved(self):
        actions=(RouteAction('buy','Grandma',3),RouteAction('buy','Cursor',2))
        self.assertIsNotNone(evaluate(self.state,actions,horizon=0))
        self.assertIsNone(evaluate(self.state,tuple(reversed(actions)),horizon=0))
    def test_full_core_normalization_preserves_endpoint(self):
        actions=(RouteAction('buy','Farm',1),RouteAction('buy','Cursor',10),RouteAction('upgrade','Reinforced index finger'))
        quantities=tuple(10 if n=='Cursor' else 1 if n=='Farm' else 0 for n in self.state.building_catalog)
        errand=Errand(quantities,frozenset({'Reinforced index finger'}),purchase_order=actions)
        normalized=canonical_full_core(self.state,errand)
        self.assertNotEqual(actions,normalized.purchase_order)
        a,_=apply_errand(self.state,actions);b,_=apply_errand(self.state,normalized.purchase_order)
        for field in ('age','bank','lifetime_cookies','handmade_cookies','building_counts','purchased_upgrades'):
            self.assertEqual(getattr(a,field),getattr(b,field))
    def test_lookahead_values_a_cheap_upgrade_prerequisite(self):
        options=Options(native_backend=True,canonical_full_core=True,early_stop=False,all_evaluated=True,native_anchor_all=True,two_step_pool=400,two_step_weight=1)
        neighbors=generate_neighbors(self.state,1_000_000,width=80,search_width=160,queue_expansions=500,price_horizon_multiplier=16,options=options)
        self.assertEqual(neighbors[0].errand.purchase_order,(RouteAction('buy','Cursor',1),))
    def test_new_opening_exceeds_old_horizon(self):
        state=self.state
        for a in (RouteAction('buy','Cursor',1),RouteAction('upgrade','Reinforced index finger'),RouteAction('upgrade','Carpal tunnel prevention cream')):
            state,_=apply_errand(state,(a,))
        actions=(RouteAction('buy','Cursor',10),RouteAction('upgrade','Ambidextrous'))
        self.assertIsNone(evaluate(state,actions,horizon=16))
        actual=evaluate(state,actions,horizon=0);expected,_=apply_errand(state,actions)
        self.assertEqual(actual.age,expected.age)
    def test_partial_normalization_repairs_an_invalid_append_order(self):
        state=self.state
        for _ in range(3):state,_=apply_errand(state,(RouteAction('buy','Cursor',10),))
        actions=(RouteAction('buy','Grandma',1),RouteAction('buy','Cursor',1))
        self.assertIsNone(evaluate(state,actions,horizon=0))
        normalized=canonical_actions(state,actions)
        self.assertEqual(normalized,tuple(reversed(actions)))
        native=evaluate(state,normalized,horizon=0);expected,_=apply_errand(state,normalized)
        self.assertEqual(native.age,expected.age)
    def test_partial_normalization_preserves_valid_orders_with_surplus_bank(self):
        state=self.state
        for quantity in (10,10,10,1):state,_=apply_errand(state,(RouteAction('buy','Cursor',quantity),))
        # A reachable waiting period leaves surplus bank throughout the errand.
        target_bank=state.building_price('Cursor')+state.building_price('Farm')+50
        duration=(target_bank-state.bank)/state.cps()
        state.age+=duration;state.handmade_cookies+=duration*state.hand_cps()
        state.lifetime_cookies+=target_bank-state.bank;state.bank=target_bank
        actions=(RouteAction('buy','Farm',1),RouteAction('buy','Cursor',1))
        normalized=canonical_actions(state,actions)
        self.assertNotEqual(actions,normalized)
        original,_=apply_errand(state,actions);canonical,_=apply_errand(state,normalized)
        self.assertGreater(canonical.bank,0)
        for field in ('age','bank','lifetime_cookies','handmade_cookies','building_counts','purchased_upgrades'):
            self.assertEqual(getattr(original,field),getattr(canonical,field))
    def test_complete_search_output_replays(self):
        base=load_route(ROOT/'routes/million-250cps/generated_beam.route')
        with tempfile.TemporaryDirectory() as directory:
            seed=Path(directory)/'seed.txt'
            seed.write_text(str(len(base.errands))+'\n'+'\n'.join(str(len(e))+' '+' '.join(str(c) for c in pack_actions(e)) for e in base.errands)+'\n')
            completed=subprocess.run([str(WORK/'native_beam'),'--seed',str(seed),'--seconds','.05','--workers','2','--width','20','--inner','40','--pops','100','--horizon','0'],check=True,capture_output=True,text=True)
            row=json.loads(completed.stdout.splitlines()[-1])
            from dataclasses import replace
            plan=replace(base,errands=tuple(unpack_actions(e) for e in row['route']))
            self.assertAlmostEqual(execute_route(plan).final_gamestate.age,row['finish'],places=7)
    def test_malformed_native_seed_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'bad.txt';path.write_text('1\n-1\n')
            result=subprocess.run([str(WORK/'native_anneal'),str(path),'0','1'],capture_output=True)
            self.assertEqual(result.returncode,3)
    def test_routes_survive_memory_compaction(self):
        from dataclasses import replace
        base=load_route(ROOT/'routes/million-250cps/generated_beam.route')
        with tempfile.TemporaryDirectory() as directory:
            seed=Path(directory)/'seed.txt'
            seed.write_text(str(len(base.errands))+'\n'+'\n'.join(str(len(e))+' '+' '.join(str(c) for c in pack_actions(e)) for e in base.errands)+'\n')
            command=[str(WORK/'native_beam'),'--seed',str(seed),'--seconds','3',
                     '--workers','2','--width','30','--inner','60','--pops','50',
                     '--horizon','0','--order','1','--stage-balance','1',
                     '--compact','1','--nodes','500','--heap','50','--harvest','8']
            output=subprocess.run(command,check=True,capture_output=True,text=True)
            rows=[json.loads(line) for line in output.stdout.splitlines()]
            self.assertGreater(rows[-1]['compactions'],0)
            for row in rows:
                if 'route' not in row:continue
                plan=replace(base,errands=tuple(unpack_actions(e) for e in row['route']))
                self.assertAlmostEqual(execute_route(plan).final_gamestate.age,row['finish'],places=7)

    def test_target_rollouts_and_hand_frontier_survive_compaction(self):
        from dataclasses import replace
        base=load_route(ROOT/'routes/million-250cps/generated_beam.route')
        with tempfile.TemporaryDirectory() as directory:
            seed=Path(directory)/'seed.txt'
            seed.write_text(str(len(base.errands))+'\n'+'\n'.join(str(len(e))+' '+' '.join(str(c) for c in pack_actions(e)) for e in base.errands)+'\n')
            for targets in (1,2):
                command=[str(WORK/'native_beam'),'--seed',str(seed),'--seconds','2',
                         '--workers','2','--persistent-workers','1','--width','30','--inner','60','--pops','50',
                         '--horizon','0','--order','1','--stage-balance','1','--hand-dominance','1',
                         '--target-rollout',str(targets),'--canonical-partials','1',
                         '--retain-closed','1',
                         '--compact','1','--nodes','500','--heap','50','--harvest','8']
                output=subprocess.run(command,check=True,capture_output=True,text=True)
                rows=[json.loads(line) for line in output.stdout.splitlines()]
                self.assertGreater(rows[-1]['compactions'],0)
                for row in rows:
                    if 'route' not in row:continue
                    plan=replace(base,errands=tuple(unpack_actions(e) for e in row['route']))
                    self.assertAlmostEqual(execute_route(plan).final_gamestate.age,row['finish'],places=7)

if __name__=='__main__':unittest.main()
