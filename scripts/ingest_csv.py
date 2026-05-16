import asyncio
import os
import sys
import csv
import pandas as pd
from datetime import datetime

# Ensure imports work from the root folder
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db.database import SessionLocal
from db.models import Post, Subreddit
from vector_store.chroma_client import VectorStore

async def ingest_from_csv(csv_path: str, limit: int = 50):
    if not os.path.exists(csv_path):
        print(f"Error: Could not find {csv_path}. Please download it from Kaggle and place it in the project root.")
        return

    print(f"Reading data from {csv_path}...")
    df = pd.read_csv(csv_path)
    # The Kaggle dataset columns might vary, so we handle missing safely
    posts_data = df.head(limit).to_dict('records')
    
    db = SessionLocal()
    vector_store = VectorStore("reddit_memory")
    
    subreddit_name = "worldnews"
    
    print("Saving to PostgreSQL and generating Embeddings for ChromaDB...")
    
    sub = db.query(Subreddit).filter(Subreddit.name == subreddit_name).first()
    if not sub:
        sub = Subreddit(name=subreddit_name, description=f"Imported from CSV")
        db.add(sub)
        db.commit()
        db.refresh(sub)

    texts_to_embed = []
    ids_to_embed = []
    metadatas = []

    for idx, item in enumerate(posts_data):
        # We might not have reddit_id in the CSV, so we fallback to index if needed
        reddit_id = str(item.get('id', f"csv_{idx}"))
        title = str(item.get('title', 'Unknown Title'))
        body = str(item.get('selftext', '')) # Many worldnews posts have no body
        if body == 'nan': body = ''
        
        score = item.get('score', 0)
        if pd.isna(score): score = 0
        
        author = str(item.get('author', '[deleted]'))

        existing_post = db.query(Post).filter(Post.reddit_id == reddit_id).first()
        if not existing_post:
            new_post = Post(
                reddit_id=reddit_id,
                title=title,
                body=body,
                author=author,
                score=int(score),
                subreddit_id=sub.id,
                embedding_id=reddit_id
            )
            db.add(new_post)
            
            content = f"Title: {title}\n"
            if body:
                content += f"Body: {body[:1000]}"

            texts_to_embed.append(content)
            ids_to_embed.append(reddit_id)
            metadatas.append({
                "subreddit": subreddit_name,
                "author": author,
                "score": int(score),
                "type": "post"
            })

    db.commit()
    db.close()

    if texts_to_embed:
        vector_store.add_texts(ids=ids_to_embed, texts=texts_to_embed, metadatas=metadatas)
        print(f"\nIngestion Complete! Ingested {len(texts_to_embed)} new posts into Postgres and ChromaDB.")
    else:
        print("\nAll posts were already in the database. No new embeddings generated.")

if __name__ == "__main__":
    # We will use pandas, so ensure it's in our env
    import subprocess
    try:
        import pandas
    except ImportError:
        print("Installing pandas to read the CSV...")
    asyncio.run(ingest_from_csv(r"data\posts.csv", limit=100))
