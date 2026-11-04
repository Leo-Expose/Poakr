"""Offline NumPy-only amortization, explicitly sampled (not exact) preflop table."""
import sys,json,time,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from runtime.bot import EquityEngine,Rules,Settings
import numpy as np
rng=np.random.default_rng(61027); engine=EquityEngine(Rules(),Settings(),rng)
rows=[]; start=time.perf_counter(); draws=16384
for hi in range(13):
    for lo in range(hi+1):
        for suited in ((False,) if hi==lo else (False,True)):
            hole=(hi*4,lo*4+(0 if suited else 1)); rem=np.array([c for c in range(52) if c not in hole],int)
            wins=0.
            for _ in range(draws//4096):
                keys=rng.random((4096,len(rem))); picks=rem[np.argpartition(keys,6,axis=1)[:,:7]]
                wins+=engine._compare(hole,(),picks[:,:2],picks[:,2:]).sum()
            rows.append([hi,lo,int(suited),float(wins/draws)])
result=dict(draws_per_hand=draws,rows=rows,seconds=time.perf_counter()-start,
            simultaneous_hoeffding_half_width=math.sqrt(math.log(2*169/.02)/(2*draws)),seed=61027)
(ROOT/'data/preflop/preflop_regenerated.json').write_text(json.dumps(result,indent=2))
print('preflop',len(rows),'hands;',result['seconds'],'s; simultaneous width',result['simultaneous_hoeffding_half_width'])
