from dataclasses import dataclass
import os

DEFAULT_PROMPT = 'You are a helpful assistant. Give clear, concise answers.'

@dataclass(frozen=True)
class Settings:
    keys: tuple[str, ...]
    model: str
    database_url: str
    origins: tuple[str, ...]
    simulate: bool
    timeout: float = 30

    @classmethod
    def from_env(cls):
        keys = tuple(k.strip() for k in os.getenv('LLM_API_KEYS', '').split(',') if k.strip())
        if len(keys) < 2 or len(set(keys)) != len(keys):
            raise RuntimeError('Configure at least two distinct LLM_API_KEYS.')
        if any(k.startswith('replace_') for k in keys):
            raise RuntimeError('Replace placeholder API keys before starting.')
        return cls(keys, os.getenv('LLM_MODEL', 'gemini/gemini-3.5-flash-lite'),
                   os.getenv('DATABASE_URL', 'sqlite:///./app.db'),
                   tuple(o.strip() for o in os.getenv('ALLOWED_ORIGINS', 'http://localhost:3000').split(',') if o.strip()),
                   os.getenv('ENABLE_FAILURE_SIMULATION', 'false').lower() == 'true',
                   float(os.getenv('LLM_TIMEOUT_SECONDS', '30')))
