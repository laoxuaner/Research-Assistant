"""Versioned, repeatable local SQLite migrations. Add new versions; never edit applied migrations."""
from sqlalchemy import text
from .models import Base

def migrate(engine):
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT DEFAULT CURRENT_TIMESTAMP)"))
        versions = set(conn.execute(text("SELECT version FROM schema_migrations")).scalars())
        if 1 not in versions:
            Base.metadata.create_all(conn)
            conn.execute(text("CREATE VIRTUAL TABLE chunks_fts USING fts5(chunk_id UNINDEXED, project_id UNINDEXED, paper_id UNINDEXED, tokens, tokenize='unicode61')"))
            conn.execute(text("CREATE TRIGGER chunks_fts_delete AFTER DELETE ON chunks BEGIN DELETE FROM chunks_fts WHERE chunk_id=old.id; END"))
            conn.execute(text("INSERT INTO schema_migrations(version) VALUES (1)"))
