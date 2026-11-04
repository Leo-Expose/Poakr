"""Exact kernel/quotient versus quadratic oracle; no opponent-policy claims."""
import sys,time,json,random,resource,statistics,os,hashlib
os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
resource.setrlimit(resource.RLIMIT_AS,(1<<30,1<<30))
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];(ROOT/'evidence/cora/reruns').mkdir(parents=True,exist_ok=True);sys.path.insert(0,str(ROOT))
from research.kernels import RiverKernel,PolicyMixture
from runtime.bot import EquityEngine,Rules,Settings
import numpy as np
r=random.Random(2181);rows=[]
for i in range(30):
    cards=r.sample(range(52),7);board=cards[2:];hero=cards[:2]
    start=time.perf_counter();k=RiverKernel(board);build=time.perf_counter()-start
    start=time.perf_counter();oracle=[]
    for j,h in enumerate(k.holes):
        good=np.all(k.holes!=h[0],axis=1)&np.all(k.holes!=h[1],axis=1)
        oracle.append(np.mean((k.scores[j]>k.scores[good])+.5*(k.scores[j]==k.scores[good])))
    quadratic=time.perf_counter()-start
    assert np.allclose(oracle,k.percentile,atol=1e-14,rtol=0)
    model=PolicyMixture();dense=model.begin(k,hero,False);small=model.begin(k,hero,True)
    def measure(b):
        begin=time.perf_counter()
        for _ in range(15): b.response(.25)
        return (time.perf_counter()-begin)/15
    td,ts=measure(dense),measure(small)
    assert np.allclose(dense.response(.25),small.response(.25),atol=1e-13)
    rows.append(dict(kernel_build_s=build,quadratic_oracle_s=quadratic,physical_hands=len(dense.ids),
                     quotient_states=len(small.z),dense_joint_bytes=dense.joint.nbytes,compressed_joint_bytes=small.joint.nbytes,
                     dense_response_s=td,compressed_response_s=ts,kernel_numeric_work_bytes=k.work_bytes))
result=dict(boards=30,results=rows,cpu_affinity=list(os.sched_getaffinity(0)),address_space_limit_bytes=1<<30,numpy_version=np.__version__,kernel_sha256=hashlib.sha256((ROOT/'research/kernels.py').read_bytes()).hexdigest(),timing_context='isolated after corrected confirmation; one CPU; no concurrent benchmark',median_build_ms=1000*statistics.median(x['kernel_build_s'] for x in rows),
            median_oracle_ms=1000*statistics.median(x['quadratic_oracle_s'] for x in rows),
            median_state_compression=statistics.median(x['physical_hands']/x['quotient_states'] for x in rows),
            median_response_speedup=statistics.median(x['dense_response_s']/x['compressed_response_s'] for x in rows),
            peak_process_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
(ROOT/'evidence/cora/reruns/microbench_results.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='results'},indent=2))
