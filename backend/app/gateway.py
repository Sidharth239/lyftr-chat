"""Ordered key pool over the LiteLLM SDK; exact response cache via LiteLLM Cache."""
from dataclasses import dataclass
import hashlib
import json
import logging

log = logging.getLogger(__name__)

class ProvidersUnavailable(Exception):
    pass

@dataclass(frozen=True)
class Answer:
    reply: str
    model: str
    input_tokens: int
    output_tokens: int
    key_id: str | None
    fallback_attempts: int
    resolution_source: str

class Gateway:
    def __init__(self, settings, completion=None, cache=None):
        self.settings = settings
        if completion is None or cache is None:
            import litellm
            from litellm.caching.caching import Cache
            litellm.suppress_debug_info = True
            litellm.set_verbose = False
            # No background writes: explicit synchronous Cache operations guarantee
            # a subsequent request can immediately reuse a successful response.
            cache = cache if cache is not None else Cache(type='local', ttl=86400)
            litellm.cache = cache
            completion = completion or litellm.completion
        self.completion = completion
        self.cache = cache

    def respond(self, messages, failures):
        model = self.settings.model
        digest = hashlib.sha256(json.dumps({'model': model, 'messages': messages}, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
        cache_key = 'lyftr:v1:' + digest
        # A test header deliberately bypasses reads so it exercises the key pool,
        # even if a previous request cached the exact prompt.
        if not failures:
            cached = self.cache.get_cache(cache_key=cache_key)
            if cached is not None:
                return Answer(**cached, key_id=None, fallback_attempts=0, resolution_source='LLM_CACHE')
        attempts = 0
        for index, key in enumerate(self.settings.keys, 1):
            key_id = f'key_{index}'
            if key_id in failures or '*' in failures:
                log.info('Simulated provider failure: %s (%s)', key_id, failures.get(key_id, failures.get('*')))
                attempts += 1
                continue
            try:
                # The ordered outer loop is the failover mechanism; disable SDK retries
                # and automatic caching to keep per-key attempts and cache labels exact.
                response = self.completion(model=model, messages=messages, api_key=key,
                                           timeout=self.settings.timeout, num_retries=0,
                                           caching=False, cache={'no-cache': True, 'no-store': True})
                text = response.choices[0].message.content
                usage = response.usage
                if not isinstance(text, str) or not text.strip() or usage is None:
                    raise ValueError('Provider returned no usable text or usage')
                payload = {'reply': text, 'model': model, 'input_tokens': int(usage.prompt_tokens), 'output_tokens': int(usage.completion_tokens)}
                if min(payload['input_tokens'], payload['output_tokens']) < 0:
                    raise ValueError('Invalid usage')
            except Exception as exc:
                # LiteLLM normalizes upstream failures. Try the next key even on
                # auth/config/timeouts, but never expose provider exceptions or secrets.
                log.warning('Provider attempt failed: %s (%s, status=%s)', key_id, type(exc).__name__, getattr(exc, 'status_code', None))
                attempts += 1
                continue
            if not failures:
                self.cache.add_cache(result=payload, cache_key=cache_key)
            # Simulation must not overwrite an existing normal cache entry.
            return Answer(**payload, key_id=key_id, fallback_attempts=attempts, resolution_source='LIVE_INFERENCE')
        raise ProvidersUnavailable
