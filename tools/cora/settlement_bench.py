"""Constrained synthetic settlement trace + selection microbenchmark.
Not official transport, game strength, OS isolation, or a worst-case clock proof.
"""
import os
import sys
import time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def worker(stage):
    start = time.perf_counter()
    import resource
    import json
    import statistics
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    resource.setrlimit(resource.RLIMIT_AS, (1 << 30, 1 << 30))
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
        os.environ[key] = '1'
    forbidden = []
    def audit(event, args):
        if event.startswith(('socket.', 'subprocess.')) or event in ('os.system','os.fork','os.posix_spawn'):
            forbidden.append(event)
            raise RuntimeError('forbidden operation: '+event)
        if event == 'open':
            _, mode, flags = args
            if (isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)):
                forbidden.append(event)
                raise RuntimeError('runtime write forbidden')
    sys.addaudithook(audit)
    from research.guarantee_lab.certificates import Contract
    from research.guarantee_lab.river_credit import RiverContract
    from research.guarantee_lab.turn_credit import TurnContract
    from research.guarantee_lab.settlement import TickLedger, SettlementController, Rules, Request, Mode
    rules = Rules('synthetic-standard-high-matched-ticks-v1',Contract(*([True]*5)),
                  RiverContract(*([True]*7)),TurnContract(*([True]*7)))
    ledger = TickLedger(200,4)
    def begin(name, hero): ledger.begin(ledger.revision+1,name,hero)
    def pay(player,amount): ledger.pay(ledger.revision+1,ledger.active.hand_id,player,amount)
    def reveal(board): ledger.reveal(ledger.revision+1,ledger.active.hand_id,board)
    def req():
        h = ledger.active
        owed = max(0,h.paid[1]-h.paid[0])
        return Request(h.hand_id,ledger.revision,rules.version,h.hero,h.board,owed,
                       frozenset(('call','fold','raise') if owed else ('check','raise')))
    begin('past',(4,8)); pay(0,60); pay(1,61)
    ledger.settle(ledger.revision+1,'past','hero_fold',(0,121))
    if stage == 'turn':
        begin('certified',(28,29)); pay(0,50); pay(1,70); reveal((30,31,0,5))
    else:
        begin('certified',(47,51)); pay(0,50); pay(1,70); reveal((35,39,43,0,5))
    controller = SettlementController(ledger,[60,2,3,5],rules)
    arm_start = time.perf_counter()
    certificate = controller.try_arm()
    arm_s = time.perf_counter()-arm_start
    assert certificate.strict_success and certificate.lower_score == 2
    initial_request = req()
    samples = []
    for _ in range(10000):
        a = time.perf_counter_ns()
        decision = controller.choose(initial_request,deadline_recovery=True)
        samples.append(time.perf_counter_ns()-a)
        assert decision.action == 'call' and decision.amount == 20
    trace = []
    trace.append(dict(hand='certified',mode=controller.mode.value,action='call',amount=20))
    controller.confirm(controller.choose(req()))
    assert controller.mode == Mode.SETTLE_SAFE_HAND
    if stage == 'turn':
        reveal((30,31,0,5,2))
        trace.append(dict(hand='certified',mode=controller.mode.value,action='check',amount=0))
        controller.confirm(controller.choose(req(),deadline_recovery=True))
    controller.settle(ledger.revision+1,'certified','hero_win',(140,0),reported_raw=10)
    assert controller.mode == Mode.ABANDON
    for index,cost in ((2,3),(3,5)):
        name = 'future-'+str(index)
        begin(name,(4,8)); pay(0,cost); pay(1,cost+1)
        decision = controller.choose(req())
        assert decision.action == 'fold'
        trace.append(dict(hand=name,mode=controller.mode.value,action=decision.action,amount=0))
        controller.confirm(decision)
        controller.settle(ledger.revision+1,name,'hero_fold',(0,2*cost+1))
    assert ledger.raw == 2 and controller.mode == Mode.DONE and controller.certificate.strict_success
    result = dict(stage=stage,prototype_only=True,initial_banked_raw=-60,certified_lower_score='2',
                  final_raw=ledger.raw,final_mode=controller.mode.value,trace=trace,
                  arming_s=arm_s,selection_reads=10000,selection_median_us=statistics.median(samples)/1000,
                  selection_p95_us=sorted(samples)[9499]/1000,
                  worker_wall_s=time.perf_counter()-start,
                  peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                  affinity=list(os.sched_getaffinity(0)),address_space_limit_bytes=1 << 30,
                  numpy_loaded='numpy' in sys.modules,forbidden_attempts=forbidden,
                  python=sys.version.split()[0],
                  scope='same-state read microbenchmark and synthetic four-hand ledger trace; not official wire/clock or OS isolation')
    print(json.dumps(result))


if __name__ == '__main__':
    if '--worker' in sys.argv:
        worker(sys.argv[-1])
    else:
        import json
        import subprocess
        import hashlib
        results = []
        for stage in ('turn','river'):
            start = time.perf_counter()
            run = subprocess.run([sys.executable,'-B',__file__,'--worker',stage],capture_output=True,text=True,
                                 timeout=30,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
            if run.returncode:
                raise RuntimeError(run.stderr)
            row = json.loads(run.stdout)
            row['subprocess_wall_s'] = time.perf_counter()-start
            results.append(row)
        source_paths = list((ROOT/'research/guarantee_lab').glob('*.py')) + [ROOT/'research/kernels.py',ROOT/'runtime/bot.py',Path(__file__)]
        result = dict(results=results,source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths})
        destination = ROOT/'evidence/guarantee_lab/settlement_results.json'
        destination.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result,indent=2))
