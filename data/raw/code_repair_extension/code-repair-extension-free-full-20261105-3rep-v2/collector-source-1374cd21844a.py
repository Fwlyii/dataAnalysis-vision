"""Resumable free-only API collection with paired initial programs and public diagnostics."""
from __future__ import annotations

import argparse
from collections import Counter, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pickle
import platform
import random
import signal
import sys
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, build_opener, ProxyHandler

from .dataset import ROOT, load_benchmark
from .resource_policy import evaluate_resolved
from .protocol import ARMS, extract_code, feedback_message, initial_prompt
from .prepare import atomic_json, source_hashes


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def resolve(value):
    path=Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (ROOT/path).resolve()


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def identity(model, task_id, replicate, arm, round_):
    return f'{model}|{task_id}|rep{replicate}|{arm}|{round_}'


def read_rows(path):
    if not path.exists():return []
    rows=[]
    for number,line in enumerate(path.read_text().splitlines(),1):
        if line.strip():
            try:rows.append(json.loads(line))
            except ValueError as error:raise ValueError(f'Incomplete JSON line {path.name}:{number}; preserve and repair before resuming.') from error
    return rows


class Lane:
    def __init__(self, config, stop):
        self.stop=stop;self.condition=threading.Condition();self.window=deque()
        self.rpm=float(config['initial_rpm']);self.tpm=float(config['initial_tpm'])
        self.max_rpm=float(config['maximum_rpm']);self.max_tpm=float(config['maximum_tpm'])
        self.cooldown=0.;self.successes=0;self.ratelimits=0;self.last_reduction=0.

    def acquire(self, tokens):
        with self.condition:
            while not self.stop.is_set():
                now=time.monotonic()
                while self.window and now-self.window[0][0]>=60:self.window.popleft()
                if now>=self.cooldown and len(self.window)<max(1,int(self.rpm)) and sum(row[1] for row in self.window)+tokens<=self.tpm:
                    row=[now,tokens];self.window.append(row);return row
                self.condition.wait(timeout=.25)
        return None

    def observe(self, row, usage, status, retry_after=None, error=None):
        with self.condition:
            if usage.get('total_tokens') is not None:row[1]=int(usage['total_tokens'])
            elif status is not None and status!=200:row[1]=0
            if status==429:
                self.ratelimits+=1
                now=time.monotonic()
                if now-self.last_reduction>=60:
                    kind=str(error or '').upper()
                    if 'TPM' in kind:self.tpm=max(20000,self.tpm*.8)
                    elif 'RPM' in kind:self.rpm=max(20,self.rpm*.8)
                    else:self.rpm=max(20,self.rpm*.8);self.tpm=max(20000,self.tpm*.8)
                    self.last_reduction=now
                try:delay=float(retry_after or 30)
                except ValueError:delay=30
                self.cooldown=max(self.cooldown,time.monotonic()+max(2,min(300,delay)))
            elif status==200:
                self.successes+=1
                if self.successes%50==0:
                    self.rpm=min(self.max_rpm,self.rpm*1.08);self.tpm=min(self.max_tpm,self.tpm*1.08)
            self.condition.notify_all()

    def state(self):
        with self.condition:return {'rpm_budget':round(self.rpm),'tpm_budget':round(self.tpm),'rate_limits':self.ratelimits}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True);parser.add_argument('--credential-file')
    parser.add_argument('--pilot',action='store_true');parser.add_argument('--replicate',type=int)
    args=parser.parse_args();config_path=resolve(args.config);config_blob=config_path.read_bytes();config=json.loads(config_blob)
    out=resolve(config['run_dir']);out.mkdir(parents=True,exist_ok=True)
    plan=json.loads((out/'plan.json').read_text());config_sha=digest(config_blob)
    if plan['config_sha256']!=config_sha:raise ValueError('Frozen configuration changed')
    if not json.loads((out/'reference-preflight.json').read_text())['complete']:raise ValueError('All references must preflight before collection')
    if plan['reference_source_hashes']!=source_hashes():raise ValueError('Frozen evaluator/protocol source changed')
    if config.get('feedback_protocol_sha256')!=digest(Path(__file__).with_name('protocol.py').read_bytes()):raise ValueError('Feedback protocol changed')
    if config['arms']!=ARMS or config['rounds']!=5:raise ValueError('Unexpected frozen arms/rounds')
    if not config.get('free_only'):raise ValueError('This run is authorized for free models only')
    pricing=json.loads(resolve(config['pricing_snapshot']).read_text())
    free={m['modelName'] for m in pricing['models'] if str(m.get('price'))=='0' and str(m.get('inputPrice'))=='0' and m.get('status')=='normal'}
    if not set(config['models']).issubset(free) or any(m.startswith('Pro/') for m in config['models']):raise ValueError('Model is not verified free')
    if config['endpoint']!='https://api.siliconflow.cn/v1/chat/completions':raise ValueError('Unexpected credential destination')
    key=os.getenv('SILICONFLOW_API_KEY')
    if not key and args.credential_file:key=resolve(args.credential_file).read_text().strip()
    if not key:raise ValueError('Provide the user-authorized SiliconFlow credential via environment or a private local file')
    (out/'config.json').write_bytes(config_blob)
    collector_blob=Path(__file__).read_bytes()
    (out/('collector-source-'+digest(collector_blob)[:12]+'.py')).write_bytes(collector_blob)
    (out/'collector-source.py').write_bytes(collector_blob)
    lock=(out/'.collector.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    tasks_list,manifest=load_benchmark(config);tasks={task['task_id']:task for task in tasks_list}
    ids=list(plan['task_ids']);replicates=list(plan.get('replicate_ids',range(config['replicates'])))
    if args.pilot:ids=sorted(random.Random(config['schedule_seed']).sample(ids,config['pilot_size']),key=lambda tid:int(tid.split('/')[-1]))
    if args.replicate is not None:
        if args.replicate not in replicates:raise ValueError('Unknown replicate')
        replicates=[args.replicate]
    stop=threading.Event();io_lock=threading.RLock();eval_gate=threading.Semaphore(config['evaluation_concurrency'])
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stop.set())
    raw_list=read_rows(out/'responses.jsonl');evaluated_list=read_rows(out/'evaluations.jsonl')
    raw={r['record_id']:r for r in raw_list};evaluated={r['record_id']:r for r in evaluated_list}
    if len(raw)!=len(raw_list) or len(evaluated)!=len(evaluated_list):raise ValueError('Duplicate saved record ID')
    if any(r['config_sha256']!=config_sha for r in raw.values()):raise ValueError('Saved response protocol mismatch')
    handles={name:(out/(name+'.jsonl')).open('a',encoding='utf-8') for name in ['responses','evaluations','attempts','events']}
    attempt_count=len(read_rows(out/'attempts.jsonl'));api_reservation=0;lanes={m:Lane(config,stop) for m in config['models']}
    rate_override=out/'rate-overrides.json'
    if rate_override.is_file():
        for model,limits in json.loads(rate_override.read_text()).get('models',{}).items():
            if model in lanes:
                lanes[model].tpm=min(lanes[model].tpm,limits.get('tpm',lanes[model].tpm));lanes[model].max_tpm=min(lanes[model].max_tpm,limits.get('maximum_tpm',lanes[model].max_tpm))
    failures=[];started=time.monotonic();oracle_cache={};oracle_lock=threading.Lock()

    def clean(value):
        return str(value).replace(key,'[REDACTED]')[:1800]

    def append(name,row):
        with io_lock:handles[name].write(json.dumps(row,ensure_ascii=False)+'\n');handles[name].flush()

    def event(kind,rid,**kwargs):append('events',{'timestamp':timestamp(),'event_type':kind,'record_id':rid,**kwargs})

    def oracle(tid):
        with oracle_lock:
            if tid not in oracle_cache:
                path=out/'oracles'/(tid.replace('/','_')+'.pkl');blob=path.read_bytes()
                meta=json.loads(path.with_suffix('.json').read_text())
                if meta.get('oracle_sha256')!=digest(blob):raise ValueError('Reference oracle checksum mismatch')
                oracle_cache[tid]=pickle.loads(blob)
            return oracle_cache[tid]

    def score(row):
        rid=row['record_id']
        if rid in evaluated:return evaluated[rid]
        with eval_gate:
            result=evaluate_resolved(config,tasks[row['task_id']],row['code'],oracle(row['task_id']),include_holdout=False,run_dir=out,record_id=rid)
        result={k:row[k] for k in ['record_id','model','task_id','replicate','arm','round']}|result|{'timestamp':timestamp(),'config_sha256':config_sha}
        # Unfinished infrastructure evaluations are not saved as measured FAIL.
        if not result['public'].get('complete',False):
            event('evaluation_incomplete',rid,infrastructure_status=result.get('infrastructure_status'),checked=result['public'].get('cases_checked'))
            raise RuntimeError('Diagnostic execution incomplete: '+rid)
        append('evaluations',result)
        with io_lock:evaluated[rid]=result
        return result

    def job(model,tid,replicate,arm,round_):
        nonlocal api_reservation,attempt_count
        rid=identity(model,tid,replicate,arm,round_)
        if rid in raw:return score(raw[rid])
        if stop.is_set():return None
        parent=None;feedback=None;messages=[{'role':'user','content':initial_prompt(tasks[tid])}]
        if round_ and arm!='resample':
            parent=identity(model,tid,replicate,'seed' if round_==1 else arm,round_-1)
            previous=raw[parent];feedback=feedback_message(arm,evaluated[parent])
            messages=previous['request']['messages']+[{'role':'assistant','content':previous['content']},{'role':'user','content':feedback}]
        payload={'model':model,'messages':messages,'temperature':config['temperature'],'top_p':config['top_p'],'max_tokens':config['max_tokens'],'stream':False}
        if 'Qwen3-' in model:payload['enable_thinking']=config['qwen3_enable_thinking']
        token_estimate=sum(len(m['content']) for m in messages)//3+config['max_tokens']
        for attempt in range(1,config['max_attempts']+1):
            reserved=lanes[model].acquire(token_estimate)
            if reserved is None:return None
            with io_lock:
                if attempt_count+api_reservation>=config['max_api_attempts']:stop.set();raise RuntimeError('Precommitted API attempt cap reached')
                api_reservation+=1
            response=None;error=None;status=None;retry_after=None;provider_trace=None;start=time.monotonic()
            try:
                request=Request(config['endpoint'],data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
                opener=build_opener(ProxyHandler({}))
                with opener.open(request,timeout=config['transport_timeout_s']) as result:
                    status=result.status;response=json.load(result);retry_after=result.headers.get('Retry-After');provider_trace=result.headers.get('x-siliconcloud-trace-id')
                if response.get('model')!=model:raise ValueError('Provider returned a different model')
                content=response['choices'][0]['message'].get('content')
                if not isinstance(content,str) or not content.strip():raise ValueError('Provider returned empty output')
            except HTTPError as exc:
                status=exc.code;retry_after=exc.headers.get('Retry-After');error=clean(exc.read().decode(errors='replace'))
            except Exception as exc:error=clean(type(exc).__name__+': '+str(exc))
            usage=(response or {}).get('usage') or {};lanes[model].observe(reserved,usage,status,retry_after,error)
            with io_lock:attempt_count+=1;api_reservation-=1
            append('attempts',{'timestamp':timestamp(),'record_id':rid,'model':model,'attempt':attempt,'http_status':status,'usage':usage,'error':error,'seconds':round(time.monotonic()-start,3),'provider_trace':provider_trace})
            if error is None:
                content=response['choices'][0]['message']['content'];code=extract_code(content)
                row={'record_id':rid,'batch_id':config['batch_id'],'timestamp':timestamp(),'model':model,'task_id':tid,'replicate':replicate,'arm':arm,'round':round_,
                     'parent_id':parent,'shared_seed_id':identity(model,tid,replicate,'seed',0),'feedback_source_id':parent if arm not in ['resample','self_review','seed'] else None,
                     'feedback':feedback,'request':payload,'response':response,'content':content,'code':code,'code_sha256':digest(code.encode()),'usage':usage,
                     'seconds':round(time.monotonic()-start,3),'finish_reason':response['choices'][0].get('finish_reason'),'config_sha256':config_sha}
                append('responses',row)
                with io_lock:raw[rid]=row
                event('generated',rid,model=model,replicate=replicate,arm=arm,round=round_)
                return score(row)
            if status in [401,402,403]:stop.set();raise RuntimeError('Provider authorization/quota error '+str(status))
            if stop.wait(min(30,2**attempt)):return None
        raise RuntimeError('API retry allowance exhausted for '+rid)

    def block(model,tid,replicate):
        try:
            job(model,tid,replicate,'seed',0)
            if stop.is_set():return
            for round_ in range(1,config['rounds']):
                arms=list(ARMS);random.Random(f'{config["schedule_seed"]}:{model}:{tid}:{replicate}:{round_}').shuffle(arms)
                for arm in arms:
                    if stop.is_set():return
                    job(model,tid,replicate,arm,round_)
        except Exception as error:
            with io_lock:failures.append({'model':model,'task_id':tid,'replicate':replicate,'error':clean(error)})
            event('block_error',identity(model,tid,replicate,'block',0),error=clean(error))

    def progress():
        with io_lock:
            state={'timestamp':timestamp(),'scope':'pilot' if args.pilot else 'full','responses':len(raw),'evaluated':len(evaluated),
                   'expected':config['maximum_physical_responses'],'api_attempts':attempt_count,'by_model':dict(Counter(r['model'] for r in raw.values())),
                   'round_counts':dict(Counter(str(r['round']) for r in raw.values())),'seconds':round(time.monotonic()-started,1),'stopped':stop.is_set(),
                   'failed_blocks':len(failures),'recent_failures':failures[-8:],'limits':{m:lane.state() for m,lane in lanes.items()}}
            atomic_json(out/'collection-status.json',state)
        print(json.dumps(state,ensure_ascii=False),flush=True)

    jobs=[(model,tid,replicate) for tid in ids for replicate in replicates for model in config['models']]
    random.Random(config['schedule_seed']).shuffle(jobs)
    with ThreadPoolExecutor(max_workers=config['max_concurrency']) as pool:
        futures=[pool.submit(block,*job_args) for job_args in jobs]
        while not all(future.done() for future in futures):
            progress();time.sleep(15)
        for future in futures:future.result()
    progress()
    for handle in handles.values():handle.close()
    if failures or stop.is_set():raise SystemExit(2)


if __name__=='__main__':main()
