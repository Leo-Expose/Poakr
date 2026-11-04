"""Build single-file protocol-1.0 candidate without runtime workspace imports."""
import ast
import hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
header='''#!/usr/bin/env python3
"""Discard Hold'em protocol 1.0 candidate. Organizer-runner certification pending.
Target Python 3.11; stdlib + NumPy only. No runtime file, network or process I/O.
"""
import sys, os
sys.dont_write_bytecode=True
for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[_key]='1'
'''
import argparse
parser=argparse.ArgumentParser();parser.add_argument('--experimental',action='store_true');args=parser.parse_args()
parts=[header]
names=['engine/numpy_eval.py','research/discard_holdem/proofs.py','research/discard_holdem/protocol.py']
if args.experimental:names+=['research/discard_holdem/partial_eval.py','research/discard_holdem/adaptive.py']
for name in names:
    text=(ROOT/name).read_text();lines=text.splitlines();remove=set()
    for node in ast.parse(text).body:
        omit=(isinstance(node,ast.ImportFrom) and node.module and node.module.startswith(('engine','research')))
        omit|=(name=='engine/numpy_eval.py' and isinstance(node,ast.FunctionDef) and node.name in ('showdown_batch','equity_vs_random_batch'))
        omit|=(isinstance(node,ast.Expr) and isinstance(node.value,ast.Constant) and isinstance(node.value.value,str))
        if omit:remove.update(range(node.lineno,node.end_lineno+1))
    parts.append('\n# SOURCE '+name+'\n'+'\n'.join(line for i,line in enumerate(lines,1) if i not in remove)+'\n')
if args.experimental:parts.append('\nDiscardBot=AdaptiveDiscardBot\n')
parts.append("\nif __name__=='__main__':\n    discard_main()\n")
code=''.join(parts);ast.parse(code,feature_version=(3,11))
out=ROOT/('releases/discard/experimental/bot.py' if args.experimental else 'releases/discard/current/bot.py');out.parent.mkdir(parents=True,exist_ok=True);out.write_text(code)
print(out,len(code.encode()),hashlib.sha256(code.encode()).hexdigest())
