"""End-to-end checks against a running backend. No local API keys needed."""
import argparse
import json
import urllib.request
import urllib.error
import uuid

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('base', nargs='?', default='http://localhost:8000')
args = parser.parse_args()
base = args.base.rstrip('/')
run = uuid.uuid4().hex[:10]

def call(path, body=None, simulation=None):
    headers = {'Content-Type':'application/json'}
    if simulation: headers['X-Simulate-Failure'] = simulation
    req = urllib.request.Request(base+path, data=json.dumps(body).encode() if body is not None else None, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)

def chat(suffix, message, simulation=None):
    return call('/chat', {'session_id':f's-{run}-{suffix}','message':message}, simulation)

def check(condition, label):
    if not condition: raise AssertionError(label)
    print('PASS', label, flush=True)

code, health = call('/health'); print(json.dumps(health, indent=2))
check(code == 200 and health['keys_configured'] >= 2 and health['cache_enabled'] is True, 'health')
message = f'What is the capital of France? Answer in one sentence. Reference {run}.'
code, first = chat('a', message); check(code==200, f'live response: {first}')
print(json.dumps(first, indent=2))
code, cached = chat('b', message); check(code==200, f'cache response: {cached}')
print(json.dumps(cached, indent=2))
a,b = first['metadata'],cached['metadata']
check(a['resolution_source']=='LIVE_INFERENCE' and b['resolution_source']=='LLM_CACHE','live then cache')
check(first['reply']==cached['reply'] and b['key_id'] is None and b['fallback_attempts']==0,'cache identical; no provider key')
check(all(a[k]==b[k] and isinstance(a[k],int) for k in ('input_tokens','output_tokens')),'stored request token usage')
check(b['latency_ms']<a['latency_ms'],'cache faster')
code, nxt=chat('a','What country did I ask about? Answer only with its name.')
check(code==200 and 'france' in nxt['reply'].lower(),'multi-turn context')
for status in (429,500):
    code, fallback=chat(f'failover-{status}',f'What is 2 + 2? Reference {run}-{status}.',f'key_1={status}')
    print(json.dumps(fallback,indent=2))
    check(code==200 and fallback['metadata']['key_id']=='key_2' and fallback['metadata']['fallback_attempts']==1,f'key_1 {status} -> key_2')
code, failed=chat('a','Do not save this turn.','*=429')
check(code==503 and failed=={'detail':'all providers unavailable'},'all keys failed, clean 503')
code, hist=call(f'/sessions/s-{run}-a/messages')
check(code==200 and len(hist['messages'])==4,'history has only successful turns')
print(json.dumps(hist,indent=2))
code, invalid=chat('invalid','   '); check(code==422 and 'detail' in invalid,'validation 422')
code, unknown=call(f'/sessions/s-{run}-invalid/messages');check(code==404,'failed request not saved; unknown 404')
print(f'All checks complete. Persistence test session: s-{run}-a')
