from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv
import os

load_dotenv()

# We expect a POSTGRES_URL in .env like: postgresql://postgres:password@localhost:5432/reddit_swarm
DATABASE_URL = os.getenv("POSTGRES_URL", "postgresql://postgres:ali@localhost:5432/reddit_swarm")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
