import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db.database import engine, Base
from db.models import Subreddit, Post, Comment, AgentRun

def init_db():
    print("Creating database tables if they don't exist...")
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully.")

if __name__ == "__main__":
    init_db()
