"""Public-service controls. Values below are test fixtures, never real secrets."""
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starter.app import app
from starter.security import WindowLimiter, allowed_origins, limiter


@pytest.fixture(autouse=True)
def clean_limiter():
    with limiter.lock:
        limiter.events.clear()


def test_code_gate_no_outbound_call():
    client = TestClient(app)
    body = {'sentence': 'Cats sleep.', 'audience': 'Students', 'purpose': 'Explain', 'focus': 'grammar'}
    with patch.dict(os.environ, {'CLASSROOM_DEMO_CODE': 'classroom-fixture-only'}), patch('starter.hints.httpx.post') as post:
        assert client.post('/api/hint', json=body).status_code == 401
        assert client.post('/api/hint', json=body, headers={'X-Classroom-Code': 'wrong'}).status_code == 401
        post.assert_not_called()
    with patch.dict(os.environ, {'CLASSROOM_DEMO_CODE': ''}), patch('starter.hints.httpx.post') as post:
        assert client.post('/api/hint', json=body).status_code == 503
        post.assert_not_called()


def test_request_length_before_gateway():
    client = TestClient(app)
    with patch.dict(os.environ, {'CLASSROOM_DEMO_CODE': 'classroom-fixture-only'}), patch('starter.hints.httpx.post') as post:
        headers = {'X-Classroom-Code': 'classroom-fixture-only'}
        b = {'sentence': 'a' * 1501, 'audience': 'Students', 'purpose': 'Explain', 'focus': 'grammar'}
        assert client.post('/api/hint', json=b, headers=headers).status_code == 422
        assert client.post('/api/hint', content=b'x' * 8193, headers=headers).status_code == 413
        assert client.post('/api/analyse', content=b'x' * 100001).status_code == 413
        post.assert_not_called()


def test_rate_limit_blocks_gateway_and_sets_retry():
    client = TestClient(app)
    body = {'sentence': 'Cats sleep.', 'audience': 'Students', 'purpose': 'Explain', 'focus': 'grammar'}
    with patch.dict(os.environ, {'CLASSROOM_DEMO_CODE': 'classroom-fixture-only', 'AI_REQUESTS_PER_MINUTE': '2', 'ANTROUTER_API_KEY': ''}):
        headers = {'X-Classroom-Code': 'classroom-fixture-only'}
        assert client.post('/api/hint', json=body, headers=headers).status_code == 200
        assert client.post('/api/hint', json=body, headers=headers).status_code == 200
        response = client.post('/api/hint', json=body, headers=headers)
        assert response.status_code == 429
        assert int(response.headers['Retry-After']) > 0


def test_window_expiry_and_global_ceilings():
    limit = WindowLimiter()
    limit.check('group', 1, now=0)
    with pytest.raises(HTTPException) as e:
        limit.check('group', 1, now=1)
    assert e.value.status_code == 429
    limit.check('group', 1, now=60)
    with patch.dict(os.environ, {'CLASSROOM_DEMO_CODE': 'classroom-fixture-only', 'AI_REQUESTS_PER_MINUTE': '100', 'AI_TOTAL_PER_MINUTE': '1', 'ANTROUTER_API_KEY': ''}):
        c = TestClient(app)
        body = {'sentence': 'Cats sleep.', 'audience': 'Students', 'purpose': 'Explain', 'focus': 'grammar'}
        headers = {'X-Classroom-Code': 'classroom-fixture-only'}
        assert c.post('/api/hint', json=body, headers=headers).status_code == 200
        assert c.post('/api/hint', json=body, headers=headers).status_code == 429


def test_actual_cors_startup_in_fresh_process():
    code = '''
from fastapi.testclient import TestClient
from starter.app import app
c=TestClient(app)
good=c.options('/api/hint',headers={'Origin':'https://dashoufajia.github.io','Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'content-type,x-classroom-code'})
assert good.status_code==200
assert good.headers['access-control-allow-origin']=='https://dashoufajia.github.io'
assert 'access-control-allow-credentials' not in good.headers
bad=c.options('/api/hint',headers={'Origin':'https://untrusted.example','Access-Control-Request-Method':'POST'})
assert bad.status_code==400
assert 'access-control-allow-origin' not in bad.headers
print('Exact Pages origin accepted; other origins rejected.')
'''
    env = {**os.environ, 'APP_ENV': 'production', 'ALLOWED_ORIGINS': 'https://dashoufajia.github.io'}
    result = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_reject_wildcard_cors_and_missing_production_origin():
    for origin in ['*', 'https://*.github.io', 'https://dashoufajia.github.io/repo/', 'http://untrusted.example']:
        with patch.dict(os.environ, {'ALLOWED_ORIGINS': origin}), pytest.raises(RuntimeError):
            allowed_origins()
    with patch.dict(os.environ, {'ALLOWED_ORIGINS': '', 'APP_ENV': 'production'}), pytest.raises(RuntimeError):
        allowed_origins()


def test_only_writing_samples_are_returned():
    result = TestClient(app).get('/api/data').json()
    assert set(result) == {'version', 'samples'}
    assert [s['id'] for s in result['samples']] == ['W1', 'W2', 'W3']
    assert 'items' not in result
