#!/usr/bin/env python3
"""Deterministically assemble one-file runtime from auditable source components."""
from pathlib import Path
import ast, hashlib
root=Path(__file__).resolve().parent.parent
header='''#!/usr/bin/env python3
"""Pokerbot v2: configurable core + EXAMPLE JSONL adapter (not official protocol).
Runtime: Python 3.11, stdlib + NumPy, no installs/network/runtime file writes.
"""
from __future__ import annotations
import os, time
PROGRAM_START=time.perf_counter()
# Honor 1-vCPU constraints before NumPy loads its numerical backend.
for _thread_key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[_thread_key]='1'
'''
parts=[header]
for name in ('fast_eval.py','core.py','adapter.py'):
    text=(root/'src'/name).read_text()
    lines=text.splitlines()
    # Remove only source-package imports/future directive and module docstrings;
    # build fails if a new source-package dependency is introduced unexpectedly.
    tree=ast.parse(text)
    remove=set()
    for node in tree.body:
        if isinstance(node,ast.ImportFrom) and node.level and (node.level!=1 or node.module not in ('core','fast_eval')):
            raise RuntimeError('unregistered source dependency: '+str(node.module))
        if isinstance(node,ast.ImportFrom) and (node.level or node.module=='__future__'):
            remove.update(range(node.lineno,node.end_lineno+1))
        if isinstance(node,ast.Expr) and isinstance(node.value,ast.Constant) and isinstance(node.value.value,str):
            remove.update(range(node.lineno,node.end_lineno+1))
    text='\n'.join(line for i,line in enumerate(lines,1) if i not in remove)+'\n'
    if name=='adapter.py':
        text=text.replace("if __name__=='__main__':\n    main()", '')
    parts.append('\n# SOURCE: '+name+'\n'+text)
parts.append("\nBOOT_COST=time.perf_counter()-PROGRAM_START\nif __name__=='__main__':\n    main()\n")
result=''.join(parts)
ast.parse(result,feature_version=(3,11))
out=root/'releases/v2/rebuilt/bot.py'; out.parent.mkdir(parents=True,exist_ok=True); out.write_text(result)
print('Built',out,len(result),'bytes',hashlib.sha256(result.encode()).hexdigest())
