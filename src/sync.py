from sqlalchemy import create_engine
from sqlmodel import Session
from src.config import Config

sync_engine = create_engine(
    Config.DATABASE_URL.replace("+asyncpg","+psycopg"),
    pool_size=5,
    max_overflow=0,
    pool_pre_ping=True
)

def get_sync_session() -> Session:
    return Session(sync_engine)