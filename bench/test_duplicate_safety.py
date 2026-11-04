#!/usr/bin/env python3
"""Adversarial tests of shipped duplicate path; no privileged runout memory."""
import sys, os, random, time, json, subprocess, tempfile, shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'legacy'))
import bot_v1 as bot
from engine.cards import make_evaluator, make_best_of
from itertools import combinations

r = random.Random(191)
checks = 0

def check(x, name):
    global checks
    assert x, name
    checks += 1
    print('PASS', name)

def trained():
    tr = bot.DuplicateTracker()
    for _ in range(6):
        h = r.sample(range(52), 9)
        tr.record(h[:2], h[4:]); tr.record(h[2:4], h[4:])
    return tr

tr = trained()
check(tr.enabled(), 'valid duplicate history enables board matching')
check(tr.infer_partner([0,1], []) == (None,0.0), 'NO adjacency-based preflop guessing')
# Every copy1 preflop and every copy2 preflop must decline without a pair ID.
check(all(tr.infer_partner(r.sample(range(52),2), []) == (None,0.0) for _ in range(100)),
      '100 phase-ambiguous preflops declined')
tr.hist = []
tr.record([0,1], [10,11,12,13,14])
check(tr.infer_partner([2,3], [10,11,12,13,14])[0] == [0,1], 'unique valid board match')
check(tr.infer_partner([0,3], [10,11,12]) == (None,0.0), 'hole overlap rejected')
check(tr.infer_partner([2,3], [10,11,12,0]) == (None,0.0), 'inferred hole / board collision rejected')
check(tr.infer_partner([2,3], [10,11,12,15]) == (None,0.0), 'divergent turn invalidates matching flop')
tr.record([4,5], [10,11,12,13,14])
check(tr.infer_partner([2,3], [10,11,12]) == (None,0.0), 'ambiguous candidate holes rejected')
tr = trained(); tr.verify_revealed([0,1], [0,2])
check(not tr.enabled() and tr.infer_partner([2,3], []) == (None,0.0), 'contradictory showdown disables inference')
tr = bot.DuplicateTracker()
for _ in range(1000):
    d = r.sample(range(52),9); tr.record(d[:2],d[4:])
check(not tr.enabled(), '1000 independent randomized hands do not activate')
# Same hole cards across successive hands: explicit IDs distinguish them.
tr = bot.DuplicateTracker()
tr.observe_request(dict(hand_id=1,hole=[0,1],board=[10,11,12]))
tr.observe_request(dict(hand_id=2,hole=[1,0],board=[]))
check(len(tr.hist)==1, 'explicit IDs handle repeated/reordered hole cards')
# Card-only shell must not interpret legal actions as the opponent folding.
bot.OPP = bot.OpponentModel()
before = bot.OPP.n[:]
bot._learn_from_line(json.dumps({'legal':['fold','call','raise']}), True, 2)
check(bot.OPP.n == before, 'legal-action text never contaminates opponent learning')
bot._learn_from_line(json.dumps({'opponent_action':'fold'}), True, 2)
check(bot.OPP.n[2] == 1, 'explicit opponent response is counted')
# Compare embedded exact evaluator equity against independent 5-subset evaluator.
best = make_best_of(make_evaluator(13,4),7)
for nb in (3,4,5):
    d = r.sample(range(52),9); my,opp,board=d[:2],d[2:4],d[4:4+nb]
    rem=[c for c in range(52) if c not in my+opp+board]
    ws=[]
    for extra in combinations(rem,5-nb):
        a,b=best(my,board+list(extra)),best(opp,board+list(extra))
        ws.append(1.0 if a>b else 0.0 if a<b else 0.5)
    eq=bot.equity_vs_known(my,opp,board,r)
    check(abs(eq-sum(ws)/len(ws))<1e-12, f'exact equity agrees with reference on {nb}-card board')
try:
    bot.equity_vs_known([0,1],[1,2],[3,4,5],r)
    raise AssertionError('accepted invalid cards')
except ValueError:
    check(True, 'invalid equity raises rather than fabricating 50%')
# A 30% draw can be profitable at 10% pot odds; old 52% cutoff was wrong.
obs={'to_call':1,'legal':[('fold',),('call',)]}
check(bot.decide_known_hand(obs,[0,1],0.10,0.30,2,obs['legal'],0,4)==('call',),
      'known-hand calling obeys pot odds')
# All chosen sizes must exist in legal set.
obs={'to_call':0,'legal':[('check',),('bet',2.0)]}
check(bot.decide_known_hand(obs,[0,1],0,1.0,3,obs['legal'],0,4)==('bet',2.0),
      'value sizing obeys restricted legal set')
# Portable deployment: copy ONLY bot.py, evaluate in subprocess from new cwd.
with tempfile.TemporaryDirectory(dir='/home/user') as td:
    shutil.copy(bot.__file__, os.path.join(td,'bot.py'))
    code="import bot,random; print(bot.equity_vs_known([48,49],[44,45],[0,21,31,6,15],random.Random(0)))"
    out=subprocess.run([sys.executable,'-c',code],cwd=td,env={k:v for k,v in os.environ.items() if k!='PYTHONPATH'},capture_output=True,text=True)
    check(out.returncode==0 and out.stdout.strip() in ('0.0','0.5','1.0'), 'standalone bot.py requires no engine package')
tr = trained()
tr.remember_inference({'hand_id':'hand-7'}, [0,1])
tr.verify_status_message(json.dumps({'type':'showdown', 'hand_id':'another', 'opponent_hole':[0,2]}))
check(tr.enabled(), 'unrelated showdown cannot trip kill switch')
tr.verify_status_message(json.dumps({'type':'showdown', 'hand_id':'hand-7', 'opponent_hole':[0,2]}))
check(not tr.enabled(), 'actual structured showdown hook trips kill switch')
bot.BANK = bot.TimeBank()
bot.BANK.spent = bot.BANK.total
obs = {'legal':[('fold',),('call',)], 'to_call':20}
check(bot.decide(obs,r,bot.np.random.default_rng(0))==('fold',), 'exhausted bank exits before expensive work')
bot.BANK = bot.TimeBank()
# Worst-cost postflop path: 400 exact flop requests, no hidden-range sampling.
d = r.sample(range(52),9); start=time.perf_counter()
for _ in range(400): bot.equity_vs_known(d[:2],d[2:4],d[4:7],r)
elapsed=time.perf_counter()-start
check(elapsed < 15, f'400 exact flop equity calls take {elapsed:.3f}s (<15s local guard)')
print(f'\n{checks}/{checks} safety checks passed')
