import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

class Storage:
    def __init__(self, url: str):
        if not url.startswith('sqlite:///') or url == 'sqlite:///:memory:':
            raise ValueError('DATABASE_URL must point to a SQLite file.')
        self.path = Path(url[len('sqlite:///'):]).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def initialize(self):
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY, system_prompt TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user','assistant')),
                content TEXT NOT NULL,
                metadata TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS messages_session ON messages(session_id, id);
            ''')

    def ping(self):
        with self.connect() as db:
            db.execute('SELECT 1 FROM messages LIMIT 1').fetchall()

    def read(self, session_id):
        with self.connect() as db:
            session = db.execute('SELECT system_prompt FROM sessions WHERE session_id=?', (session_id,)).fetchone()
            rows = db.execute('SELECT role, content, metadata FROM messages WHERE session_id=? ORDER BY id', (session_id,)).fetchall()
        return (session['system_prompt'] if session else None, [
            {'role': r['role'], 'content': r['content'], **({'metadata': json.loads(r['metadata'])} if r['metadata'] else {})}
            for r in rows])

    def save_turn(self, session_id, prompt, message, reply, metadata):
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            db.execute('INSERT INTO sessions VALUES (?, ?) ON CONFLICT(session_id) DO UPDATE SET system_prompt=excluded.system_prompt', (session_id, prompt))
            db.executemany('INSERT INTO messages(session_id,role,content,metadata,created_at) VALUES (?,?,?,?,?)', [
                (session_id, 'user', message, None, now),
                (session_id, 'assistant', reply, json.dumps(metadata), now),
            ])
