import os
import sys
import pandas as pd
import asyncio

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db.database import SessionLocal, Base, engine
from db.models import TopicCategory, Topic, Post, Comment

# A simple heuristic mapping to demonstrate hierarchical topic clustering locally.
# In a full run, an LLM or sentence-transformers HDBSCAN could generate these dynamically.
TOPIC_TAXONOMY = {
    "Geopolitics": {
        "keywords": ["war", "conflict", "election", "president", "treaty", "nato", "un", "military", "politics", "government", "russia", "ukraine", "israel", "gaza", "china", "taiwan", "us", "uk"],
        "topics": {
            "Middle East": ["israel", "gaza", "palestine", "iran", "syria", "lebanon", "middle east", "saudi", "yemen"],
            "Eastern Europe": ["russia", "ukraine", "putin", "zelensky", "moscow", "kiev", "kyiv", "nato"],
            "Americas": ["us", "usa", "biden", "trump", "america", "congress", "senate", "mexico", "brazil"],
            "Asia": ["china", "taiwan", "beijing", "xi jinping", "japan", "korea", "india", "pakistan"],
            "General Politics": [] # fallback
        }
    },
    "Economics": {
        "keywords": ["economy", "inflation", "market", "stock", "trade", "gdp", "recession", "bank", "interest rate", "fed", "crypto", "bitcoin"],
        "topics": {
            "Crypto & Finance": ["crypto", "bitcoin", "ethereum", "bank", "interest", "fed"],
            "Global Markets": ["stock", "market", "trade", "inflation", "gdp", "economy", "recession"],
            "General Economics": []
        }
    },
    "Environment & Science": {
        "keywords": ["climate", "warming", "environment", "pollution", "space", "nasa", "spacex", "moon", "mars", "science", "research", "study", "planet"],
        "topics": {
            "Space Exploration": ["space", "nasa", "spacex", "moon", "mars", "planet"],
            "Climate Change": ["climate", "warming", "environment", "pollution", "carbon", "green", "energy"],
            "General Science": ["research", "study", "science", "discover"]
        }
    },
    "Technology": {
        "keywords": ["tech", "ai", "artificial intelligence", "robot", "software", "cyber", "hack", "data", "apple", "google", "microsoft", "meta", "openai"],
        "topics": {
            "Artificial Intelligence": ["ai", "artificial intelligence", "openai", "chatgpt", "llm", "neural"],
            "Cybersecurity": ["cyber", "hack", "breach", "data", "security", "ransomware"],
            "Corporate Tech": ["apple", "google", "microsoft", "meta", "facebook", "amazon", "tech"]
        }
    }
}

def determine_topic(text: str):
    text = str(text).lower()
    
    best_category = "General News"
    best_topic = "Uncategorized"
    max_cat_score = 0
    
    # 1. Find best category
    for cat, cat_data in TOPIC_TAXONOMY.items():
        score = sum(1 for kw in cat_data["keywords"] if kw in text)
        if score > max_cat_score:
            max_cat_score = score
            best_category = cat
            
            # 2. Find best topic inside category
            max_top_score = 0
            for top, top_kws in cat_data["topics"].items():
                t_score = sum(1 for kw in top_kws if kw in text)
                if t_score > max_top_score:
                    max_top_score = t_score
                    best_topic = top
            
            # If no subtopic matched but category matched, use the fallback
            if max_top_score == 0:
                best_topic = list(cat_data["topics"].keys())[-1]
                
    return best_category, best_topic

def reset_and_ingest(posts_csv: str, comments_csv: str, limit: int = 500):
        
    print("Rebuilding Database Schema for Hierarchical Topics...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    print(f"Loading top {limit} posts from {posts_csv}...")
    df_posts = pd.read_csv(posts_csv)
    posts_data = df_posts.head(limit).to_dict('records')
    
    print("Extracting Topics and Inserting into Postgres...")
    
    # Pre-cache DB objects
    cats_db = {}
    tops_db = {}
    
    for idx, item in enumerate(posts_data):
        title = str(item.get('title', ''))
        body = str(item.get('selftext', ''))
        
        # Heuristic NLP Classification
        cat_name, top_name = determine_topic(title + " " + body)
        
        # 1. Ensure Category
        if cat_name not in cats_db:
            new_cat = TopicCategory(name=cat_name, description=f"Auto-generated category: {cat_name}")
            db.add(new_cat)
            db.commit()
            db.refresh(new_cat)
            cats_db[cat_name] = new_cat
            
        # 2. Ensure Topic
        top_key = f"{cat_name}::{top_name}"
        if top_key not in tops_db:
            new_top = Topic(name=top_name, category_id=cats_db[cat_name].id, description=f"Subtopic: {top_name}")
            db.add(new_top)
            db.commit()
            db.refresh(new_top)
            tops_db[top_key] = new_top
            
        # 3. Insert Post
        reddit_id = str(item.get('id', f"csv_{idx}"))
        score = item.get('score', 0)
        score = int(score) if pd.notna(score) else 0
        
        new_post = Post(
            reddit_id=reddit_id,
            title=title,
            body="" if body == 'nan' else body,
            author=str(item.get('author', '[deleted]')),
            score=score,
            topic_id=tops_db[top_key].id
        )
        db.add(new_post)
        
    db.commit()
    print(f"Successfully clustered {len(posts_data)} posts into {len(cats_db)} Categories and {len(tops_db)} Topics.")
    
    # We could also ingest comments_csv and link them by post_id here.
    # Leaving out for brevity unless requested.
    
    db.close()

if __name__ == "__main__":
    if not os.path.exists("data"):
        print("Error: Please put your posts.csv inside a 'data' folder.")
        sys.exit(1)
        
    ingest_from_csv_path = r"data\posts.csv"
    ingest_comments_path = r"data\comments.csv"
    
    reset_and_ingest(ingest_from_csv_path, ingest_comments_path, limit=500)
