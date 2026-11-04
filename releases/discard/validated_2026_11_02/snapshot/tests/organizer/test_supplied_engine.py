"""New supplied-engine conformance tests. Vendor source remains immutable."""
import importlib.util
import hashlib
import json
import queue
import random
import re
import sys
import unittest
from collections import deque
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('supplied_reference',ROOT/'vendor/organizer/Starter_Kit/engine.py')
engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)
from engine.numpy_eval import eval_batch
from research.discard_holdem.proofs import card,text_card,default_discard,match_cap_score
from research.discard_holdem.protocol import replay


class ScriptBot:
    def __init__(self,name,replies,trace):
        self.name=name;self.replies=deque(replies);self.messages=[];self.notices=0;self.trace=trace
    def send(self,msg):
        self.messages.append(msg);self.trace.append((self.name,'send',msg['type']));return True
    def begin(self,msg):
        self.messages.append(msg);self.trace.append((self.name,'begin',msg['type']))
    def wait_reply(self,deadline):
        self.trace.append((self.name,'wait',None));return json.dumps(self.replies.popleft()),None


def action(kind,amount=None):
    result=dict(type='action',action=kind)
    if amount is not None:result['amount']=amount
    return result


def discard(c):return dict(type='discard',card=c)


def golden(holes,board,a,b):
    trace=[];bots=(ScriptBot('A',a,trace),ScriptBot('B',b,trace))
    match=SimpleNamespace(bots=bots,wall_deadline=float('inf'))
    hand=engine.Hand(match,7,0,holes,board)
    nets=hand.play()
    assert all(not bot.replies and bot.notices==0 for bot in bots)
    return hand,nets,trace


def native_tuple(score):
    score=int(score);category=score>>20
    count=(5,4,3,3,1,5,2,2,1)[category]
    return (category,)+tuple(((score>>(4*(count-1-i)))&15)+2 for i in range(count))


class OrganizerTests(unittest.TestCase):
    def test_vendor_bytes_match_supplied_code_blocks_and_manifest(self):
        source=(ROOT/'vendor/organizer/combined_files.md')
        # Original combined Markdown is preserved in the downloadable workspace.
        manifest=json.loads((ROOT/'vendor/organizer/manifest.json').read_text())
        for name,digest in manifest['files'].items():
            self.assertEqual(hashlib.sha256((ROOT/'vendor/organizer/Starter_Kit'/name).read_bytes()).hexdigest(),digest)
        if source.exists():
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),manifest['source_sha256'])
            for m in re.finditer(r'^## `Starter_Kit/([^`]+)`\n\n(.*?)(?=\n---\n|\Z)',source.read_text(),re.M|re.S):
                name,body=m.groups()
                if name.endswith('.py'):body=re.fullmatch(r'```python\n(.*?)\n```\s*',body,re.S)[1]+'\n'
                self.assertEqual((ROOT/'vendor/organizer/Starter_Kit'/name).read_text(),body)

    def test_problem_example1_full_hand_and_replayed_ledger(self):
        hand,nets,_=golden((['Qh','Jh','4c'],['9s','9d','Kc']),['Th','9h','2c','3s','5h'],
                           [action('raise',6),action('raise',8),action('call'),discard('4c'),action('call'),action('raise',70)],
                           [action('call'),action('check'),action('raise',24),discard('Kc'),action('raise',40),action('check'),action('call')])
        self.assertEqual(nets,[140,-140]);self.assertEqual(hand.committed,[140,140])
        self.assertEqual(hand.scores[0],(5,12,11,10,9,5))
        self.assertEqual(hand.scores[1][0],3)
        for seat in (0,1):
            r=replay(hand.history_for(seat),('button','big_blind')[seat],'river')
            self.assertEqual(r.paid,[140,140]);self.assertTrue(r.closed)

    def test_problem_example2_raise_cap(self):
        hand,nets,_=golden((['As','Ad','5c'],['Kh','Ks','Qd']),['7c','Kd','2h','9s','Ac'],
                        [action('raise',6),action('raise',50),action('check'),discard('5c'),action('check'),action('check')],
                        [action('raise',18),action('call'),action('check'),discard('Qd'),action('check'),action('check')])
        self.assertEqual(nets,[50,-50])
        last_preflop=[m for m in hand.bots[1].messages if m['type']=='action_request' and m['street']=='preflop'][-1]
        self.assertEqual(last_preflop['raises_left'],0)
        self.assertNotIn('raise',last_preflop['legal_actions'])
        self.assertNotIn('min_raise',last_preflop)

    def test_problem_example3_allin_has_no_later_action_but_does_discard(self):
        hand,nets,trace=golden((['As','Ad','5c'],['Kh','Ks','Qd']),['7c','Kd','2h','9s','Ac'],
                              [action('raise',200),discard('5c')],[action('call'),discard('Qd')])
        self.assertEqual(nets,[200,-200]);self.assertEqual(len(hand.history),2)
        discard_begins=[i for i,event in enumerate(trace) if event[1:] == ('begin','discard_request')]
        discard_results=[i for i,event in enumerate(trace) if event[1:] == ('send','discard_result')]
        self.assertEqual(len(discard_begins),2);self.assertLess(max(discard_begins),min(discard_results))
        # Both requests begin BEFORE either discard wait: actual concurrent clocks.
        self.assertEqual(trace[discard_begins[0]+1][1:4],('begin','discard_request'))
        for bot in hand.bots:self.assertEqual(sum(m['type']=='action_request' for m in bot.messages),1)

    def test_problem_example4_fold_before_discard(self):
        hand,nets,_=golden((['As','Kd','7c'],['Qs','Qd','3h']),['2c','4d','5h','6s','8c'],
                           [action('call'),action('fold')],[action('check'),action('raise',4)])
        self.assertEqual(nets,[-2,2]);self.assertEqual(hand.discards,[None,None])
        result=hand.bots[0].messages[-1]
        self.assertEqual(len(result['my_hole_cards']),3);self.assertIsNone(result['opp_hole_cards']);self.assertIsNone(result['opp_discard'])

    def test_problem_example5_kickers_and_playing_board(self):
        board=['Ah','Kd','8c','5s','2h']
        self.assertGreater(engine.best_hand(['Ac','Qs'],board),engine.best_hand(['Ad','Js'],board))
        board=['Ts','Js','Qd','Kh','Ac']
        self.assertEqual(engine.best_hand(['9c','9d'],board),engine.best_hand(['4c','4h'],board))
        self.assertEqual(engine.best_hand(['9c','9d'],board),(4,14))

    def test_2000_seven_card_ranks_match_supplied_evaluator_exactly(self):
        rng=random.Random(20261102)
        rows=[rng.sample(range(52),7) for _ in range(2000)]
        native=eval_batch(np.array(rows,dtype=np.int64))
        for row,score in zip(rows,native):
            texts=list(map(text_card,row))
            self.assertEqual(native_tuple(score),engine.best_hand(texts[:2],texts[2:]),texts)

    def test_corrections_and_protocol_parsers(self):
        hole=['7d','7s','Ac']
        self.assertEqual(engine.default_discard(hole),default_discard(hole))
        self.assertEqual(engine.default_discard(hole),'7s')
        req=dict(legal_actions=['fold','call','raise'],min_raise=4,max_raise=200)
        for value in (True,3,201,4.0):
            self.assertIsNotNone(engine.parse_action(json.dumps(action('raise',value)),req)[2])
        self.assertEqual(engine.parse_action(json.dumps(action('raise',4)),req),('raise',4,None))
        self.assertIsNotNone(engine.parse_discard(json.dumps(discard('Kh')),hole)[1])

    def test_duplicate_layout_matches_problem_statement(self):
        # Verify supplied generation convention; DO NOT use it in bot decisions.
        deck=[r+s for r in engine.RANKS for s in engine.SUITS]
        random.Random('seed:0').shuffle(deck)
        seat_cards=(deck[:3],deck[3:6])
        first=engine.Hand(SimpleNamespace(bots=('A','B')),1,0,seat_cards,deck[6:11])
        second=engine.Hand(SimpleNamespace(bots=('A','B')),2,1,seat_cards,deck[6:11])
        first_a=first.dealt[first.bots.index('A')];second_a=second.dealt[second.bots.index('A')]
        self.assertNotEqual(first_a,second_a);self.assertEqual(first.board,second.board)
        self.assertEqual(first_a,second.dealt[second.bots.index('B')])

    def test_documents_current_vendor_first_five_seconds_charging(self):
        # Observation/regression record, not endorsement of the charging rule.
        # Raw send->receipt is 2s, while this supplied implementation charges 0.
        bot=object.__new__(engine.Bot)
        bot.crashed=bot.eof=False;bot.sent_at=100.;bot.startup_deadline=105.
        bot.time_left_ms=60000.;bot.per_response_ms=5000.;bot.time_used_s=0.
        bot.lines=queue.Queue();bot.lines.put((102.,'{"type":"action","action":"check"}'))
        with patch.object(engine.time,'monotonic',return_value=102.):line,error=bot.wait_reply(500.)
        self.assertIsNone(error);self.assertIsNotNone(line)
        self.assertEqual(bot.time_used_s,0.)
        self.assertEqual(102.-bot.sent_at,2.)


if __name__=='__main__':unittest.main(verbosity=2)
