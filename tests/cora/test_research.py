"""Exact-kernel, latent-policy, nonleakage and hard-lock tests."""
import sys,unittest,random,time,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from research.kernels import RiverKernel,PolicyMixture,WinLock
from research.agent import Agent
from runtime.bot import Rules
import numpy as np


class KernelTests(unittest.TestCase):
    def test_every_hand_matches_disjoint_pair_oracle(self):
        rng=random.Random(821)
        for rules in (Rules(),Rules(ranks='6789TJQKA'),Rules(wheel=False)):
            board=rng.sample(range(rules.deck_size),5); k=RiverKernel(board,rules)
            for i,h in enumerate(k.holes):
                valid=np.all(k.holes!=h[0],axis=1)&np.all(k.holes!=h[1],axis=1)
                expected=np.mean((k.scores[i]>k.scores[valid])+.5*(k.scores[i]==k.scores[valid]))
                self.assertAlmostEqual(float(k.percentile[i]),float(expected),14)
    def test_all_tie_board(self):
        k=RiverKernel([32,36,40,44,48]) # club royal flush board
        self.assertTrue(np.all(k.percentile==.5))
    def test_hero_view_removes_all_blockers(self):
        k=RiverKernel([0,21,31,6,15]); ids,z,p,o=k.view([48,49])
        self.assertEqual(len(ids),990);self.assertFalse(np.any(np.isin(k.holes[ids],[48,49])))
        self.assertEqual(set(o),{-1,0,1})
    def test_likelihood_changes_equity_in_right_direction(self):
        k=RiverKernel([0,21,31,6,15]); model=PolicyMixture()
        # Isolate a tight, no-bluff model for the conditional-range unit test.
        mask=(model.threshold==.8)&(model.bluff==0)&(model.slack==.22)&(model.raise_rate==0)&(model.value_rate==1)
        model.weights=mask.astype(float);model.weights/=model.weights.sum()
        belief=model.begin(k,[40,41]); before=belief.equity()
        belief.observe('bet',False,0)
        self.assertLess(belief.equity(),before)
    def test_public_outcome_teaches_without_hole_reveal(self):
        k=RiverKernel([0,21,31,6,15]); model=PolicyMixture(); before=model.weights.copy()
        b=model.begin(k,[40,41]);b.observe('bet',False,0);b.finish(+1)
        self.assertFalse(np.allclose(model.weights,before))
        self.assertAlmostEqual(float(model.weights.sum()),1.)
    def test_no_probability_collapse(self):
        k=RiverKernel([0,21,31,6,15]);model=PolicyMixture()
        for _ in range(20):
            b=model.begin(k,[40,41]);b.observe('bet',False,0);b.observe('bet',True,.6);b.finish(-1)
        self.assertTrue(np.all(np.isfinite(model.weights)));self.assertTrue(np.all(model.weights>0))
    def test_exact_behavioral_quotient(self):
        k=RiverKernel([0,21,31,6,15]);m=PolicyMixture()
        dense=m.begin(k,[40,41],compress=False);small=m.begin(k,[40,41],compress=True)
        self.assertLess(len(small.z),len(dense.z))
        for kind,faced,price in [('check',False,0),('bet',True,.25),('call',True,.40)]:
            dense.observe(kind,faced,price);small.observe(kind,faced,price)
            self.assertAlmostEqual(dense.equity(),small.equity(),13)
            self.assertTrue(np.allclose(dense.joint.sum(axis=1),small.joint.sum(axis=1),atol=1e-13))
            self.assertTrue(np.allclose(dense.response(.3),small.response(.3),atol=1e-13))
    def test_evidence_commit_and_replay_are_atomic(self):
        from runtime.bot import ComputationExpired
        k=RiverKernel([0,21,31,6,15]);m=PolicyMixture();b=m.begin(k,[40,41])
        before=b.joint.copy();real=m.likelihood
        def interrupted(*args): raise ComputationExpired('injected')
        m.likelihood=interrupted
        with self.assertRaises(ComputationExpired): b.observe('bet',False,0,event_id=3)
        self.assertTrue(np.array_equal(b.joint,before));self.assertEqual(b.evidence,0)
        m.likelihood=real;b.observe('bet',False,0,event_id=3)
        after=b.joint.copy();self.assertFalse(b.observe('bet',False,0,event_id=3))
        self.assertTrue(np.array_equal(b.joint,after));self.assertEqual(b.evidence,1)
    def test_policy_categorical_probabilities_sum_to_one(self):
        m=PolicyMixture();z=np.linspace(0,1,101)
        for price in (0.,.1,.4,.7,1.):
            for can_raise in (True,False):
                kinds=('fold','call','bet') if can_raise else ('fold','call')
                total=sum(m.likelihood(z,k,True,price,can_raise) for k in kinds)
                self.assertTrue(np.allclose(total,1,atol=1e-15,rtol=0))
                b=m.likelihood(z,'check',False,price,can_raise)
                if can_raise:b=b+m.likelihood(z,'bet',False,price,can_raise)
                self.assertTrue(np.allclose(b,1,atol=1e-15,rtol=0))
    def test_showdown_is_exact_and_response_matches_legal_continuation(self):
        k=RiverKernel([0,21,31,6,15]);m=PolicyMixture();b=m.begin(k,[40,41])
        for cr in (True,False):
            call=m.likelihood(b.z,'call',True,.3,cr)
            if cr:call+=m.likelihood(b.z,'bet',True,.3,cr)
            expected=(float(np.sum(b.joint*call)),float(np.sum(b.joint*call*b.payoff[None,:])))
            self.assertTrue(np.allclose(b.response(.3,cr),expected,atol=1e-14))
        b.observe('bet',False,0);b.finish(-1)
        self.assertTrue(np.all(b.joint[:,b.outcome!=-1]==0))
        self.assertAlmostEqual(float(b.joint.sum()),1.)
    def test_public_kernel_reuse_not_previous_hole_inference(self):
        a=Agent(preflop={});ka=a._kernel((0,21,31,6,15))
        a.set_context('new',120,0);kb=a._kernel((0,21,31,6,15))
        self.assertIs(ka,kb);self.assertIsNone(a.hole);self.assertIsNone(a.belief)
        self.assertEqual(a.session.settings.duplicate_mode,'off')


class CertificateTests(unittest.TestCase):
    def test_tie_is_not_a_win(self):
        self.assertFalse(WinLock.certified(9,1,5,2))
        self.assertTrue(WinLock.certified(9.01,1,5,2))
    def test_bound_against_adversarial_returns(self):
        # Abandonment loses at most initial commitment and each forced posting.
        rng=random.Random(199)
        for _ in range(10000):
            left=rng.randrange(1,101); paid=rng.uniform(0,200); post=rng.uniform(0,5)
            net=paid+(left-1)*post+rng.uniform(.001,100)
            bound=WinLock.lower_bound(net,paid,left,post)
            actual=net-paid-sum(rng.uniform(0,post) for _ in range(left-1))
            self.assertGreaterEqual(actual,bound-1e-9);self.assertGreater(actual,0)
    def test_missing_guarantees_rejected(self):
        for args in ((1,-1,3,2),(1,0,0,2),(1,0,True,2),(float('nan'),0,1,2)):
            with self.assertRaises(ValueError): WinLock.certified(*args)


if __name__=='__main__': unittest.main(verbosity=2)
