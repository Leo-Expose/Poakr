"""One-CPU/1-GiB read-only/no-network closed-loop EXAMPLE controller test.
Run after timing experiments, not concurrently. Imports bundled candidate, not
research Agent. The fixture and opponent are in-process: total time/RSS include
those costs and conservatively upper-bound the candidate on this workload.
"""
import sys,os,time,json,random,resource,importlib.util,subprocess,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];(ROOT/'evidence/cora/reruns').mkdir(parents=True,exist_ok=True)

def worker(hands,contract):
    os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    resource.setrlimit(resource.RLIMIT_AS,(1<<30,1<<30))
    resource.setrlimit(resource.RLIMIT_CPU,(65,65))
    sys.dont_write_bytecode=True
    attempts=[]
    def audit(event,args):
        if event=='open':
            path,mode,flags=args
            if (isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)):
                attempts.append(event);raise PermissionError('read-only test')
        if event in ('socket.__new__','socket.connect','socket.bind','subprocess.Popen','os.system'):
            attempts.append(event);raise PermissionError('no network/processes')
    sys.addaudithook(audit)
    begin=time.perf_counter()
    spec=importlib.util.spec_from_file_location('cora_standalone',ROOT/'releases/cora/v1/cora_bot.py')
    m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
    sys.path.insert(0,str(ROOT))
    from engine.game import Game,GameConfig
    from engine.equity import equity_vs_range,pot_odds
    cfg=GameConfig();adapter=m.CoraAdapter(m.EMBEDDED_PREFLOP,boot_cost=m.BOOT_COST)
    rid=0;net=0.;decisions=0;illegal=0;locked_at=None
    def exchange(obj):
        start=time.perf_counter();old=adapter.bank;spent=old.spent if old else 0.
        reply=adapter.handle(m.strict_json(json.dumps(obj,allow_nan=False)))
        if reply is not None:reply=json.loads(json.dumps(reply,allow_nan=False))
        bank=adapter.bank if adapter.bank else old
        if bank:
            credited=max(0.,bank.spent-spent) if bank is old else 0.
            bank.charge(max(0.,time.perf_counter()-start-credited))
        return reply
    exchange(dict(type='start_match',match_id='resource',starting_stack=cfg.stack,sb=cfg.sb,bb=cfg.bb,
                  max_raises=cfg.max_raises,hands_total=hands,timebank_s=60,raw_net_abandonment_contract=contract))
    def history_wire(history):
        stacks=[cfg.stack-cfg.sb,cfg.stack-cfg.bb];comm=[cfg.sb,cfg.bb];pot=0.;street=-1;events=[]
        for s,p,a in history:
            if s!=street:pot+=sum(comm);comm=[0.,0.];street=s
            tc=max(0.,comm[1-p]-comm[p]);middle=pot+sum(comm)
            if a[0]=='bet':pay=min(tc+middle*a[1],stacks[p]);act=dict(kind='bet',pay=pay)
            elif a[0]=='call':pay=min(tc,stacks[p]);act=dict(kind='call')
            else:pay=0.;act=dict(kind=a[0])
            events.append(dict(street=s+1,actor=p,action=act));stacks[p]-=pay;comm[p]+=pay
        return events
    class Candidate:
        hand=0;left=hands;seat=0
        def decide(self,obs):
            nonlocal rid,decisions,illegal
            legal=[];back={}
            for old in obs['legal']:
                action=dict(kind=old[0])
                if old[0]=='bet':action['pay']=min(obs['to_call']+obs['pot']*old[1],obs['my_stack'])
                key=tuple(sorted(action.items()))
                if key not in back:legal.append(action);back[key]=old
            request=dict(type='decision',match_id='resource',request_id=str(rid),hand_id=str(self.hand),hole=obs['hole'],
                         board=obs['board'],pot=obs['pot'],to_call=obs['to_call'],my_stack=obs['my_stack'],opp_stack=obs['opp_stack'],
                         hands_left=self.left,banked_net=net,seat=self.seat,legal=legal,history=history_wire(obs['history']))
            rid+=1;decisions+=1;reply=exchange(request)
            if reply is None or reply['action'] not in legal:illegal+=1;raise AssertionError('illegal/missing candidate reply')
            return back[tuple(sorted(reply['action'].items()))]
    class Opponent:
        def __init__(self):self.rng=random.Random(82071)
        def decide(self,obs):
            eq=equity_vs_range(obs['hole'],obs['board'],n_draws=64,seed=self.rng.randrange(1<<30))
            bets=[a for a in obs['legal'] if a[0]=='bet']
            if obs['to_call']==0:
                if eq>.75 and bets:return bets[0]
                return ('check',)
            return ('call',) if eq>pot_odds(obs['to_call'],obs['pot'])-.10 else ('fold',)
    a=Candidate();b=Opponent();rng=random.Random(171000+hands)
    for d in range(hands//2):
        dealt=rng.sample(range(52),9)
        for copy in (0,1):
            a.hand=2*d+copy;a.left=hands-a.hand;a.seat=copy
            own,hist=Game(cfg,171000+a.hand).play_hand(dealt,*((a,b) if copy==0 else (b,a)))
            value=own if copy==0 else -own
            folded=any(e[2][0]=='fold' for e in hist);last=max((e[0] for e in hist),default=-1)
            nboard=5 if not folded else sum(cfg.board_by_street[:last+1])
            outcome=None if folded else (1 if value>0 else -1 if value<0 else 0)
            exchange(dict(type='hand_end',match_id='resource',hand_id=str(a.hand),seat=copy,board=dealt[4:4+nboard],
                          outcome=outcome,history=history_wire(hist)))
            net+=value
            if adapter.agent.locked and locked_at is None:locked_at=a.hand
    if locked_at is not None:assert net>0
    bank=adapter.bank
    stats=dict(soft_deadline_recoveries=adapter.agent.errors,kernel_builds=adapter.agent.kernel_builds)
    exchange(dict(type='end_match',match_id='resource'))
    result=dict(hands=hands,contract=contract,wall_s=time.perf_counter()-begin,bank_spent_s=bank.spent,
                bank_left_s=bank.remaining(),requests=decisions,illegal_actions=illegal,
                **stats,
                locked_at=locked_at,net=net,peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                cpu_affinity=list(os.sched_getaffinity(0)),address_space_limit_bytes=1<<30,forbidden_attempts=attempts,
                python=sys.version,numpy_version=m.np.__version__,standalone_sha256=hashlib.sha256((ROOT/'releases/cora/v1/cora_bot.py').read_bytes()).hexdigest(),execution='bundled EXAMPLE adapter via serialized in-process frames; not official subprocess protocol')
    assert not attempts and illegal==0 and result['bank_left_s']>0
    print(json.dumps(result),flush=True)

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='worker':worker(int(sys.argv[2]),sys.argv[3]=='true')
    else:
        results=[]
        for n,contract in ((400,True),(1000,True),(1000,False)):
            env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
            start=time.perf_counter()
            p=subprocess.run([sys.executable,'-B',__file__,'worker',str(n),str(contract).lower()],cwd=ROOT,env=env,capture_output=True,text=True,timeout=70)
            if p.returncode:raise RuntimeError(p.stderr or p.stdout)
            row=json.loads(p.stdout);row['external_process_wall_s']=time.perf_counter()-start;results.append(row);print(json.dumps(row),flush=True)
        (ROOT/'evidence/cora/reruns/resource_results.json').write_text(json.dumps(results,indent=2))
