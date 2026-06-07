import sys
import os

# Add the project root to sys.path
sys.path.append(os.getcwd())

try:
    from db.database import engine
    from db.models import Base
    from sqlalchemy import inspect
    
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print("Tables found in database:")
    for table in tables:
        print(f" - {table}")
    
    if "brightdata_posts" in tables:
        print("SUCCESS: brightdata_posts table exists.")
    else:
        print("FAILURE: brightdata_posts table NOT found.")
except Exception as e:
    print(f"ERROR: {e}")
