import json, math, os
import pytest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from starter.app import app,analyse
D=json.loads(Path('03_Data.json').read_text(encoding='utf-8'))
client=TestClient(app)
@pytest.fixture(autouse=True)
def classroom_test_configuration():
 from starter.security import limiter
 with limiter.lock: limiter.events.clear()
 client.headers['X-Classroom-Code']='unit-test-demo-code'
 with patch.dict(os.environ,{'CLASSROOM_DEMO_CODE':'unit-test-demo-code'}):
  yield
def test_fixture():
 f=D['calculation_fixture'];a=analyse(f['text'])
 for k in ['words','sentences','types']: assert a['counts'][k]==f[k]
 for k in ['TTR','MATTR_50','mean_sentence_length']:assert a['metrics'][k]==f[k]
def test_syntax():
 a=analyse(D['manual_syntax_fixture']['text'])
 assert a['metrics']['finite_clauses_per_sentence_proxy']==2
 assert a['metrics']['dependent_finite_clauses_per_clause_proxy']==.5
def test_readability_formula():
 f=D['synthetic_readability_fixture'];assert round(206.835-1.015*f['words']/f['sentences']-84.6*f['syllables']/f['words'],2)==f['FRE']
def test_samples_and_offsets():
 for s in D['samples']:
  a=analyse(s['text']);assert a['counts']['words']>200
  for f in a['flags']:assert s['text'][f['start']:f['end']]==f['span']
 assert len(analyse(D['samples'][1]['text'])['flags'])==4
 assert analyse(D['samples'][2]['text'])['flags']==[]
def test_empty_limits():
 for text in ['', '   ', '123 !!!']:assert client.post('/api/analyse',json={'text':text}).status_code==400
 assert client.post('/api/analyse',json={'text':'a'*20001}).status_code==422
def test_fallback():
 b={'sentence':'Some feedback are too general.','audience':'Students','purpose':'Explain service','focus':'grammar'}
 with patch.dict(os.environ,{'ANTROUTER_API_KEY':''}):
  a=client.post('/api/hint',json=b).json();assert a['source']=='rule';assert 'agreement' in a['hint']
 with patch('starter.hints.httpx.post',side_effect=__import__('httpx').ConnectError('offline')):
  a=client.post('/api/hint',json=b).json();assert a['source']=='rule';assert 'AI' in a['status']
 assert client.post('/api/hint',json={**b,'sentence':'!!!'}).status_code==400

def test_ai_payload_and_output():
 import httpx
 b={'sentence':'Cats sleep.','audience':'Students','purpose':'Explain habits','focus':'clarity'}
 response=httpx.Response(200,json={'choices':[{'message':{'content':json.dumps({'quote':b['sentence'],'hint':'Consider one specific detail.','example':'Cats sleep in warm places.'})}}]},request=httpx.Request('POST','https://api.antrouter.io/v1/chat/completions'))
 with patch.dict(os.environ,{'ANTROUTER_API_KEY':'test-only-placeholder'}),patch('starter.hints.httpx.post',return_value=response) as post:
  result=client.post('/api/hint',json=b).json()
  assert result['source']=='ai'
  payload=json.loads(post.call_args.kwargs['json']['messages'][1]['content'])
  assert set(payload)=={'sentence','audience','purpose','focus','metrics','counts'}
  assert payload['sentence']==b['sentence']
  assert payload['counts']['words']==2
