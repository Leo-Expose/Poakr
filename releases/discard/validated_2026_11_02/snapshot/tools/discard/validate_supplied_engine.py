"""Measure the supplied engine without editing its source or disabling clocks.
External subclass records raw request-to-received-line latency, independently of
its first-five-seconds charging behavior. No extra information reaches either bot.
"""
import sys
import os
import json
import time
import hashlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[2]
ENGINE=ROOT/'vendor/organizer/Starter_Kit/engine.py'
spec=importlib.util.spec_from_file_location('supplied_engine_validation',ENGINE)
engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


class MeasuredBot(engine.Bot):
    def __init__(self,*args,**kwargs):
        self.raw_latencies=[];self.first_five_latencies=[];self.latest_receipt=None
        self.discard_requests=0;self.action_requests=0
        super().__init__(*args,**kwargs)
    def _read_stdout(self):
        for raw in self.proc.stdout:
            ts=time.monotonic();line=raw.decode('utf-8','replace').rstrip('\r\n')
            self.latest_receipt=(ts,line)
            self.lines.put((ts,line))
        self.lines.put((time.monotonic(),None))
    def begin(self,msg):
        if msg['type']=='discard_request':self.discard_requests+=1
        if msg['type']=='action_request':self.action_requests+=1
        super().begin(msg)
    def wait_reply(self,wall_deadline):
        line,error=super().wait_reply(wall_deadline)
        if error is None:
            ts,received=self.latest_receipt
            assert received==line and ts>=self.sent_at,'unexpected extra protocol output'
            latency=max(0,ts-self.sent_at)
            self.raw_latencies.append(latency)
            if self.sent_at<self.startup_deadline:self.first_five_latencies.append(latency)
        return line,error


def run(stage,opponent,seed,label,candidate_position='A'):
    folder=ROOT/'evidence/organizer_runner/measured'/label
    if folder.exists():raise ValueError('fresh evidence label required; do not overwrite a validated run')
    folder.mkdir(parents=True)
    candidate=ROOT/'releases/discard/v1/bot.py'
    opponent=Path(opponent).resolve()
    a,b=(candidate,opponent) if candidate_position=='A' else (opponent,candidate)
    args=SimpleNamespace(stage=stage,hands=None,seed=str(seed),verbose=False,log_dir=str(folder),
                         no_time_limits=False,bot_a=str(a),bot_b=str(b),
                         python=str(ROOT/'tools/discard/resource_launcher.py'))
    original=engine.Bot;engine.Bot=MeasuredBot
    try:
        match=engine.Match(args);start=time.monotonic();match.run();wall=time.monotonic()-start
    finally:engine.Bot=original
    text=(folder/'match.log').read_text()
    assert f"{engine.STAGES[stage]['hands']} of {engine.STAGES[stage]['hands']} hands played" in text
    assert 'forfeited at hand' not in text
    candidate_index=0 if candidate_position=='A' else 1
    all_meta=[]
    for bot in match.bots:
        stderr=(folder/(bot.name+'_stderr.txt')).read_text().strip()
        meta=json.loads(stderr)
        assert meta['validation_probe'] and not meta['forbidden_attempts'] and meta['ready_s']<5
        if 'errors' in meta:assert meta['errors']==0 and meta['score_trusted'] and meta['completed']==match.hands
        all_meta.append(meta)
        assert bot.notices==0
        # Strict raw timing includes startup on the first reply. It is separate
        # from the vendor's bank rule and does not depend on free early requests.
        assert sum(bot.raw_latencies)<engine.STAGES[stage]['time_bank_ms']/1000
        assert max(bot.raw_latencies)<5
    candidate_bot=match.bots[candidate_index]
    result=dict(stage=stage,hands=match.hands,seed=str(seed),candidate_position=candidate_position,
                candidate_sha256=sha(candidate),opponent=str(opponent.relative_to(ROOT)),opponent_sha256=sha(opponent),
                engine_sha256=sha(ENGINE),launcher_sha256=sha(ROOT/'tools/discard/resource_launcher.py'),
                measurement_driver_sha256=sha(Path(__file__)),engine_source_modified=False,time_limits_disabled=False,
                wall_s=wall,raw_request_s=sum(candidate_bot.raw_latencies),max_raw_reply_s=max(candidate_bot.raw_latencies),
                engine_charged_s=candidate_bot.time_used_s,raw_first_five_seconds_s=sum(candidate_bot.first_five_latencies),
                requests=len(candidate_bot.raw_latencies),action_requests=candidate_bot.action_requests,
                discard_requests=candidate_bot.discard_requests,notices=candidate_bot.notices,
                candidate_probe=all_meta[candidate_index],other_probe=all_meta[1-candidate_index],
                result_summary=text[text.rfind('\nSeed '):].strip(),
                scope='supplied starter engine; external measurement/resource probe; Python audit, not OS sandbox')
    (folder/'measurements.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    return result


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--stage',type=int,choices=(1,2),default=1)
    p.add_argument('--opponent',default=str(ROOT/'vendor/organizer/Starter_Kit/bot.py'))
    p.add_argument('--seed',required=True);p.add_argument('--label',required=True)
    p.add_argument('--candidate-position',choices=('A','B'),default='A');args=p.parse_args()
    if Path(args.label).name!=args.label:raise ValueError('plain label required')
    run(args.stage,args.opponent,args.seed,args.label,args.candidate_position)
