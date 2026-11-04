import copy
import itertools
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from research.discard_holdem.proofs import (
    card,text_card,parse_cards,default_discard,future_blinds,quads_turn,river_floor,river_geometry,match_cap_score,
)
from research.discard_holdem.protocol import DiscardBot,replay
from tools.discard.local_runner import LocalMatch,Client,Opponent


def init(bot,hands=4):
    return bot.handle(dict(type='init',protocol_version='1.0',total_hands=hands,starting_stack=200,
                          small_blind=1,big_blind=2,time_bank_ms=60000,per_response_ms=5000))


def new(bot,hid,seat,holes):
    return bot.handle(dict(type='new_hand',hand_id=hid,seat=seat,hole_cards=holes,stack=200,opp_stack=200))


def request(bot,history,street='preflop',board=None):
    r=replay(history,bot.seat,street);tc=max(0,r.bets[1]-r.bets[0])
    msg=dict(type='action_request',hand_id=bot.hand_id,street=street,board=board or [],pot=r.pot,
             my_bet=r.bets[0],opp_bet=r.bets[1],to_call=tc,my_stack=200-r.paid[0],opp_stack=200-r.paid[1],
             history=copy.deepcopy(history),legal_actions=['fold','call'] if tc else ['check'],
             raises_left=4-r.raises,time_left_ms=60000)
    if r.raises<4 and max(r.paid)<200:
        maximum=min(r.bets[0]+200-r.paid[0],r.bets[1]+200-r.paid[1])
        msg['legal_actions'].append('raise');msg.update(min_raise=min(maximum,r.bets[1]+max(2,r.delta)),max_raise=maximum)
    return msg


def comeback(spend=False,hands=4):
    b=DiscardBot(spend_to_cap=spend);init(b,hands)
    new(b,1,'button',['Ah','Ac','Kd'])
    past=[dict(street='preflop',actor='me',action='raise',amount=60),
          dict(street='preflop',actor='opp',action='raise',amount=200),
          dict(street='preflop',actor='me',action='fold')]
    b.handle(dict(type='hand_result',hand_id=1,result='fold',net=-60,board=[],
                  my_hole_cards=['Ah','Ac','Kd'],opp_hole_cards=None,opp_discard=None,history=past))
    new(b,2,'big_blind',['9c','9d','4c'])
    hist=[dict(street='preflop',actor='opp',action='raise',amount=50),
          dict(street='preflop',actor='me',action='call',amount=50),
          dict(street='flop',actor='me',action='check'),dict(street='flop',actor='opp',action='check')]
    discard=b.handle(dict(type='discard_request',hand_id=2,hole_cards=['9c','9d','4c'],board=['9h','9s','2c'],
                          pot=100,my_stack=150,opp_stack=150,time_left_ms=60000))
    assert discard==dict(type='discard',card='4c')
    b.handle(dict(type='discard_result',hand_id=2,my_discard='4c',opp_discard='Ah',hole_cards=['9c','9d']))
    hist.extend([dict(street='turn',actor='me',action='check'),dict(street='turn',actor='opp',action='raise',amount=20)])
    return b,hist


class ProofTests(unittest.TestCase):
    def test_card_mapping_and_default_tie_order(self):
        self.assertEqual([text_card(card(x)) for x in ['As','Td','2c']],['As','Td','2c'])
        self.assertEqual(default_discard(['2c','2s','2h']),'2s')
        self.assertEqual(default_discard(['Ah','2c','2d']),'2d')
        for value in ('10c','as','A♠','ZZ',True):
            with self.assertRaises(ValueError):card(value)
        with self.assertRaises(ValueError):parse_cards(['As','As'],(2,))

    def test_exact_alternating_blind_suffix(self):
        for seat in ('button','big_blind'):
            for n in range(1001):
                expected=sum((2,1)[i%2] if seat=='button' else (1,2)[i%2] for i in range(n))
                self.assertEqual(future_blinds(seat,n),expected)
        with self.assertRaises(ValueError):future_blinds('button',True)

    def test_actual_cap_is_per_match_not_per_hand(self):
        self.assertEqual(match_cap_score([(600,400,400)]),1)
        self.assertEqual(match_cap_score([(600,400,400),(-550,400,400)]),0)
        # Two hands +500,-450: official match net +50, not clipped hand sum 0.
        self.assertEqual(match_cap_score([(50,2,400)]),25)

    def _all_worlds(self,hero,board,dead):
        from runtime.bot import Evaluator,Rules
        deck=[c for c in range(52) if c not in hero+board+dead]
        worlds=np.array([(a,b,r) for a,b in itertools.combinations(deck,2) for r in deck if r not in (a,b)],dtype=np.int64)
        self.assertEqual(len(worlds),39732)
        boards=np.column_stack((np.tile(board,(len(worlds),1)),worlds[:,2]))
        own=np.column_stack((np.tile(hero,(len(worlds),1)),boards))
        peer=np.column_stack((worlds[:,:2],boards))
        evaluator=Evaluator(Rules())
        self.assertTrue(np.all(evaluator.score(own)>evaluator.score(peer)))

    def test_dead_card_blocks_nonrainbow_straight_flush_all_39732_worlds(self):
        hero=tuple(map(card,['9c','9d']));board=tuple(map(card,['9h','9s','2c','3c']));dead=tuple(map(card,['4c','Ah']))
        self.assertTrue(quads_turn(hero,board,dead));self._all_worlds(hero,board,dead)
        self.assertFalse(quads_turn(hero,board,tuple(map(card,['Ad','Ah']))))

    def test_dead_ace_blocks_higher_quads_all_39732_worlds(self):
        hero=tuple(map(card,['9c','9d']));board=tuple(map(card,['9h','9s','Ac','3d']));dead=tuple(map(card,['4c','Ah']))
        self.assertTrue(quads_turn(hero,board,dead));self._all_worlds(hero,board,dead)
        self.assertFalse(quads_turn(hero,board,tuple(map(card,['2c','4c']))))

    def test_river_uses_both_discards_all_physical_peers(self):
        hero=tuple(map(card,['As','Ks']));board=tuple(map(card,['Ts','Js','Qs','2c','3d']));dead=tuple(map(card,['4c','Ah']))
        self.assertEqual(river_floor(hero,board,dead,70),(70,903))
        relation,n,q=river_geometry(hero,board,dead)
        self.assertEqual((relation,n,q),(1,903,1.0))

    def test_three_hole_quads_cannot_survive_mandatory_discard(self):
        with self.assertRaises(ValueError):quads_turn((28,29,30),(31,0,5,10),(12,16))

    def test_margin_budget_induction_all_small_losses(self):
        # At each decision a voluntary commitment <=B-F-1 leaves at least +1
        # after its worst loss and all future forced posts, independent of cards.
        for bank,future in itertools.product(range(1,30),range(12)):
            budget=bank-future-1
            for paid in range(max(0,budget)+1):
                if budget<0:continue
                self.assertGreaterEqual(bank-paid-future,1)


class ProtocolTests(unittest.TestCase):
    def test_unknown_types_and_fields_are_ignored(self):
        a=DiscardBot();b=DiscardBot();init(a);init(b)
        self.assertIsNone(a.handle(dict(type='future_message',arbitrary=['unknown'])))
        for bot in (a,b):new(bot,1,'button',['As','Kd','7c'])
        req=request(a,[]);changed=copy.deepcopy(req)
        changed.update(future_flag=True,opponent_hole_cards=['2s','2h','2d'],unrevealed_board=['Ac']*5)
        self.assertEqual(a.handle(req),b.handle(changed))

    def test_call_and_raise_amounts_are_street_totals(self):
        hist=[dict(street='preflop',actor='me',action='raise',amount=6),
              dict(street='preflop',actor='opp',action='call',amount=6),
              dict(street='flop',actor='opp',action='raise',amount=6),
              dict(street='flop',actor='me',action='call',amount=6)]
        r=replay(hist,'button','turn')
        self.assertEqual(r.paid,[12,12]);self.assertEqual(r.bets,[0,0])
        bad=copy.deepcopy(hist);bad[1]['amount']=4
        with self.assertRaises(ValueError):replay(bad,'button','turn')

    def test_big_blind_has_option_after_limp_and_raise_limit(self):
        r=replay([dict(street='preflop',actor='me',action='call',amount=2)],'button','preflop')
        self.assertFalse(r.closed);self.assertEqual(r.actor,'opp');self.assertEqual(r.raises,1)
        hist=[dict(street='preflop',actor='me',action='raise',amount=4),
              dict(street='preflop',actor='opp',action='raise',amount=6),
              dict(street='preflop',actor='me',action='raise',amount=8)]
        self.assertEqual(replay(hist,'button','preflop').raises,4)
        hist.append(dict(street='preflop',actor='opp',action='raise',amount=10))
        with self.assertRaises(ValueError):replay(hist,'button','preflop')

    def test_coupled_discard_commits_one_pair_not_max_per_runout(self):
        b=DiscardBot(samples=4);b.original=b.own=(0,4,8);b.dead=()
        calls=[]
        def fake(rows):
            calls.append(len(rows))
            if len(calls)==1:return np.zeros(12,dtype=int)
            return np.array([1,-1,1,-1,-1,1,-1,1,0,0,0,0])
        with patch('research.discard_holdem.protocol.eval_batch',side_effect=fake):
            q,keep=b._equity((12,16,20))
        self.assertEqual(q,.5)  # illegal own per-world maximum would return 1
        self.assertIn(keep,list(itertools.combinations(b.own,2)))

    def test_new_turn_certificate_settles_before_abandoning(self):
        b,hist=comeback()
        reply=b.handle(request(b,hist,'turn',['9h','9s','2c','3c']))
        self.assertEqual(reply,dict(type='action',action='call'))
        self.assertTrue(b.pending);self.assertFalse(b.locked)
        self.assertEqual(b.certificate['lower'],7)
        hist.append(dict(street='turn',actor='me',action='call',amount=20))
        self.assertEqual(b.handle(request(b,hist,'river',['9h','9s','2c','3c','2h']))['action'],'check')
        hist.extend([dict(street='river',actor='me',action='check'),dict(street='river',actor='opp',action='check')])
        b.handle(dict(type='hand_result',hand_id=2,result='showdown',net=70,board=['9h','9s','2c','3c','2h'],
                      my_hole_cards=['9c','9d'],opp_hole_cards=['Ac','Kd'],opp_discard='Ah',history=hist))
        self.assertEqual(b.score,10);self.assertTrue(b.locked);self.assertFalse(b.pending)

    def test_cap_target_preserves_initial_certified_floor(self):
        b,hist=comeback(True)
        b.handle(request(b,hist,'turn',['9h','9s','2c','3c']))
        self.assertEqual(b.certificate['abandonment_lower'],7)
        self.assertEqual(b.certificate['lower'],7)

    def test_cap_seeking_never_spends_through_reserved_match_win(self):
        b,hist=comeback(True,hands=6)
        b.handle(request(b,hist,'turn',['9h','9s','2c','3c']))
        hist.append(dict(street='turn',actor='me',action='call',amount=20))
        b.handle(request(b,hist,'river',['9h','9s','2c','3c','2h']))
        hist.extend([dict(street='river',actor='me',action='check'),dict(street='river',actor='opp',action='check')])
        b.handle(dict(type='hand_result',hand_id=2,result='showdown',net=70,board=['9h','9s','2c','3c','2h'],
                      my_hole_cards=['9c','9d'],opp_hole_cards=['Ac','Kd'],opp_discard='Ah',history=hist))
        self.assertEqual(b.score,10)
        self.assertEqual(b.reserve,4)
        new(b,3,'button',['2c','3d','4h'])
        self.assertEqual(b.handle(request(b,[]))['action'],'fold')
        b.handle(dict(type='hand_result',hand_id=3,result='fold',net=-1,board=[],my_hole_cards=['2c','3d','4h'],
                      opp_hole_cards=None,opp_discard=None,history=[dict(street='preflop',actor='me',action='fold')]))
        new(b,4,'big_blind',['2c','3d','4h'])
        b.handle(dict(type='hand_result',hand_id=4,result='fold',net=1,board=[],my_hole_cards=['2c','3d','4h'],
                      opp_hole_cards=None,opp_discard=None,history=[dict(street='preflop',actor='opp',action='fold')]))
        new(b,5,'button',['As','Ad','Ac'])
        with patch.object(b,'_equity',return_value=(1.,(card('As'),card('Ad')))):
            reply=b.handle(request(b,[]))
        self.assertEqual(reply['action'],'raise')
        self.assertLessEqual(reply['amount'],4)  # B10 - next BB2 - original reserve4
        hist=[dict(street='preflop',actor='me',action='raise',amount=reply['amount']),
              dict(street='preflop',actor='opp',action='raise',amount=200)]
        self.assertEqual(b.handle(request(b,hist))['action'],'fold')
        hist.append(dict(street='preflop',actor='me',action='fold'))
        b.handle(dict(type='hand_result',hand_id=5,result='fold',net=-reply['amount'],board=[],
                      my_hole_cards=['As','Ad','Ac'],opp_hole_cards=None,opp_discard=None,history=hist))
        new(b,6,'big_blind',['2c','3d','4h'])
        hist=[dict(street='preflop',actor='opp',action='raise',amount=200)]
        self.assertEqual(b.handle(request(b,hist))['action'],'fold')
        hist.append(dict(street='preflop',actor='me',action='fold'))
        b.handle(dict(type='hand_result',hand_id=6,result='fold',net=-2,board=[],
                      my_hole_cards=['2c','3d','4h'],opp_hole_cards=None,opp_discard=None,history=hist))
        self.assertGreaterEqual(b.score,4);self.assertTrue(b.score_trusted)

    def test_low_bank_still_answers_discard_and_pending_call(self):
        b,hist=comeback();req=request(b,hist,'turn',['9h','9s','2c','3c']);req['time_left_ms']=1
        self.assertEqual(b.handle(req)['action'],'call')
        x=DiscardBot();init(x);new(x,1,'button',['2c','2s','Ah'])
        reply=x.handle(dict(type='discard_request',hand_id=1,hole_cards=['2c','2s','Ah'],board=['3d','4d','5h'],pot=4,
                            my_stack=198,opp_stack=198,time_left_ms=1))
        self.assertEqual(reply,dict(type='discard',card='2s'))

    def test_reconciliation_and_notice_withdraw_certificate(self):
        b=DiscardBot();init(b);new(b,1,'button',['As','Kd','7c'])
        req=request(b,[]);b.handle(req)
        with self.assertRaises(ValueError):b.handle(req)
        b.handle(dict(type='notice',code='illegal_action',applied='fold'))
        self.assertFalse(b.score_trusted)
        self.assertIsNone(b.expected_reply)

    def test_wrong_price_or_dead_card_collision_rejected(self):
        b,hist=comeback();req=request(b,hist,'turn',['9h','9s','2c','3c']);req['to_call']=1
        with self.assertRaises(ValueError):b.handle(req)
        with self.assertRaises(ValueError):b.handle(dict(type='discard_result',hand_id=2,my_discard='4c',opp_discard='9c',hole_cards=['9c','9d']))

    def test_local_runner_both_duplicate_layouts_and_aggression(self):
        for layout in ('fixed_seat_cards','swapped_seat_cards'):
            for name in ('CallingStation','Aggressor','Selective','Shove'):
                a=Client(DiscardBot());m=LocalMatch(a,Client(Opponent(name)),hands=12,seed=190000,layout=layout)
                result=m.run()
                self.assertEqual(a.bot.errors,0);self.assertTrue(a.bot.score_trusted)
                self.assertEqual(result['invalid_responses'],0);self.assertEqual(a.bot.score,result['net'])

    def test_allin_preflop_still_requires_simultaneous_flop_discard(self):
        class ShoveCall(Opponent):
            def handle(self,msg):
                if msg['type']=='action_request':
                    if 'raise' in msg['legal_actions']:return dict(type='action',action='raise',amount=msg['max_raise'])
                    return dict(type='action',action='call' if msg['to_call'] else 'check')
                return super().handle(msg)
        result=LocalMatch(Client(ShoveCall('CallingStation')),Client(ShoveCall('CallingStation')),hands=4,seed=45).run()
        self.assertEqual(result['allin_discard_replies'],8)
        self.assertEqual(result['discard_replies'],8)

    def test_single_file_actual_stdio(self):
        transcript=[dict(type='init',protocol_version='1.0',total_hands=400,starting_stack=200,small_blind=1,big_blind=2,
                         time_bank_ms=60000,per_response_ms=5000),
                    dict(type='new_hand',hand_id=1,seat='button',hole_cards=['As','Kd','7c'],stack=200,opp_stack=200),
                    dict(type='future_kind'),
                    dict(type='action_request',hand_id=1,street='preflop',board=[],pot=3,my_bet=1,opp_bet=2,to_call=1,
                         my_stack=199,opp_stack=198,legal_actions=['fold','call','raise'],min_raise=4,max_raise=200,
                         raises_left=3,history=[],time_left_ms=60000),dict(type='match_end',reason='complete')]
        p=subprocess.run([sys.executable,'-B',str(ROOT/'releases/discard/current/bot.py')],
                         input='\n'.join(map(json.dumps,transcript))+'\n',capture_output=True,text=True,timeout=5)
        self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(p.stderr,'')
        self.assertEqual(len(p.stdout.splitlines()),1)
        self.assertIn(json.loads(p.stdout)['action'],('fold','call','raise'))


if __name__=='__main__':unittest.main(verbosity=2)
