"""Independent correctness, adversarial state, protocol and resource tests for v2."""
import unittest, random, math, json, sys, os, subprocess, tempfile, pathlib, ast
from collections import Counter
from itertools import combinations
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from runtime import bot as b


def ref_five(cards,rules):
    ns=len(rules.suits); ranks=sorted((c//ns for c in cards),reverse=True)
    groups=Counter(ranks); pairs=sorted((r for r,n in groups.items() if n==2),reverse=True)
    trips=sorted((r for r,n in groups.items() if n==3),reverse=True)
    quads=sorted((r for r,n in groups.items() if n==4),reverse=True)
    singles=sorted((r for r,n in groups.items() if n==1),reverse=True)
    flush=len({c%ns for c in cards})==1
    straight=max((high for pat,high in rules.patterns if set(pat)<=set(ranks)),default=-1)
    if flush and straight>=0: name,tie='straight_flush',[straight]
    elif quads: name,tie='quads',quads+singles
    elif trips and pairs: name,tie='full_house',trips+pairs
    elif flush: name,tie='flush',ranks
    elif straight>=0: name,tie='straight',[straight]
    elif trips: name,tie='trips',trips+singles
    elif len(pairs)==2: name,tie='two_pair',pairs+singles
    elif pairs: name,tie='pair',pairs+singles
    else: name,tie='high',ranks
    v=0
    for r in tie: v=(v<<4)|r
    return (rules.category_order.index(name)<<24)|v


def ref_best(cards,rules):
    return max(ref_five([cards[i] for i in idx],rules) for idx in combinations(range(len(cards)),5)
               if rules.exact_hole_used is None or sum(i<rules.hole_count for i in idx)==rules.exact_hole_used)


def normalize_standard(v): return ((int(v)>>20)<<24)|(int(v)&((1<<20)-1))


def obs(rid='r',hid='h',**changes):
    d=dict(request_id=rid,hand_id=hid,hole=(48,49),board=(),pot=3,to_call=1,my_stack=199,opp_stack=198,
           legal=(b.Action('fold'),b.Action('call'),b.Action('bet',4)),hands_left=400)
    d.update(changes); return b.Observation(**d)


class RulesAndEvaluator(unittest.TestCase):
    def test_card_parser_strict(self):
        r=b.Rules()
        for text,wanted in [('Ac',48),('10s',35),('A♠',51),('Td',33)]: self.assertEqual(r.card(text),wanted)
        for v in ('A13','1c','10','Acx',True,-1,52,None):
            with self.assertRaises(b.ValidationError): r.card(v)
    def test_duplicates_nonfinite_and_rules(self):
        with self.assertRaises(b.ValidationError): b.Rules().cards(['Ac','Ac'])
        for v in (float('nan'),float('inf'),True,'4',1e308,10**1000):
            with self.assertRaises(b.ValidationError): b.number(v,'n')
        with self.assertRaises(b.ValidationError): b.Rules(suits='cdhsx')
        with self.assertRaises(b.ValidationError): b.Rules(hole_count=1,board_by_street=(3,))
        with self.assertRaises(b.ValidationError): b.Rules(exact_hole_used=2,board_by_street=(2,))
    def test_standard_random_reference(self):
        r=random.Random(99); rules=b.Rules(); evaluator=b.Evaluator(rules)
        hands=np.array([r.sample(range(52),7) for _ in range(1200)])
        expected=[ref_best(h.tolist(),rules) for h in hands]
        actual=[normalize_standard(x) for x in evaluator.score(hands)]
        self.assertEqual(actual,expected)
    def test_variant_reference(self):
        variants=[b.Rules(ranks='6789TJQKA'), b.Rules(board_by_street=(2,1,1)),
                  b.Rules(hole_count=1,board_by_street=(3,1)),
                  b.Rules(hole_count=4,exact_hole_used=2),
                  b.Rules(category_order=('high','pair','two_pair','trips','straight','full_house','flush','quads','straight_flush')),
                  b.Rules(wheel=False), b.Rules(suits='cd',ranks='23456789TJQKA'),
                  b.Rules(category_order=tuple(reversed(b.CATEGORIES)))]
        r=random.Random(8)
        for rules in variants:
            hands=np.array([r.sample(range(rules.deck_size),rules.hole_count+rules.board_count) for _ in range(100)])
            self.assertEqual(b.Evaluator(rules).score(hands).tolist(),[ref_best(h.tolist(),rules) for h in hands])
    def test_invalid_evaluator_cards(self):
        e=b.Evaluator(b.Rules())
        for hands in ([[0,0,1,2,3,4,5]],[[0,1,2,3,4,5,52]],[[0.1]*7],[[0,1]]):
            with self.assertRaises(b.ValidationError): e.score(hands)
        self.assertEqual(len(e.score(np.empty((0,7),int))),0)
    def test_known_exact_flop_turn_river(self):
        rng=random.Random(7); rules=b.Rules()
        engine=b.EquityEngine(rules,b.Settings(),np.random.default_rng(0))
        dealt=rng.sample(range(52),9)
        for nb in (3,4,5):
            hole,opp,board=tuple(dealt[:2]),tuple(dealt[2:4]),tuple(dealt[4:4+nb])
            unseen=[c for c in range(52) if c not in hole+opp+board]
            scores=[]
            for runout in combinations(unseen,5-nb):
                a=ref_best(list(hole+board+runout),rules); z=ref_best(list(opp+board+runout),rules)
                scores.append(1.0 if a>z else 0.0 if a<z else 0.5)
            eq=engine.estimate(hole,board,opp,(.5,),engine.clock()+3)
            self.assertTrue(eq.exact); self.assertAlmostEqual(eq.value,sum(scores)/len(scores),12)
            self.assertEqual(eq.samples,len(scores))
    def test_exact_timeout_never_returns_prefix_equity(self):
        class Clock:
            def __init__(self): self.n=0
            def __call__(self): self.n+=1; return self.n
        e=b.EquityEngine(b.Rules(),b.Settings(),np.random.default_rng(1),Clock())
        self.assertIsNone(e.estimate((48,49),(0,21,31),(44,45),(.5,),3))
    def test_sampling_and_confidence_bounds(self):
        e=b.EquityEngine(b.Rules(),b.Settings(),np.random.default_rng(1))
        v=e.estimate((48,49),(),None,(.5,),e.clock()+2)
        self.assertFalse(v.exact); self.assertGreater(v.value,.75)
        self.assertLessEqual(v.low,v.value); self.assertGreaterEqual(v.high,v.value)
    def test_small_variant_exact_preflop(self):
        rules=b.Rules(ranks='23456',suits='cd',hole_count=1,board_by_street=(2,1,1))
        engine=b.EquityEngine(rules,b.Settings(),np.random.default_rng(3))
        hole,opp=(0,),(9,); unseen=[x for x in range(10) if x not in hole+opp]
        expected=[]
        for board in combinations(unseen,4):
            a,z=ref_best(list(hole+board),rules),ref_best(list(opp+board),rules)
            expected.append(1 if a>z else 0 if a<z else .5)
        result=engine.estimate(hole,(),opp,(.5,),engine.clock()+2)
        self.assertTrue(result.exact); self.assertEqual(result.samples,70)
        self.assertAlmostEqual(result.value,sum(expected)/70)
    def test_mc_cache_reuses_and_resumes_with_valid_bounds(self):
        engine=b.EquityEngine(b.Rules(),b.Settings(max_samples=256),np.random.default_rng(7))
        first=engine.estimate((48,49),(),None,(.5,),engine.clock()+2)
        state=repr(engine.rng.bit_generator.state)
        again=engine.estimate((48,49),(),None,(.5,),engine.clock()+2)
        self.assertEqual(first,again); self.assertEqual(state,repr(engine.rng.bit_generator.state))
        self.assertGreater(first.looks,0)


class StateAndPolicy(unittest.TestCase):
    def test_session_isolation(self):
        a=b.BotSession('a',seed=1); z=b.BotSession('z',seed=1)
        a.act(obs())
        self.assertEqual(z.decisions,0); self.assertEqual(z.duplicate.matches,0)
        self.assertEqual(z.bank.spent,0); self.assertEqual(z.opponent.counts,{})
    def test_idempotent_request_and_conflicting_id(self):
        s=b.BotSession('a'); o=obs(); action=s.act(o)
        self.assertEqual(action,s.act(o)); self.assertEqual(s.decisions,1)
        with self.assertRaises(b.ValidationError): s.act(obs(pot=4))
    def test_board_regression_and_hand_reuse(self):
        d=b.DuplicateMemory(b.Rules(),b.Settings())
        d.observe(obs(board=(0,21,31)))
        with self.assertRaises(b.ValidationError): d.observe(obs('r2',board=()))
        with self.assertRaises(b.ValidationError): d.observe(obs('r2',hole=(44,45)))
    def test_duplicate_ambiguity_conflict_and_kill(self):
        d=b.DuplicateMemory(b.Rules(),b.Settings(duplicate_mode='board'))
        d.matches=3
        d.observe(obs('a','a',board=(0,21,31,6,15)))
        target=obs('b','b',hole=(44,45),board=(0,21,31))
        d.observe(target); self.assertEqual(d.infer(target),(48,49))
        self.assertIsNone(d.infer(obs('c','c',hole=(48,45),board=(0,21,31))))
        self.assertIsNone(d.infer(obs('c','c',hole=(44,45),board=(0,21,31,7))))
        self.assertIsNone(d.infer(obs('c','c',hole=(44,45),board=())))
        d.observe(obs('d','d',hole=(40,41),board=(0,21,31)))
        self.assertIsNone(d.infer(target))
        d.reveal('b',(48,50)); self.assertGreater(d.contradictions,0); self.assertIsNone(d.infer(target))
    def test_public_terminal_board_and_finished_hand(self):
        d=b.DuplicateMemory(b.Rules(),b.Settings(duplicate_mode='board')); d.matches=3
        d.observe(obs('a','a'))
        d.finish_hand('a',[0,21,31,6,15])
        target=obs('b','b',hole=(44,45),board=(0,21,31))
        d.observe(target); self.assertEqual(d.infer(target),(48,49))
        d.reveal('b',(48,49)); self.assertEqual(d.confirmed_swaps,1)
        d.finish_hand('b',[0,21,31,6,15])
        with self.assertRaises(b.ValidationError): d.observe(obs('new','b',hole=(44,45),board=(0,21,31,6,15)))
    def test_impossible_terminal_reveal_is_atomic(self):
        d=b.DuplicateMemory(b.Rules(),b.Settings()); d.observe(obs())
        prior=d.history['h']
        with self.assertRaises(b.ValidationError): d.finish_hand('h',[0,21,31,6,15],(0,44))
        self.assertEqual(d.history['h'],prior)
        self.assertEqual(d.confirmed_swaps,0)
    def test_explicit_pair_id_preflop_only(self):
        d=b.DuplicateMemory(b.Rules(),b.Settings(duplicate_mode='pair_id'))
        d.observe(obs('a','a',pair_id='p'))
        target=obs('b','b',hole=(44,45),pair_id='p')
        d.observe(target); self.assertEqual(d.infer(target),(48,49))
        self.assertIsNone(d.infer(obs('c','c',hole=(40,41),pair_id='new')))
    def test_random_hands_do_not_self_enable(self):
        d=b.DuplicateMemory(b.Rules(),b.Settings(duplicate_mode='board')); rng=random.Random(13)
        for i in range(500):
            x=rng.sample(range(52),5); d.observe(obs(str(i),str(i),hole=tuple(x[:2]),board=tuple(x[2:])))
        self.assertEqual(d.matches,0)
    def test_observation_validation(self):
        for o in (obs(to_call=float('nan')),obs(board=(0,1)),obs(hole=(48,48)),
                  obs(legal=(b.Action('check'),)),obs(legal=()),obs(pot=0),obs(legal=(b.Action('bet',200),))):
            with self.assertRaises(b.ValidationError): o.validate(b.Rules())
    def test_price_accounts_uncalled_overbet(self):
        o=obs(pot=110,to_call=100,my_stack=20,legal=(b.Action('fold'),b.Action('call')))
        self.assertEqual(o.price(),(20,30,.4))
    def test_ties_and_profitable_draws_call(self):
        s=b.BotSession('s')
        o=obs(pot=20,to_call=1,legal=(b.Action('fold'),b.Action('call')))
        for eq in (.3,.5):
            result=b.EquityResult(eq,eq,eq,44,True,'known-exact')
            self.assertEqual(s.policy.choose(o,result,True,400),b.Action('call'))
    def test_free_checks_and_legal_sizes(self):
        s=b.BotSession('s'); o=obs(to_call=0,legal=(b.Action('check'),b.Action('bet',6)))
        self.assertEqual(s.policy.choose(o,b.EquityResult(1,1,1,1,True,'x'),True,400),b.Action('bet',6))
        self.assertEqual(s.policy.choose(o,b.EquityResult(0,0,0,1,True,'x'),True,400),b.Action('check'))
    def test_watchdog_interrupts_slow_compute(self):
        import time, signal
        if not hasattr(signal,'setitimer'): self.skipTest('POSIX timer unavailable')
        session=b.BotSession('slow',settings=b.Settings(decision_cap_s=.003))
        def slow(*args): time.sleep(.05); return None
        session.equity.estimate=slow
        begin=time.perf_counter(); action=session.act(obs())
        self.assertEqual(action,b.Action('fold'))
        self.assertLess(time.perf_counter()-begin,.04)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL),(0.0,0.0))
    def test_watchdog_preserves_existing_host_timer(self):
        import signal
        if not hasattr(signal,'setitimer'): self.skipTest('POSIX timer unavailable')
        old=signal.getsignal(signal.SIGALRM)
        signal.setitimer(signal.ITIMER_REAL,1)
        try:
            with b.decision_guard(.001):
                self.assertGreater(signal.getitimer(signal.ITIMER_REAL)[0],.9)
            self.assertEqual(signal.getsignal(signal.SIGALRM),old)
        finally: signal.setitimer(signal.ITIMER_REAL,0)
    def test_budget_stage_host_and_exhaustion(self):
        a=b.BotSession('a',hands_total=400); z=b.BotSession('z',hands_total=1000)
        self.assertLess(z.bank.budget(1000,.025),a.bank.budget(400,.025))
        a.bank.update_host(1); self.assertEqual(a.bank.remaining(),0)
        self.assertEqual(a.act(obs()),b.Action('fold')); self.assertIsNone(a.last_equity)
    def test_opponent_events_are_validated_deduped(self):
        m=b.OpponentStats(b.Settings())
        self.assertTrue(m.observe(1,2,'fold',True,.5)); self.assertFalse(m.observe(1,2,'fold',True,.5))
        with self.assertRaises(b.ValidationError): m.observe(2,2,'check',True,.5)
        self.assertEqual(m.last_seq,1)
        self.assertEqual(m.fold_lower(2,.5),0)
        for i in range(2,60): m.observe(i,2,'fold',True,.5)
        self.assertGreater(m.fold_lower(2,.5),.6)
        self.assertEqual(m.fold_lower(2,2),0)
    def test_bounded_memory(self):
        s=b.BotSession('m',settings=b.Settings(cache_size=8,history_size=8))
        for i in range(40):
            s.act(obs(str(i),str(i),legal=(b.Action('fold'),)))
        self.assertLessEqual(len(s.responses),8); self.assertLessEqual(len(s.duplicate.history),8)


class ProtocolAndDeployment(unittest.TestCase):
    def start(self,a,mid='m',hands=400):
        return a.handle(dict(type='start_match',match_id=mid,hands_total=hands,timebank_s=60))
    def message(self):
        return dict(type='decision',match_id='m',request_id='r',hand_id='h',hole=['Ac','Ad'],board=[],pot=3,to_call=1,
                    my_stack=199,opp_stack=198,hands_left=400,legal=[{'kind':'fold'},{'kind':'call'},{'kind':'bet','pay':4}])
    def test_control_messages_and_match_reset(self):
        a=b.ExampleAdapter(); self.assertIsNone(self.start(a)); first=a.session
        self.assertIsNone(a.handle(dict(type='status',match_id='m')))
        with self.assertRaises(b.ValidationError): self.start(a)
        self.assertIs(a.session,first)
        self.assertIsNone(a.handle(dict(type='end_match',match_id='m')))
        self.start(a,'next',1000); self.assertIsNot(a.session,first); self.assertEqual(a.session.decisions,0)
    def test_no_guessed_actions_or_sizing(self):
        a=b.ExampleAdapter(); self.start(a); message=self.message()
        reply=a.handle(message); self.assertEqual(reply['request_id'],'r')
        self.assertEqual(a.handle(message),reply)
        with self.assertRaises(b.ValidationError): b.legal_from_json(['bet'])
        with self.assertRaises(b.ValidationError): b.legal_from_json([{'kind':'raise','amount':200}])
        malformed=self.message(); malformed['request_id']='bad'; malformed['hole']=['Ac','Ac']
        with self.assertRaises(b.ValidationError): a.handle(malformed)
        self.assertIn(a.fallback(malformed)['action']['kind'],('fold','call','bet'))
    def test_duplicate_json_keys_and_empty_ids_rejected(self):
        for text in ('{"x":1,"x":2}','{"x":NaN}'):
            with self.assertRaises(b.ValidationError): b.strict_json(text)
        for value in ('','   ',None,True):
            with self.assertRaises(b.ValidationError): b.identifier(value,'id')
    def test_wrong_match_never_fallback(self):
        a=b.ExampleAdapter(); self.start(a); m=self.message(); m['match_id']='wrong'
        with self.assertRaises(b.ValidationError): a.handle(m)
        self.assertIsNone(a.fallback(m))
    def test_build_deterministic_and_python311_grammar(self):
        p=ROOT/'runtime/bot.py'; before=p.read_bytes()
        subprocess.run([sys.executable,str(ROOT/'bench/build_release.py')],check=True,capture_output=True)
        self.assertEqual(before,p.read_bytes()); ast.parse(p.read_text(),feature_version=(3,11))
    def test_single_file_subprocess_protocol_and_read_only(self):
        a=b.ExampleAdapter(); data=[dict(type='start_match',match_id='m',hands_total=400,timebank_s=60),self.message(),
                                   dict(type='status',match_id='m'),dict(type='end_match',match_id='m')]
        with tempfile.TemporaryDirectory(dir='/home/user') as td:
            p=pathlib.Path(td)/'bot.py'; p.write_bytes((ROOT/'runtime/bot.py').read_bytes()); p.chmod(0o444)
            os.chmod(td,0o555)
            try:
                run=subprocess.run([sys.executable,'-B',str(p)],input='\n'.join(json.dumps(x) for x in data)+'\n',
                                   capture_output=True,text=True,cwd=td,timeout=10)
                self.assertEqual(run.returncode,0,run.stderr)
                self.assertEqual(len(run.stdout.splitlines()),1)
                self.assertEqual(json.loads(run.stdout)['type'],'action')
                self.assertEqual(set(x.name for x in pathlib.Path(td).iterdir()),{'bot.py'})
            finally: os.chmod(td,0o755)
    def test_oversized_malformed_and_nonfinite_json(self):
        data=[json.dumps(dict(type='start_match',match_id='m',hands_total=400,timebank_s=60)),
              'x'*(b.MAX_LINE_BYTES+2),'{bad}', '{"type":"status","match_id":"m","x":NaN}',json.dumps(self.message())]
        run=subprocess.run([sys.executable,str(ROOT/'runtime/bot.py')],input='\n'.join(data)+'\n',capture_output=True,text=True,timeout=10)
        self.assertEqual(run.returncode,0); self.assertEqual(len(run.stdout.splitlines()),1)
        self.assertEqual(len(run.stderr.splitlines()),3)


if __name__=='__main__': unittest.main(verbosity=2)
