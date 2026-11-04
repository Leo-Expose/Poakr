#!/usr/bin/env python3
"""External validation launcher, NOT submitted bot code.
Invoked by the supplied engine's --python option. Preserves protocol stdout,
constrains both child processes, and emits one probe record to captured stderr.
Python audit hooks are not OS sandbox isolation. Library/source loading is read.
"""
import os
import sys
import time
import resource
import runpy
import json

start=time.monotonic()
sys.dont_write_bytecode=True
os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
resource.setrlimit(resource.RLIMIT_AS,(1<<30,1<<30))
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[key]='1'
forbidden=[]

def audit(event,args):
    if event.startswith(('socket.','subprocess.')) or event in ('os.system','os.fork','os.posix_spawn'):
        forbidden.append(event);raise RuntimeError('forbidden runtime operation: '+event)
    if event=='open':
        _,mode,flags=args
        if (isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)):
            forbidden.append(event);raise RuntimeError('runtime file write forbidden')

sys.addaudithook(audit)
ns=runpy.run_path(sys.argv[1],run_name='resource_validation')
ready=time.monotonic()-start
bot=ns['discard_main']() if 'discard_main' in ns else ns['main']()
meta=dict(validation_probe=True,ready_s=ready,peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
          affinity=list(os.sched_getaffinity(0)),address_space_limit_bytes=1<<30,
          forbidden_attempts=forbidden,python=sys.version.split()[0])
if bot is not None:
    meta.update(errors=bot.errors,score_trusted=bot.score_trusted,score=bot.score,completed=bot.completed,
                proof_arms=bot.proof_arms,protected_floor=bot.reserve,lock_actions=bot.lock_actions)
print(json.dumps(meta,separators=(',',':')),file=sys.stderr,flush=True)
