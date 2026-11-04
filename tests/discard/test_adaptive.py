"""Experimental wrapper regressions, separate from frozen v1's evidence."""
import importlib.util
import itertools
import json
from pathlib import Path
import random
import runpy
import sys
import unittest
from unittest.mock import patch
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from research.discard_holdem.adaptive import AdaptiveDiscardBot,current_strength,empirical_percentile
from research.discard_holdem.partial_eval import eval_made
from research.discard_holdem.proofs import card,text_card
from research.discard_holdem.protocol import DiscardBot
spec=importlib.util.spec_from_file_location('original_discard_tests',ROOT/'tests/discard/test_protocol.py')
original=importlib.util.module_from_spec(spec);spec.loader.exec_module(original)
spec=importlib.util.spec_from_file_location('rank_reference',ROOT/'vendor/organizer/Starter_Kit/engine.py')
reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)


class AdaptiveTests(unittest.TestCase):
    def test_3000_current_ranks_match_supplied_rank5(self):
        rng=random.Random(92);lengths=(5,4,3,3,1,5,2,2,1)
        for n in (5,6,7):
            rows=[rng.sample(range(52),n) for _ in range(1000)]
            for row,value in zip(rows,eval_made(np.array(rows))):
                value=int(value);cat=value>>20;k=lengths[cat]
                decoded=(cat,)+tuple(((value>>(4*(k-1-i)))&15)+2 for i in range(k))
                expected=max(reference.rank5(list(c)) for c in itertools.combinations(map(text_card,row),5))
                self.assertEqual(decoded,expected)

    def test_percentiles_are_tie_and_permutation_invariant(self):
        v=np.array([9,2,9,5]);a=empirical_percentile(v)
        self.assertEqual(a[0],a[2]);self.assertLess(a[1],a[3]);self.assertLess(a[3],a[0])
        order=np.array([2,0,3,1]);np.testing.assert_array_equal(empirical_percentile(v[order]),a[order])

    def test_range_model_uses_only_current_board(self):
        peers=np.array([[card('As'),card('Ad')],[card('8h'),card('9h')]])
        board=tuple(map(card,['Ac','2h','3h']))
        strength=current_strength(peers,board)
        self.assertGreater(strength[0],strength[1]);self.assertEqual(strength.shape,(2,))

    def test_range_weights_positive_and_initially_uniform(self):
        b=AdaptiveDiscardBot();msg=dict(street='preflop',to_call=198,pot=202)
        strength=np.arange(20)
        np.testing.assert_array_equal(b._range_weights(strength,msg),np.ones(20))
        b.opp_n[0]=100;b.opp_raises[0]=5
        w=b._range_weights(strength,msg)
        self.assertTrue(np.all(w>0));self.assertGreater(w[-1],w[0]);self.assertAlmostEqual(float(w.mean()),1.)

    def test_base_proof_methods_are_not_overridden(self):
        for name in ('_arm','_verify_history','_safe_action','_remaining_cost','fallback','handle'):
            self.assertIs(getattr(AdaptiveDiscardBot,name),getattr(DiscardBot,name))

    def test_original_pending_and_initial_floor_regressions_with_subclass(self):
        names=('test_new_turn_certificate_settles_before_abandoning','test_cap_target_preserves_initial_certified_floor',
               'test_cap_seeking_never_spends_through_reserved_match_win','test_low_bank_still_answers_discard_and_pending_call',
               'test_reconciliation_and_notice_withdraw_certificate')
        with patch.object(original,'DiscardBot',AdaptiveDiscardBot):
            for name in names:
                with self.subTest(name=name):getattr(original.ProtocolTests(name),name)()

    def _steal_fixture(self):
        b=AdaptiveDiscardBot();original.init(b,400);original.new(b,1,'button',['As','Kd','7c'])
        b.completed=10;b.cheap_n=100;b.cheap_folds=100
        msg=original.request(b,[])
        return b,msg

    def test_steal_never_overrides_lock_pending_lowbank_or_untrusted(self):
        for attribute,value in [('locked',True),('pending',True),('score_trusted',False),('steal_used',True)]:
            b,msg=self._steal_fixture();setattr(b,attribute,value)
            reply=dict(type='action',action='call')
            self.assertEqual(b._cheap_steal(msg,reply),reply)
        b,msg=self._steal_fixture();msg['time_left_ms']=99
        reply=dict(type='action',action='call');self.assertEqual(b._cheap_steal(msg,reply),reply)

    def test_cheap_steal_is_bounded_and_accepted_history_tracks_final_reply(self):
        b,msg=self._steal_fixture()
        with patch.object(b,'_equity',return_value=(.5,b.own[:2])):reply=b.handle(msg)
        self.assertEqual(reply,dict(type='action',action='raise',amount=4))
        self.assertLessEqual(reply['amount']-msg['my_bet'],4)
        self.assertEqual(b.expected_reply[1]['action'],'raise');self.assertEqual(b.expected_reply[1]['amount'],4)
        self.assertTrue(b.steal_used)

    def test_large_raise_and_insufficient_evidence_never_probe(self):
        for n,risk in [(0,4),(7,4),(100,9)]:
            b,msg=self._steal_fixture();b.cheap_n=n;msg['min_raise']=risk
            reply=dict(type='action',action='call');self.assertEqual(b._cheap_steal(msg,reply),reply)

    def test_public_aggregate_learning_does_not_retain_revealed_cards(self):
        b=AdaptiveDiscardBot();msg=dict(history=[dict(street='preflop',actor='me',action='raise',amount=4),
                    dict(street='preflop',actor='opp',action='fold')],opp_hole_cards=['As','Ad'])
        b._learn_terminal(msg,'button')
        self.assertEqual((b.cheap_n,b.cheap_folds,b.opp_n), (1,1,[1,0]))
        self.assertNotIn('opp_hole_cards',b.__dict__)

    def test_standalone_is_the_same_adaptive_class(self):
        ns=runpy.run_path(str(ROOT/'releases/discard/experimental/bot.py'),run_name='experimental_test')
        b=ns['DiscardBot']();self.assertEqual(type(b).__name__,'AdaptiveDiscardBot')
        original.init(b,400);original.new(b,1,'button',['As','Ad','7c'])
        reply=b.handle(original.request(b,[]));self.assertIn(reply['action'],('raise','call','fold'))

if __name__=='__main__':unittest.main(verbosity=2)
