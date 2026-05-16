import asyncio
import os
import sys

# Ensure imports work from the root folder
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.reddit_client import fetch_top_posts
from db.database import SessionLocal
from db.models import Post, Subreddit
from vector_store.chroma_client import VectorStore

async def ingest_to_databases(subreddit_name: str, limit: int = 10):
    print(f"Fetching top {limit} posts from r/{subreddit_name}...")
    
    # 1. Fetch from Reddit
    posts_data = await fetch_top_posts(subreddit_name, limit)
    if not posts_data:
        print("No posts fetched or Reddit API failed.")
        return

    db = SessionLocal()
    vector_store = VectorStore("reddit_memory")
    
    print("Saving to PostgreSQL and generating Embeddings for ChromaDB...")
    
    # Check if subreddit exists in DB
    sub = db.query(Subreddit).filter(Subreddit.name == subreddit_name).first()
    if not sub:
        sub = Subreddit(name=subreddit_name, description=f"Imported {subreddit_name}")
        db.add(sub)
        db.commit()
        db.refresh(sub)

    texts_to_embed = []
    ids_to_embed = []
    metadatas = []

    for item in posts_data:
        # Check if post already exists
        existing_post = db.query(Post).filter(Post.reddit_id == item["reddit_id"]).first()
        if not existing_post:
            new_post = Post(
                reddit_id=item["reddit_id"],
                title=item["title"],
                body=item["body"],
                author=item["author"],
                score=item["score"],
                subreddit_id=sub.id,
                embedding_id=item["reddit_id"] # Link the row directly to the Vector DB ID
            )
            db.add(new_post)
            
            # Prepare for Vector DB
            content = f"Title: {item['title']}\n"
            if item["body"]:
                content += f"Body: {item['body'][:1000]}" # Truncate massive posts for the vector embedder

            texts_to_embed.append(content)
            ids_to_embed.append(item["reddit_id"])
            metadatas.append({
                "subreddit": subreddit_name,
                "author": item["author"],
                "score": item["score"],
                "type": "post"
            })

    db.commit()
    db.close()

    # 2. Save to Vector Store (ChromaDB)
    if texts_to_embed:
        vector_store.add_texts(ids=ids_to_embed, texts=texts_to_embed, metadatas=metadatas)
        print(f"\nIngestion Complete! Ingested {len(texts_to_embed)} new posts into Postgres and ChromaDB.")
    else:
        print("\nAll posts were already in the database. No new embeddings generated.")

if __name__ == "__main__":
    # Example usage: Run the script directly to pull 10 posts from r/worldnews (or r/machinelearning)
    # Be sure your .env has REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET
    import argparse
    parser = argparse.ArgumentParser(description="Ingest Reddit data into DBs")
    parser.add_argument("--sub", type=str, default="MachineLearning", help="Subreddit to scrape")
    parser.add_argument("--limit", type=int, default=15, help="Number of posts")
    args = parser.parse_args()
    
    asyncio.run(ingest_to_databases(args.sub, args.limit))
