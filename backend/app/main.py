from contextlib import asynccontextmanager
import logging
from threading import Lock
from time import perf_counter
from dataclasses import asdict
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from .config import Settings, DEFAULT_PROMPT
from .storage import Storage
from .gateway import Gateway, ProvidersUnavailable

class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=4000)
    system_prompt: str | None = None

    @field_validator('message', mode='before')
    @classmethod
    def trim_message(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator('session_id')
    @classmethod
    def nonblank_session(cls, value):
        if not value.strip():
            raise ValueError('session_id must not be blank')
        return value


def parse_failures(header, enabled, key_count):
    if not enabled or header is None:
        return {}
    result = {}
    allowed = {'*', *(f'key_{i}' for i in range(1, key_count+1))}
    for pair in header.split(','):
        parts = pair.strip().split('=')
        if len(parts) != 2 or parts[0] not in allowed or parts[1] not in {'429','500','502','503'}:
            raise HTTPException(422, 'invalid X-Simulate-Failure header')
        result[parts[0]] = int(parts[1])
    return result


def create_app(settings=None, gateway=None):
    # Lazily initialize on startup so tests can inject a provider without credentials.
    @asynccontextmanager
    async def lifespan(app):
        cfg = settings or Settings.from_env()
        store = Storage(cfg.database_url)
        store.initialize()
        app.state.settings = cfg
        app.state.store = store
        app.state.gateway = gateway or Gateway(cfg)
        app.state.locks = [Lock() for _ in range(128)]
        yield

    api = FastAPI(title='Lyftr Chat', lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    import os
    origins = settings.origins if settings else tuple(o.strip() for o in os.getenv('ALLOWED_ORIGINS', 'http://localhost:3000').split(',') if o.strip())
    api.add_middleware(CORSMiddleware, allow_origins=list(origins), allow_methods=['GET','POST'], allow_headers=['Content-Type','X-Simulate-Failure'])

    @api.exception_handler(Exception)
    async def internal_error(request: Request, exc: Exception):
        logging.getLogger(__name__).error('Unexpected request error: %s', type(exc).__name__)
        return JSONResponse(status_code=500, content={'detail': 'internal server error'})

    @api.get('/health')
    def health():
        try:
            api.state.store.ping()
        except Exception:
            raise HTTPException(503, 'database unavailable')
        return {'status': 'ok', 'keys_configured': len(api.state.settings.keys), 'cache_enabled': True}

    @api.post('/chat')
    def chat(body: ChatRequest, x_simulate_failure: str | None = Header(default=None)):
        start = perf_counter()
        cfg = api.state.settings
        failures = parse_failures(x_simulate_failure, cfg.simulate, len(cfg.keys))
        store = api.state.store
        # Serialize requests for the same session within the single deployed worker.
        with api.state.locks[hash(body.session_id) % len(api.state.locks)]:
            saved_prompt, history = store.read(body.session_id)
            prompt = body.system_prompt if body.system_prompt is not None else (saved_prompt if saved_prompt is not None else DEFAULT_PROMPT)
            messages = [{'role': 'system', 'content': prompt}, *({'role': m['role'], 'content': m['content']} for m in history), {'role': 'user', 'content': body.message}]
            try:
                answer = asdict(api.state.gateway.respond(messages, failures))
            except ProvidersUnavailable:
                raise HTTPException(503, 'all providers unavailable')
            reply = answer.pop('reply')
            answer['latency_ms'] = round((perf_counter() - start) * 1000)
            store.save_turn(body.session_id, prompt, body.message, reply, answer)
            return {'session_id': body.session_id, 'reply': reply, 'metadata': answer}

    @api.get('/sessions/{session_id}/messages')
    def history(session_id: str):
        prompt, messages = api.state.store.read(session_id)
        if prompt is None:
            raise HTTPException(404, 'session not found')
        return {'session_id': session_id, 'messages': messages}

    return api

app = create_app()
