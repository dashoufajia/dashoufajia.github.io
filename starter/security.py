"""Small single-instance classroom service limits; no draft or code is logged."""
from collections import OrderedDict, deque
from hashlib import sha256
from hmac import compare_digest
import math
import os
from threading import Lock
import time
from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from starlette.responses import JSONResponse


def allowed_origins():
    values = [v.strip().rstrip('/') for v in os.getenv('ALLOWED_ORIGINS', '').split(',') if v.strip()]
    for value in values:
        url = urlsplit(value)
        local = url.hostname in {'localhost', '127.0.0.1'}
        if url.username or url.password or url.path or url.query or url.fragment or not url.hostname or not (
            url.scheme == 'https' or (url.scheme == 'http' and local)
        ):
            raise RuntimeError('ALLOWED_ORIGINS must contain exact HTTPS origins without paths or wildcards.')
        if '*' in value:
            raise RuntimeError('Wildcard CORS origins are not allowed.')
    if os.getenv('APP_ENV') == 'production' and not values:
        raise RuntimeError('Set ALLOWED_ORIGINS to the actual GitHub Pages origin before production startup.')
    return values


class WindowLimiter:
    def __init__(self, max_keys=2048):
        self.events = OrderedDict()
        self.lock = Lock()
        self.max_keys = max_keys

    def check(self, key, maximum, window=60, now=None):
        now = time.monotonic() if now is None else now
        with self.lock:
            if key not in self.events:
                # Reclaim inactive keys, but do not evict active counters to bypass limits.
                for old in list(self.events):
                    if not self.events[old] or self.events[old][-1] <= now - 86400:
                        del self.events[old]
                if len(self.events) >= self.max_keys:
                    raise HTTPException(429, 'Service is busy. Try again later.', headers={'Retry-After': '60'})
                self.events[key] = deque()
            queue = self.events[key]
            while queue and queue[0] <= now - window:
                queue.popleft()
            if len(queue) >= maximum:
                retry = max(1, math.ceil(window - (now - queue[0])))
                raise HTTPException(429, 'Request limit reached. Please wait before trying again.', headers={'Retry-After': str(retry)})
            queue.append(now)
            self.events.move_to_end(key)


limiter = WindowLimiter()


def number(name, default):
    return max(1, int(os.getenv(name, str(default))))


def protect_analysis(request: Request):
    # Render's trusted proxy may set request.client; aggregate ceilings also apply.
    peer = request.client.host if request.client else 'unknown'
    limiter.check('analysis-peer:' + peer, number('ANALYSIS_REQUESTS_PER_MINUTE', 15))
    limiter.check('analysis-total', number('ANALYSIS_TOTAL_PER_MINUTE', 120))


def protect_ai(request: Request):
    peer = request.client.host if request.client else 'unknown'
    limiter.check('ai-attempt:' + peer, 20)
    expected = os.getenv('CLASSROOM_DEMO_CODE', '')
    if not expected or expected.startswith('replace-'):
        raise HTTPException(503, 'AI is unavailable: the classroom demo code has not been configured. Rule hints remain available.')
    supplied = request.headers.get('x-classroom-code', '')
    if not supplied or len(supplied) > 128 or not compare_digest(supplied.encode(), expected.encode()):
        raise HTTPException(401, 'Enter the correct classroom demo code to use AI. Rule hints remain available.')
    group = sha256(expected.encode()).hexdigest()
    limiter.check('ai-peer:' + peer, number('AI_REQUESTS_PER_MINUTE', 5))
    limiter.check('ai-class:' + group, number('AI_TOTAL_PER_MINUTE', 30))
    limiter.check('ai-day:' + group, number('AI_TOTAL_PER_DAY', 200), 86400)


class RequestSizeLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope.get('method') != 'POST':
            return await self.app(scope, receive, send)
        limit = 8192 if scope.get('path') == '/api/hint' else 100000
        headers = dict(scope.get('headers', []))
        try:
            declared = int(headers.get(b'content-length', b'0'))
        except ValueError:
            declared = limit + 1
        if declared > limit or declared < 0:
            return await JSONResponse({'detail': 'Request body is too large.'}, 413)(scope, receive, send)
        chunks = []
        size = 0
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            chunk = message.get('body', b'')
            size += len(chunk)
            if size > limit:
                return await JSONResponse({'detail': 'Request body is too large.'}, 413)(scope, receive, send)
            chunks.append(chunk)
            if not message.get('more_body', False):
                break
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {'type': 'http.request', 'body': b''.join(chunks), 'more_body': False}
            return await receive()

        await self.app(scope, bounded_receive, send)
