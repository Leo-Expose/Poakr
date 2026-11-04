import sys,unittest,itertools
from fractions import Fraction
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from research.guarantee_lab.certificates import BoundSchedule,Contract
from research.guarantee_lab.kuhn import payoff,solve

VERIFIED=Contract(True,True,True,True,True)
class GuaranteeTests(unittest.TestCase):
    def test_variable_posts_and_strict_boundary(self):
        s=BoundSchedule([1,3,5],VERIFIED)
        self.assertEqual(s.certify(12,4,0).lower_score,0)
        self.assertFalse(s.certify(12,4,0).strict_success)
        self.assertEqual(s.certify('12.01',4,0).lower_score,Fraction(1,100))
        self.assertTrue(s.certify('12.01',4,0).strict_success)
        self.assertEqual(s.certify(12,4,2).lower_score,8)
    def test_capped_score_requires_a_different_scoreboard(self):
        raw=BoundSchedule([2,2,2],VERIFIED)
        capped=BoundSchedule([2,2,2],VERIFIED,hand_cap=1)
        self.assertFalse(raw.certify(4,200,0).strict_success)
        self.assertEqual(capped.certify(4,200,0).lower_score,1)
        self.assertTrue(capped.certify(4,200,0).strict_success)
    def test_all_small_adversarial_returns_obey_bound(self):
        posts=[1,2,3]
        for cap in (None,1,2):
            schedule=BoundSchedule(posts,VERIFIED,cap)
            clip=lambda x:x if cap is None else max(-cap,min(cap,x))
            for paid in range(5):
                bound=schedule.certify(5,paid,0).lower_score
                for profits in itertools.product(range(-paid,3),range(-2,3),range(-3,3)):
                    score=5+sum(clip(x) for x in profits)
                    self.assertGreaterEqual(score,bound)
    def test_unknown_premises_rejected(self):
        for i in range(5):
            flags=[True]*5;flags[i]=False
            with self.assertRaises(ValueError):BoundSchedule([1,2],Contract(*flags))
    def test_invalid_amounts_indices_and_caps(self):
        for posts in ([],[-1],[True],[float('inf')]):
            with self.assertRaises(ValueError):BoundSchedule(posts,VERIFIED)
        for cap in (0,-1,True):
            with self.assertRaises(ValueError):BoundSchedule([1],VERIFIED,cap)
        s=BoundSchedule([1],VERIFIED)
        for idx in (-1,1,True):
            with self.assertRaises(ValueError):s.certify(1,0,idx)
    def test_toy_terminal_paths(self):
        self.assertEqual(payoff(0,56,0,2),-1)
        self.assertEqual(payoff(1,56,0,2),-2)
        self.assertEqual(payoff(4,0,2,0),1)
    def test_safe_tie_river_recovers_paid_contribution(self):
        from research.kernels import RiverKernel
        from research.guarantee_lab.river_credit import prove_river_credit,RiverContract
        proof=prove_river_credit(RiverKernel([35,39,43,47,51]),[0,1],70,RiverContract(*([True]*7)))
        self.assertEqual(proof.minimum_current_net,0);self.assertFalse(proof.strictly_beats_every_peer)
        schedule=BoundSchedule([2,3,5],VERIFIED)
        self.assertFalse(schedule.certify(10,50,0).strict_success)
        self.assertEqual(schedule.certify_river_settlement(10,proof,0).lower_score,2)
        self.assertTrue(schedule.certify_river_settlement(10,proof,0).strict_success)
    def test_unique_nuts_certifies_a_comeback(self):
        from research.kernels import RiverKernel
        from research.guarantee_lab.river_credit import prove_river_credit,RiverContract
        proof=prove_river_credit(RiverKernel([35,39,43,0,5]),[47,51],70,RiverContract(*([True]*7)))
        self.assertTrue(proof.strictly_beats_every_peer);self.assertEqual(proof.legal_peer_hands,990)
        schedule=BoundSchedule([2,3,5],VERIFIED)
        self.assertEqual(schedule.certify_river_settlement(-60,proof,0).lower_score,2)
        capped=BoundSchedule([2,3,5],VERIFIED,hand_cap=2)
        self.assertEqual(capped.certify_river_settlement(0,proof,0).lower_score,-2)
    def test_losing_physical_peer_and_unknown_premises_rejected(self):
        from research.kernels import RiverKernel
        from research.guarantee_lab.river_credit import prove_river_credit,RiverContract
        k=RiverKernel([0,21,31,6,15])
        self.assertIsNone(prove_river_credit(k,[40,41],70,RiverContract(*([True]*7))))
        flags=[True]*7;flags[2]=False
        with self.assertRaises(ValueError):prove_river_credit(k,[40,41],70,RiverContract(*flags))
    def test_symbolic_turn_quads_against_all_45540_worlds(self):
        import numpy as np
        from itertools import combinations
        from runtime.bot import Evaluator,Rules
        from research.guarantee_lab.turn_credit import prove_turn_credit,TurnContract
        hero=(28,29);board=(30,31,0,5);proof=prove_turn_credit(hero,board,70,TurnContract(*([True]*7)))
        self.assertIsNotNone(proof);self.assertEqual(proof.legal_peer_hands,1035)
        available=[c for c in range(52) if c not in hero+board]
        worlds=np.array([(a,b,c) for a,b in combinations(available,2) for c in available if c!=a and c!=b],dtype=np.int64)
        self.assertEqual(len(worlds),45540)
        own=np.column_stack((np.tile(hero,(len(worlds),1)),np.tile(board,(len(worlds),1)),worlds[:,2]))
        peer=np.column_stack((worlds[:,:2],np.tile(board,(len(worlds),1)),worlds[:,2]))
        evaluator=Evaluator(Rules());self.assertTrue(np.all(evaluator.score(own)>evaluator.score(peer)))
        s=BoundSchedule([2,3,5],VERIFIED)
        self.assertEqual(s.certify_safe_settlement(-60,proof,0).lower_score,2)
    def test_turn_nonrainbow_or_higher_public_rank_not_certified(self):
        from research.guarantee_lab.turn_credit import prove_turn_credit,TurnContract
        contract=TurnContract(*([True]*7))
        self.assertIsNone(prove_turn_credit((28,29),(30,31,0,4),70,contract))
        # Actual counterexample outside the rainbow class: peer 5c6c with
        # river 4c makes a straight flush against our quads.
        from runtime.bot import Evaluator,Rules
        import numpy as np
        scores=Evaluator(Rules()).score(np.array([[28,29,30,31,0,4,8],[12,16,30,31,0,4,8]]))
        self.assertGreater(scores[1],scores[0])
        self.assertIsNone(prove_turn_credit((28,29),(30,31,48,45),70,contract))
        flags=[True]*7;flags[1]=False
        with self.assertRaises(ValueError):prove_turn_credit((28,29),(30,31,0,5),70,TurnContract(*flags))
    def test_exact_minimax_and_duplicate_counterexample(self):
        # Rank safety alone does not verify monetary settlement semantics.
        from research.guarantee_lab.river_credit import RiverContract
        from research.guarantee_lab.turn_credit import TurnContract
        for kind in (RiverContract,TurnContract):
            with self.assertRaises(ValueError):kind(*([True]*6)).require()
            kind(*([True]*7)).require()
        r=solve()
        self.assertEqual(r['exact_lower'],'-1/18');self.assertEqual(r['exact_upper'],'-1/18')
        self.assertEqual(r['exact_primal_dual_gap'],'0')
        self.assertEqual(r['duplicate_witness']['best_possible_total'],0)

if __name__=='__main__':unittest.main(verbosity=2)
