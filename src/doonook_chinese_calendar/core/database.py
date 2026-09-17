from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from .config import settings

writer_engine = create_engine(
    settings.WRITER_DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 10},
)

WriterSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=writer_engine)

Base = declarative_base()


def get_db_writer():
    """Both calendar GETs can persist cache entries; always use the primary."""
    db = WriterSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Existing imports and dependency overrides remain compatible. No reader pool:
# all database-backed endpoints in this package can write cache entries.
engine = writer_engine
SessionLocal = WriterSessionLocal
get_db = get_db_writer
