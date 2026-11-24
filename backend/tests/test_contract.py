import time
from types import SimpleNamespace as NS
from dataclasses import replace
import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.gateway import Gateway
from app.main import create_app

class MemoryCache:
    """Test double, not used by deployed application."""
    def __init__(self): self.values = {}
    def get_cache(self, cache_key): return self.values.get(cache_key)
    def add_cache(self, result, cache_key): self.values[cache_key] = result.copy()

class Provider:
    def __init__(self): self.calls = []; self.fail = {}
    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs['api_key'] in self.fail:
            exc = RuntimeError('private upstream detail'); exc.status_code = self.fail[kwargs['api_key']]; raise exc
        time.sleep(.025)
        messages = kwargs['messages']
        content = ' | '.join(m['content'] for m in messages if m['role'] == 'user')
        return NS(choices=[NS(message=NS(content=content))],usage=NS(prompt_tokens=sum(len(m['content'].split()) for m in messages),completion_tokens=len(content.split())))

@pytest.fixture
def setup(tmp_path):
    cfg = Settings(('secret-one','secret-two'),'test/model',f'sqlite:///{tmp_path / "app.db"}',('http://localhost:3000',),True)
    provider = Provider(); gateway = Gateway(cfg, provider, MemoryCache())
    with TestClient(create_app(cfg,gateway)) as client:
        yield client, provider, cfg

def chat(c,s='s1',m='Hello there',header=None,**extra):
    return c.post('/chat',json={'session_id':s,'message':m,**extra},headers={'X-Simulate-Failure':header} if header is not None else {})

def test_health(setup):
    c,p,_=setup
    assert c.get('/health').json()=={'status':'ok','keys_configured':2,'cache_enabled':True}
    assert c.get('/docs').status_code==404

def test_cache_context_and_token_usage(setup):
    c,p,_=setup
    a=chat(c).json(); b=chat(c,'s2').json()
    assert a['metadata']['resolution_source']=='LIVE_INFERENCE'
    assert b['metadata']['resolution_source']=='LLM_CACHE'
    assert a['reply']==b['reply'] and b['metadata']['key_id'] is None and b['metadata']['fallback_attempts']==0
    for field in ['input_tokens','output_tokens','model']: assert a['metadata'][field]==b['metadata'][field]
    assert b['metadata']['latency_ms'] < a['metadata']['latency_ms']
    assert len(p.calls)==1
    d=chat(c,'s3','Different words').json(); assert d['metadata']['resolution_source']=='LIVE_INFERENCE'
    assert d['metadata']['input_tokens']==a['metadata']['input_tokens']
    e=chat(c,'s1','Remember me?').json(); assert e['metadata']['resolution_source']=='LIVE_INFERENCE'
    assert 'Hello there' in e['reply'] and len(p.calls[-1]['messages'])==4
    assert c.get('/sessions/s1/messages').json()['messages'][1]['metadata']==a['metadata']
    assert len(c.get('/sessions/s1/messages').json()['messages'])==4
    assert len(c.get('/sessions/s2/messages').json()['messages'])==2

def test_prompt_persists_and_changes_cache_key(setup):
    c,p,_=setup
    chat(c,'a',system_prompt='Speak briefly')
    assert chat(c,'b',system_prompt='Speak formally').json()['metadata']['resolution_source']=='LIVE_INFERENCE'
    assert chat(c,'c',system_prompt='Speak briefly').json()['metadata']['resolution_source']=='LLM_CACHE'
    chat(c,'a','Next')
    assert p.calls[-1]['messages'][0]['content']=='Speak briefly'
    assert all(m['role']!='system' for m in c.get('/sessions/a/messages').json()['messages'])

@pytest.mark.parametrize('status',[429,500,502,503])
def test_simulated_fallback(setup,status):
    c,p,_=setup
    r=chat(c,header=f'key_1={status}'); assert r.status_code==200
    assert r.json()['metadata']['key_id']=='key_2' and r.json()['metadata']['fallback_attempts']==1
    assert p.calls[-1]['api_key']=='secret-two' and len(p.calls)==1
    assert 'secret-two' not in r.text
    assert chat(c,'s2').json()['metadata']['key_id']=='key_1'

@pytest.mark.parametrize('status',[429,500,502,503])
def test_actual_provider_error_fallback(setup,status):
    c,p,_=setup; p.fail['secret-one']=status
    r=chat(c); assert r.status_code==200 and r.json()['metadata']['key_id']=='key_2'
    assert r.json()['metadata']['fallback_attempts']==1 and len(p.calls)==2
    assert 'private upstream detail' not in r.text

@pytest.mark.parametrize('header',['*=429','key_1=429,key_2=500'])
def test_all_failed_rollback_even_if_cached(setup,header):
    c,p,_=setup; chat(c)
    r=chat(c,'new',header=header); assert r.status_code==503 and r.json()=={'detail':'all providers unavailable'}
    assert c.get('/sessions/new/messages').status_code==404
    assert chat(c,'s1','fail',header=header).status_code==503
    assert len(c.get('/sessions/s1/messages').json()['messages'])==2
    assert len(p.calls)==1

def test_actual_all_failed(setup):
    c,p,_=setup; p.fail={'secret-one':429,'secret-two':500}
    assert chat(c).json()=={'detail':'all providers unavailable'}
    assert c.get('/sessions/s1/messages').status_code==404

@pytest.mark.parametrize('body',[{}, {'session_id':'s','message':'   '},{'session_id':'','message':'x'},{'session_id':'  ','message':'x'},{'session_id':'x'*129,'message':'x'},{'session_id':'s','message':'x'*4001},{'session_id':'s','message':4}])
def test_validation(setup,body):
    c,p,_=setup; r=c.post('/chat',json=body)
    assert r.status_code==422 and 'detail' in r.json() and not p.calls
    assert c.get('/sessions/s/messages').status_code==404

def test_malformed_json_and_header(setup):
    c,p,_=setup
    assert c.post('/chat',content='{',headers={'Content-Type':'application/json'}).status_code==422
    assert chat(c,header='key_1=404').status_code==422
    assert c.get('/sessions/s1/messages').status_code==404

def test_persistence_and_disabled_simulation(setup):
    c,p,cfg=setup; chat(c)
    changed=replace(cfg,simulate=False)
    with TestClient(create_app(changed, Gateway(changed,p,MemoryCache()))) as reopened:
        assert len(reopened.get('/sessions/s1/messages').json()['messages'])==2
        assert chat(reopened,'s2',header='*=429').json()['metadata']['key_id']=='key_1'

def test_real_litellm_cache_when_installed(setup):
    pytest.importorskip('litellm')
    from litellm.caching.caching import Cache
    _,p,cfg=setup
    with TestClient(create_app(cfg,Gateway(cfg,p,Cache(type='local',ttl=60)))) as client:
        a=chat(client,'actual-cache-a','cache integration').json(); b=chat(client,'actual-cache-b','cache integration').json()
        assert a['metadata']['resolution_source']=='LIVE_INFERENCE'
        assert b['metadata']['resolution_source']=='LLM_CACHE' and a['reply']==b['reply']
