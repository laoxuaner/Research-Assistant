from contextlib import contextmanager
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from .models import Base

class Database:
    def __init__(self, directory):
        directory.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine("sqlite:///" + str(directory / "research.db"), connect_args={"check_same_thread": False, "timeout": 30})
        @event.listens_for(self.engine, "connect")
        def configure(conn, _):
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=30000")
        self.Session = sessionmaker(self.engine, expire_on_commit=False)

    def migrate(self):
        from .migrations import migrate
        migrate(self.engine)

    @contextmanager
    def session(self):
        with self.Session() as db:
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

def serialize(row, exclude=()):
    hidden = {"storage_path", "original_path", "vector"} | set(exclude)
    return {c.name: getattr(row, c.name) for c in row.__table__.columns if c.name not in hidden}
