"""Run exact toy-poker verification. Never modifies the frozen controller."""
import os,sys,json,time,resource
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
resource.setrlimit(resource.RLIMIT_AS,(1<<30,1<<30))
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
from research.guarantee_lab.kuhn import solve
from research.guarantee_lab.certificates import BoundSchedule,Contract
start=time.perf_counter();result=solve()
contract=Contract(True,True,True,True,True)
raw=BoundSchedule([1,3,5],contract);cap=BoundSchedule([1,3,5],contract,hand_cap=2)
result['certificate_examples']={
    'raw_variable_posts':str(raw.certify(15,4,0).lower_score),
    'per_hand_cap_2_banked_capped_score_10':str(cap.certify(10,4,0).lower_score),
    'warning':'raw and capped inputs are different scoreboards; no organizer formula assumed'}
from research.kernels import RiverKernel
from research.guarantee_lab.river_credit import prove_river_credit,RiverContract
rc=RiverContract(*([True]*7));schedule=BoundSchedule([2,3,5],contract)
tie=prove_river_credit(RiverKernel([35,39,43,47,51]),[0,1],70,rc)
nuts=prove_river_credit(RiverKernel([35,39,43,0,5]),[47,51],70,rc)
result['river_settlement_examples']={
    'shared_royal_tie_old_abandonment_bound':str(schedule.certify(10,50,0).lower_score),
    'shared_royal_tie_safe_settlement_bound':str(schedule.certify_river_settlement(10,tie,0).lower_score),
    'unique_royal_with_negative_banked_net':str(schedule.certify_river_settlement(-60,nuts,0).lower_score),
    'all_legal_peer_hands_checked':nuts.legal_peer_hands,
    'current_policy':nuts.required_current_policy,'later_policy':nuts.required_later_policy,
    'integrated_into_frozen_bot':False}
from research.guarantee_lab.turn_credit import prove_turn_credit,TurnContract
turn=prove_turn_credit((28,29),(30,31,0,5),70,TurnContract(*([True]*7)))
result['symbolic_turn_example']={
    'own_cards':['9c','9d'],'public_turn':['9h','9s','2c','3d'],
    'minimum_current_net':str(turn.minimum_current_net),
    'guaranteed_final_raw_bound':str(schedule.certify_safe_settlement(-60,turn,0).lower_score),
    'physical_opponent_pairs':turn.legal_peer_hands,'possible_pair_runout_worlds':45540,
    'runtime_enumerates_runouts':False,'exhaustive_world_check':'tests/cora/test_guarantees.py',
    'current_policy':turn.required_current_policy,'integrated_into_frozen_bot':False}
result.update(wall_s=time.perf_counter()-start,peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
              cpu_affinity=list(os.sched_getaffinity(0)),address_space_limit_bytes=1<<30,
              guarantee='state-conditional under verified premises; no initial-state universal victory')
out=ROOT/'evidence/guarantee_lab';out.mkdir(parents=True,exist_ok=True)
(out/'results.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
