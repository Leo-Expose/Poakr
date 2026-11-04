"""Own exact audit/information-contract tests, not OpenSpiel execution tests."""
from dataclasses import replace
from fractions import Fraction
import hashlib
from pathlib import Path
import sys
import unittest
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from research.openspiel_bridge.objectives import audit_objectives,certify_matrix
from research.openspiel_bridge.discard_information import DiscardCommitState
from research.discard_holdem.proofs import card
from tools.openspiel.audit_guarantees import royal_witness


def fixture():
    return DiscardCommitState(holes=(('As','Kd','7c'),('Qh','Jh','2d')),board=('Th','9h','4c','3s','5h'))


class ObjectiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.audit=audit_objectives()

    def test_expected_and_adversarial_values_have_exact_zero_gap(self):
        expected=dict(uniform_chance_chips='-1/18',uniform_chance_strict_win='1/2',uniform_chance_nonloss='1/2',
                      adversarial_deal_chips='-1',adversarial_deal_strict_win='0',adversarial_deal_nonloss='0')
        for name,value in expected.items():
            result=self.audit['objectives'][name]
            self.assertEqual(result['value'],value);self.assertEqual(result['exact_gap'],'0')
            self.assertEqual(sum(map(Fraction,result['row_policy'].values())),1)
            self.assertEqual(sum(map(Fraction,result['column_policy'].values())),1)

    def test_payoff_objective_and_chance_scope_are_not_conflated(self):
        self.assertEqual(self.audit['complete_policy_deal_outcomes'],24576)
        self.assertEqual(self.audit['objectives']['uniform_chance_chips']['columns'],64)
        self.assertEqual(self.audit['objectives']['adversarial_deal_chips']['columns'],384)
        self.assertNotEqual(self.audit['objectives']['uniform_chance_chips']['row_policy'],self.audit['objectives']['uniform_chance_strict_win']['row_policy'])

    def test_exact_matrix_known_games(self):
        self.assertEqual(certify_matrix([[1,-1],[-1,1]],1)['value'],'0')
        self.assertEqual(certify_matrix([[2,2],[0,0]],3)['value'],'2/3')

    def test_certificate_rejects_float_or_invalid_inputs(self):
        for a,d in [([[.5]],1),([[True]],1),([[1]],0),([[1]],True),([],1),([[2**63]],1)]:
            with self.assertRaises(ValueError):certify_matrix(a,d)

    def test_actual_variant_shared_royal_all_903_pairs(self):
        witness=royal_witness()
        self.assertEqual(witness['physical_retained_peer_pairs'],903)
        self.assertTrue(witness['all_pairs_tie']);self.assertTrue(witness['supplied_engine_agrees'])
        self.assertEqual(witness['upper_bound_for_hero_hand_net'],0)

    def test_champion_unchanged_and_no_openspiel_runtime_import(self):
        p=ROOT/'releases/discard/v1/bot.py';data=p.read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(),'2de972289c37024c9283d8c29b273c694a2f229d67309ac347cfb7cfff7bb907')
        self.assertNotIn(b'import pyspiel',data);self.assertNotIn(b'open_spiel',data)


class InformationTests(unittest.TestCase):
    def test_sealed_other_discard_cannot_change_second_player_information(self):
        s=fixture();key=s.information_key(1);legal=s.legal_discards(1)
        for a in s.legal_discards(0):
            t=s.commit(0,a)
            self.assertEqual(t.information_key(1),key);self.assertEqual(t.legal_discards(1),legal)
            self.assertIsNone(t.exposed_discards())

    def test_reverse_commit_order_also_hides_choice(self):
        s=fixture()
        for a in s.legal_discards(1):self.assertEqual(s.commit(1,a).information_key(0),s.information_key(0))

    def test_other_holes_and_future_board_cannot_change_information(self):
        s=fixture();t=replace(s,holes=(s.holes[0],('Qs','Jd','2c')),board=s.board[:3]+('8s','6s'))
        self.assertEqual(s.information_key(0),t.information_key(0))

    def test_current_own_public_and_match_facts_remain_distinguishable(self):
        s=fixture();key=s.information_key(0)
        for t in (replace(s,holes=(tuple(reversed(s.holes[0])),s.holes[1])),replace(s,board=('Th','9h','5c','3s','6h')),
                  replace(s,paid=(24,24)),replace(s,match_net=(5,-5)),replace(s,match_cap=1000),replace(s,hand_id=2)):
            self.assertNotEqual(t.information_key(0),key)

    def test_all_nine_joint_choices_expose_only_after_both_and_commute(self):
        s=fixture();count=0
        for a in s.legal_discards(0):
            for b in s.legal_discards(1):
                x=s.commit(0,a).commit(1,b);y=s.commit(1,b).commit(0,a)
                self.assertEqual(x,y);self.assertIsNotNone(x.exposed_discards());count+=1
                self.assertEqual(x.legal_discards(0),());self.assertEqual(x.legal_discards(1),())
        self.assertEqual(count,9)

    def test_cannot_react_twice_or_discard_a_peer_card(self):
        s=fixture().commit(0,card('As'))
        with self.assertRaises(ValueError):s.information_key(0)
        with self.assertRaises(ValueError):s.commit(0,card('Kd'))
        with self.assertRaises(ValueError):fixture().commit(1,card('As'))
        with self.assertRaises(ValueError):fixture().commit(0,True)

    def test_reject_collisions_bad_money_and_boolean_player_identifiers(self):
        s=fixture()
        for kwargs in (dict(holes=(s.holes[0],s.holes[0])),dict(paid=(2,3)),dict(button=True),dict(match_net=(0,1)),dict(match_cap=True)):
            with self.assertRaises(ValueError):replace(s,**kwargs)
        with self.assertRaises(ValueError):s.legal_discards(True)

    def test_normalizes_mutable_containers_to_immutable_tuples(self):
        holes=[list(x) for x in fixture().holes];board=list(fixture().board)
        s=DiscardCommitState(holes=holes,board=board);key=s.information_key(0)
        holes[0][0]='2c';board[0]='3c'
        self.assertEqual(s.information_key(0),key)

if __name__=='__main__':unittest.main(verbosity=2)
