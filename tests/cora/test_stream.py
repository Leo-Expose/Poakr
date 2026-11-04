"""EXAMPLE adapter tests; run after frozen timing experiments."""
import sys,unittest,json,copy,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from research.stream_adapter import CoraAdapter
from research.agent import load_preflop
from runtime.bot import ValidationError

class StreamTests(unittest.TestCase):
    def make(self,contract=False):
        a=CoraAdapter(load_preflop(ROOT/'data/preflop/preflop.json'))
        a.handle(dict(type='start_match',match_id='m',starting_stack=200,sb=1,bb=2,hands_total=400,timebank_s=60,
                      raw_net_abandonment_contract=contract))
        d=dict(type='decision',match_id='m',request_id='r0',hand_id='h0',hole=['Ac','Ad'],board=[],pot=3,to_call=1,
               my_stack=199,opp_stack=198,hands_left=400,banked_net=0,seat=0,history=[],legal=[dict(kind='fold'),dict(kind='call')])
        return a,d
    def test_request_replay_and_conflict(self):
        a,d=self.make();reply=a.handle(d);n=a.agent.requests
        self.assertEqual(a.handle(dict(d,time_left_s=59)),reply);self.assertEqual(a.agent.requests,n)
        bad=dict(d,pot=4)
        with self.assertRaises(ValidationError):a.handle(bad)
        self.assertIsNone(a.fallback(bad))
    def test_money_and_turn_checked_before_planning(self):
        for changes in (dict(opp_stack=197),dict(seat=1),dict(hands_left=401),dict(hands_left=0)):
            a,d=self.make();d.update(changes)
            with self.assertRaises(ValidationError):a.handle(d)
            self.assertEqual(a.agent.requests,0)
    def test_private_fields_rejected_at_every_consumed_level(self):
        for where in ('root','history','action','legal'):
            a,d=self.make()
            if where=='root':d['opponent_hole']=['Ks','Kh']
            elif where=='history':d['history']=[dict(street=0,actor=0,action=dict(kind='call'),opponent_hole=['Ks','Kh'])]
            elif where=='action':d['history']=[dict(street=0,actor=0,action=dict(kind='call',opponent_hole=['Ks','Kh']))]
            else:d['legal'][0]['opponent_hole']=['Ks','Kh']
            with self.assertRaises(ValidationError):a.handle(d)
            self.assertEqual(a.agent.requests,0)
    def test_completed_hand_replay_is_idempotent(self):
        a,d=self.make();self.assertEqual(a.handle(d)['action'],dict(kind='call'))
        history=[dict(street=0,actor=0,action=dict(kind='call')),dict(street=0,actor=1,action=dict(kind='check'))]
        for s in (1,2,3):
            history.extend([dict(street=s,actor=p,action=dict(kind='check')) for p in (1,0)])
        end=dict(type='hand_end',match_id='m',hand_id='h0',seat=0,board=['Ts','Js','Qs','Ks','As'],outcome=0,history=history)
        a.handle(end);before=a.agent.models.weights.copy();hands=a.agent.models.hands
        a.handle(dict(end,time_left_s=58));self.assertEqual(a.agent.models.hands,hands)
        self.assertTrue((before==a.agent.models.weights).all())
        with self.assertRaises(ValidationError):a.handle(dict(end,outcome=1))
    def test_lock_requires_explicit_contract(self):
        for contract in (False,True):
            a,d=self.make(contract);d.update(banked_net=500,hands_left=200)
            reply=a.handle(d)
            self.assertEqual(a.agent.locked,contract)
            if contract:self.assertEqual(reply['action'],dict(kind='fold'))
    def test_new_match_does_not_inherit_private_or_policy_state(self):
        a,d=self.make();a.handle(d);old=a.agent
        a.handle(dict(type='end_match',match_id='m'))
        a.handle(dict(type='start_match',match_id='n',starting_stack=200,sb=1,bb=2,hands_total=400,timebank_s=60))
        self.assertIsNot(a.agent,old);self.assertIsNone(a.agent.hole);self.assertFalse(a.agent.locked)
        self.assertEqual(len(a.agent.session.duplicate.history),0)
    def test_premature_board_and_extra_closed_round_actions_rejected(self):
        a,d=self.make();d.update(board=['2c','7d','9s'],seat=1,to_call=0)
        with self.assertRaises(ValidationError):a.handle(d)
        a,d=self.make()
        d['history']=[dict(street=0,actor=p,action=dict(kind=k)) for p,k in [(0,'call'),(1,'check'),(0,'check')]]
        with self.assertRaises(ValidationError):a.handle(d)
    def test_same_hand_hole_or_unapplied_response_rejected(self):
        for change in (dict(hole=['Kc','Kd']),dict()):
            a,d=self.make();a.handle(d);second=copy.deepcopy(d);second['request_id']='r1';second.update(change)
            with self.assertRaises(ValidationError):a.handle(second)
    def test_standalone_actual_stdio(self):
        p=subprocess.run([sys.executable,'-B',str(ROOT/'releases/cora/v1/cora_bot.py')],input=(ROOT/'fixtures/cora/example_session.jsonl').read_text(),
                         text=True,capture_output=True,timeout=5)
        self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(p.stderr,'')
        lines=p.stdout.splitlines();self.assertEqual(len(lines),1)
        response=json.loads(lines[0]);self.assertEqual(response['request_id'],'r0')
        self.assertIn(response['action'],[dict(kind='fold'),dict(kind='call'),dict(kind='bet',pay=4)])

if __name__=='__main__':unittest.main(verbosity=2)
