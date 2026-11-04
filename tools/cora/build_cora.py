"""Bundle audited core helpers + research + embedded table for EXAMPLE protocol.
The duplicate-hole inference implementation and previous protocol entry point
are deliberately omitted. No runtime package or table-file imports are needed.
"""
import ast,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
base=(ROOT/'runtime/bot.py').read_text();lines=base.splitlines();remove=set()
omit={'HandRecord','DuplicateMemory','ExampleAdapter','rules_from_dict','settings_from_dict','main'}
def erase(node):
    start=min([node.lineno]+[d.lineno for d in getattr(node,'decorator_list',[])])
    remove.update(range(start,node.end_lineno+1))
for node in ast.parse(base).body:
    if isinstance(node,(ast.ClassDef,ast.FunctionDef)) and node.name in omit:erase(node)
    elif isinstance(node,ast.If) and isinstance(node.test,ast.Compare) and isinstance(node.test.left,ast.Name) and node.test.left.id=='__name__':erase(node)
    elif isinstance(node,ast.ClassDef) and node.name=='BotSession':
        for method in node.body:
            if isinstance(method,ast.FunctionDef) and method.name!='__init__':erase(method)
base='\n'.join(line for i,line in enumerate(lines,1) if i not in remove)+'\n'
base=base.replace('PROGRAM_START=time.perf_counter()','import sys\nPROGRAM_START=time.perf_counter()\nsys.dont_write_bytecode=True')
base=base.replace('self.duplicate=DuplicateMemory(rules,settings);',"self.duplicate=SimpleNamespace(history={});")
base=base.replace("integer(seed,'seed',0,2**64-1)","integer(seed,'seed',0,2**64-1)\n        if settings.duplicate_mode!='off':raise ValidationError('CORA excludes duplicate-hole inference')")
base=base.replace('Pokerbot v2: configurable core + EXAMPLE JSONL adapter (not official protocol).','CORA research: standard Holdem EXAMPLE JSONL adapter, NOT official protocol.').replace('Runtime: Python 3.11,','Target: Python 3.11 (execution qualification pending),')
parts=[base,'\n# Research modules share embedded helpers; no package imports.\nfrom types import SimpleNamespace\ncore=sys.modules[__name__]\n']
for name in ('kernels.py','agent.py','stream_adapter.py'):
    text=(ROOT/'research'/name).read_text();lines=text.splitlines();remove=set()
    for node in ast.parse(text).body:
        if isinstance(node,ast.FunctionDef) and node.name=='load_preflop':
            remove.update(range(node.lineno,node.end_lineno+1))
        if isinstance(node,ast.ImportFrom) and (node.module in ('__future__','pathlib') or node.module.startswith(('runtime','research'))):
            remove.update(range(node.lineno,node.end_lineno+1))
        if isinstance(node,ast.Expr) and isinstance(node.value,ast.Constant) and isinstance(node.value.value,str):
            remove.update(range(node.lineno,node.end_lineno+1))
    parts.append('\n# RESEARCH SOURCE: '+name+'\n'+'\n'.join(line for i,line in enumerate(lines,1) if i not in remove)+'\n')
rows=json.loads((ROOT/'data/preflop/preflop.json').read_text())['rows']
parts.append('\nEMBEDDED_PREFLOP={'+','.join(repr((a,b,s))+':'+repr(q) for a,b,s,q in rows)+'}\n')
parts.append("BOOT_COST=time.perf_counter()-PROGRAM_START\nif __name__=='__main__':\n    cora_main(EMBEDDED_PREFLOP,BOOT_COST)\n")
code=''.join(parts);ast.parse(code,feature_version=(3,11));out=ROOT/'releases/cora/current/cora_bot.py';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(code)
print('Built',len(code.encode()),'bytes; SHA256',hashlib.sha256(code.encode()).hexdigest())
