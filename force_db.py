import os
import sys
from sqlalchemy import create_engine, inspect
from dotenv import load_dotenv

sys.path.append(os.getcwd())
load_dotenv()

DATABASE_URL = os.getenv("POSTGRES_URL")
print(f"URL: {DATABASE_URL}")

try:
    engine = create_engine(DATABASE_URL)
    from db.models import Base
    
    # 1. Before
    inspector = inspect(engine)
    print(f"BEFORE: {inspector.get_table_names()}")
    
    # 2. Create
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)
    
    # 3. After
    inspector = inspect(engine)
    print(f"AFTER: {inspector.get_table_names()}")
    
    print("DONE")
except Exception as e:
    print(f"ERROR: {e}")
