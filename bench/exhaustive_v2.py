#!/usr/bin/env python3
"""All 2,598,960 standard five-card hands: independent known category frequencies."""
from pathlib import Path
import sys, time, json, resource, hashlib
from itertools import combinations, islice
ROOT=Path(__file__).resolve().parent.parent; sys.path.insert(0,str(ROOT))
from runtime import bot as b
import numpy as np
start=time.perf_counter(); e=b.Evaluator(b.Rules(board_by_street=(3,)))
counts=np.zeros(9,np.int64); it=combinations(range(52),5)
while True:
    chunk=list(islice(it,8192))
    if not chunk: break
    scores=e.score(np.array(chunk,np.int64))
    counts+=np.bincount(scores>>24,minlength=9)
expected=[1302540,1098240,123552,54912,10200,5108,3744,624,40]
assert counts.tolist()==expected,(counts.tolist(),expected)
result={'hands':int(counts.sum()),'counts':dict(zip(b.CATEGORIES,counts.tolist())),
        'seconds':time.perf_counter()-start,'max_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
        'runtime_sha256':hashlib.sha256((ROOT/'runtime/bot.py').read_bytes()).hexdigest(),'passed':True,'scope':'category frequency validation, not exhaustive seven-card differential proof'}
out=ROOT/'evidence/v2/reruns/exhaustive_results.json'; out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(result,indent=2)); print(json.dumps(result,indent=2))
