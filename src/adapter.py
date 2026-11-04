"""EXAMPLE JSONL adapter, not the organizer's undisclosed stdin/stdout grammar.
Translate the official protocol here. Core actions express chips paid now.
No output is produced for status/start/end messages. Exactly one JSON action is
emitted for each valid decision; malformed inputs are reported to stderr only
unless a valid advertised legal set supplies a fallback.
"""
import sys
import time
import json
import argparse
from .core import (Rules, Settings, BotSession, Observation, Action, ValidationError,
                   safe_action, number, integer, identifier)

MAX_LINE_BYTES = 131072



def strict_json(text):
    def pairs(items):
        out={}
        for key,value in items:
            if key in out: raise ValidationError('duplicate JSON key')
            out[key]=value
        return out
    def constant(value): raise ValidationError('nonfinite JSON')
    return json.loads(text,object_pairs_hook=pairs,parse_constant=constant)


def rules_from_dict(value):
    if not isinstance(value,dict): raise ValidationError('rules must be an object')
    known=set(Rules.__dataclass_fields__)
    if set(value)-known: raise ValidationError('unknown rule fields')
    data=dict(value)
    for k in ('board_by_street','category_order'):
        if k in data: data[k]=tuple(data[k])
    if data.get('straight_patterns') is not None:
        data['straight_patterns']=tuple((tuple(ranks),high) for ranks,high in data['straight_patterns'])
    return Rules(**data)


def settings_from_dict(value):
    if not isinstance(value,dict) or set(value)-set(Settings.__dataclass_fields__):
        raise ValidationError('unknown setting fields')
    return Settings(**value)


def legal_from_json(values):
    if not isinstance(values,list) or not 1<=len(values)<=64: raise ValidationError('legal must be a nonempty bounded list')
    actions=[]
    for item in values:
        if not isinstance(item,dict) or set(item)-{'kind','pay'}: raise ValidationError('invalid action object')
        actions.append(Action(item.get('kind'),number(item.get('pay',0),'pay')))
    if len(set(actions))!=len(actions): raise ValidationError('duplicate legal action')
    return tuple(actions)


def observation_from_json(obj,rules):
    legal=legal_from_json(obj.get('legal'))
    hands_left=obj.get('hands_left')
    if hands_left is not None: hands_left=integer(hands_left,'hands_left')
    pair=obj.get('pair_id')
    return Observation(
        request_id=identifier(obj.get('request_id'),'request_id'),
        hand_id=identifier(obj.get('hand_id'),'hand_id'),
        hole=tuple(sorted(rules.cards(obj.get('hole')))),
        board=rules.cards(obj.get('board')),
        pot=number(obj.get('pot'),'pot'),to_call=number(obj.get('to_call'),'to_call'),
        my_stack=number(obj.get('my_stack'),'my_stack'),opp_stack=number(obj.get('opp_stack'),'opp_stack'),
        legal=legal,pair_id=identifier(pair,'pair_id') if pair is not None else None,
        chip_lead=number(obj.get('chip_lead',0),'chip_lead',-1e12),hands_left=hands_left)


def action_response(request_id,action):
    value={'kind':action.kind}
    if action.kind=='bet': value['pay']=action.pay
    return {'type':'action','request_id':request_id,'action':value}


class ExampleAdapter:
    def __init__(self,rules=Rules(),settings=Settings(),seed=0,boot_cost=0):
        self.rules=rules; self.settings=settings; self.seed=seed
        self.boot_cost=boot_cost; self.session=None; self.completed=set(); self.failures=0
    def handle(self,obj):
        if not isinstance(obj,dict): raise ValidationError('message must be object')
        kind=obj.get('type')
        if kind=='start_match':
            mid=identifier(obj.get('match_id'),'match_id')
            if self.session is not None and self.session.match_id==mid:
                raise ValidationError('duplicate start_match must not reset state or bank')
            if self.session is not None: raise ValidationError('end current match before starting another')
            if mid in self.completed: raise ValidationError('match ID reused')
            self.session=BotSession(mid,self.rules,self.settings,
                                    integer(obj.get('hands_total'),'hands_total',1,100_000),
                                    number(obj.get('timebank_s'),'timebank_s',0.01),self.seed)
            self.session.bank.charge(self.boot_cost); self.boot_cost=0
            return None
        if kind not in ('decision','opponent_event','showdown','hand_end','status','end_match'):
            raise ValidationError('unknown message type')
        if self.session is None: raise ValidationError('start_match required')
        session=self.session
        if identifier(obj.get('match_id'),'match_id')!=session.match_id:
            raise ValidationError('wrong match_id')
        if 'time_left_s' in obj: session.bank.update_host(number(obj['time_left_s'],'time_left_s'))
        if kind=='end_match':
            self.completed.add(session.match_id)
            if len(self.completed)>256: raise ValidationError('too many matches in one process')
            self.session=None; return None
        if kind=='opponent_event':
            session.opponent.observe(integer(obj.get('seq'),'seq'),integer(obj.get('street'),'street',0,len(self.rules.board_by_street)),
                                     obj.get('kind'),obj.get('faced_bet'),number(obj.get('faced_ratio',0),'faced_ratio'))
            return None
        if kind in ('showdown','hand_end'):
            hand_id=identifier(obj.get('hand_id'),'hand_id')
            opponent=self.rules.cards(obj['opponent_hole']) if 'opponent_hole' in obj else None
            session.duplicate.finish_hand(hand_id,obj.get('board'),opponent)
            return None
        if kind=='status': return None
        obs=observation_from_json(obj,self.rules)
        action=session.act(obs,charge=False)
        return action_response(obs.request_id,action)

    def fallback(self,obj):
        # Never invent an action, sizing, request ID, or match when parsing fails.
        if not isinstance(obj,dict) or obj.get('type')!='decision' or self.session is None:
            return None
        try:
            if identifier(obj.get('match_id'),'match_id')!=self.session.match_id: return None
            legal=legal_from_json(obj.get('legal'))
            request_id=identifier(obj.get('request_id'),'request_id')
            if self.session.responses.get(request_id) is not None:
                # A conflicting payload under an old ID is an error, not a new action.
                return None
            return action_response(request_id,safe_action(legal))
        except (ValueError,TypeError): return None


def read_bounded_lines(stream):
    while True:
        line=stream.readline(MAX_LINE_BYTES+1)
        if not line: return
        if len(line)>MAX_LINE_BYTES:
            while line and not line.endswith('\n'): line=stream.readline(MAX_LINE_BYTES+1)
            yield None
        else: yield line


def main(argv=None):
    parser=argparse.ArgumentParser(description='Example JSONL poker adapter — not an official protocol implementation')
    parser.add_argument('--config',help='read-only JSON configuration file')
    parser.add_argument('--seed',type=int,default=0)
    args=parser.parse_args(argv)
    rules,settings=Rules(),Settings()
    if args.config:
        with open(args.config,'r',encoding='utf-8') as f:
            text=f.read(MAX_LINE_BYTES+1)
        if len(text)>MAX_LINE_BYTES: raise ValidationError('config too large')
        config=strict_json(text)
        if not isinstance(config,dict) or set(config)-{'rules','settings'}: raise ValidationError('invalid config')
        rules=rules_from_dict(config.get('rules',{})); settings=settings_from_dict(config.get('settings',{}))
    adapter=ExampleAdapter(rules,settings,args.seed,globals().get('BOOT_COST',0))
    for line in read_bounded_lines(sys.stdin):
        start=time.perf_counter(); obj=None; prior=adapter.session
        try:
            if line is None: raise ValidationError('line too large')
            if not line.strip(): continue
            obj=strict_json(line)
            response=adapter.handle(obj)
        except Exception as exc:
            adapter.failures+=1
            if adapter.session: adapter.session.errors+=1
            response=adapter.fallback(obj)
            # Bounded diagnostics only, never traceback/prose on stdout.
            sys.stderr.write('input_error:'+type(exc).__name__+'\n')
        try:
            if response is not None:
                sys.stdout.write(json.dumps(response,allow_nan=False,separators=(',',':'))+'\n')
                sys.stdout.flush()
        finally:
            target=adapter.session if adapter.session is not None else prior
            if target: target.bank.charge(time.perf_counter()-start)


if __name__=='__main__':
    main()
