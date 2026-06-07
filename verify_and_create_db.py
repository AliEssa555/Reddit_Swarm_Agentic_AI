import os
import sys
from sqlalchemy import create_engine, inspect
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.getcwd())

load_dotenv()

DATABASE_URL = os.getenv("POSTGRES_URL", "postgresql://postgres:ali@localhost:5432/reddit_swarm")

print(f"Connecting to: {DATABASE_URL}")

try:
    engine = create_engine(DATABASE_URL)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    print("Existing tables:", tables)
    
    from db.models import Base
    print("Creating all tables defined in models...")
    Base.metadata.create_all(bind=engine)
    
    # Re-inspect
    inspector = inspect(engine)
    tables_after = inspector.get_table_names()
    print("Tables after create_all:", tables_after)
    
    required_tables = ["brightdata_posts", "brightdata_comments", "agent_runs"]
    missing = [t for t in required_tables if t not in tables_after]
    
    if not missing:
        print("SUCCESS: All required tables now exist.")
    else:
        print(f"FAILURE: The following tables are still missing: {missing}")

except Exception as e:
    print(f"ERROR: {e}")
