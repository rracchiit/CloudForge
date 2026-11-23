
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import DATABASE_URL

# Create database engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

# Create database sessions
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


# FastAPI database dependency
def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
