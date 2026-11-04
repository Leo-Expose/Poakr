#!/usr/bin/env python3
"""Isolated 1-vCPU, 1-GiB, no-network/no-file-write stress for 400/1000 hands.
Synthetic request stress, NOT poker match performance or an official runner test.
"""
import sys, os, json, time, pathlib, subprocess, resource
ROOT=pathlib.Path(__file__).resolve().parent.parent

def worker(hands):
    os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    resource.setrlimit(resource.RLIMIT_AS,(1024**3,1024**3))
    resource.setrlimit(resource.RLIMIT_CPU,(50,50))
    def audit(event,args):
        if event.startswith('socket.') or event in ('subprocess.Popen','os.system'):
            raise RuntimeError('forbidden network/process call')
        if event=='open':
            path,mode,flags=args
            if (isinstance(mode,str) and any(c in mode for c in 'wax+')) or flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC):
                raise RuntimeError('forbidden filesystem write')
    sys.addaudithook(audit)
    sys.path.insert(0,str(ROOT)); start=time.perf_counter()
    from runtime import bot as b
    import random, hashlib
    runtime_sha256=hashlib.sha256((ROOT/'runtime/bot.py').read_bytes()).hexdigest()
    boot=time.perf_counter()-start
    s=b.BotSession('stress',settings=b.Settings(duplicate_mode='board'),hands_total=hands,seed=43)
    s.bank.charge(boot); rng=random.Random(43); requests=0; last_id=0
    for deal in range(hands//2):
        dealt=rng.sample(range(52),9)
        for copy in (0,1):
            hand=2*deal+copy; hole=tuple(sorted(dealt[copy*2:copy*2+2])); board=tuple(dealt[4:])
            for nb in (0,3,4,5):
                o=b.Observation(str(requests),str(hand),hole,board[:nb],6,0,197,197,
                                (b.Action('check'),b.Action('bet',3),b.Action('bet',6)),hands_left=hands-hand)
                action=s.act(o); assert action in o.legal; requests+=1
    result={'hands':hands,'requests':requests,'wall_s':time.perf_counter()-start,'accounted_s':s.bank.spent,
            'bank_remaining_s':s.bank.remaining(),'info_decisions':s.info_decisions,'compute_timeouts':s.errors,
            'rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,'cpu_count':len(os.sched_getaffinity(0)),
            'address_space_cap_mib':1024,'network_and_file_write_audit':'no attempted forbidden operations',
            'legal_responses':requests,'python':sys.version.split()[0],'runtime_sha256':runtime_sha256}
    assert result['wall_s']<60
    print(json.dumps(result))

if __name__=='__main__':
    if '--worker' in sys.argv:
        worker(int(sys.argv[-1]))
    else:
        results=[]
        for hands in (400,1000):
            run=subprocess.run([sys.executable,'-B',__file__,'--worker',str(hands)],capture_output=True,text=True,timeout=65,
                               env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
            if run.returncode: raise RuntimeError(run.stderr or f'worker exited {run.returncode}')
            result=json.loads(run.stdout); results.append(result); print(json.dumps(result),flush=True)
        out=ROOT/'evidence/v2/reruns/resource_results.json'; out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(results,indent=2))
