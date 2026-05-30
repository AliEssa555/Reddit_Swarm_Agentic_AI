from fastapi import FastAPI, Request
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts.nlp_topic_extraction import determine_topic
from db.database import SessionLocal
from db.models import TopicCategory, Topic, Post

app = FastAPI(title="Reddit Swarm Dashboard API")

@app.post("/webhook/reddit")
async def reddit_webhook(request: Request):
    """
    Bright Data triggers this URL automatically asynchronously once its massive scrape cluster finishes!
    It comes in hot with hundreds or thousands of clean JSON properties.
    """
    posts = await request.json()
    print(f"\n[WEBHOOK TRIGGERED] Successfully Received {len(posts)} posts from Bright Data Cloud!")
    
    db = SessionLocal()
    
    # Let's map everything dynamically!
    cats_db = {}
    tops_db = {}
    
    inserted_count = 0
    
    for item in posts:
        title = item.get("title", "")
        # The bright data schema uses 'description' for post body
        body = item.get("description", "") 
        reddit_id = str(item.get("post_id", ""))
        
        # Analyze Topic autonomously
        cat_name, top_name = determine_topic(title + " " + body)
        
        # Ensure TopicCategory exists
        if cat_name not in cats_db:
            cat = db.query(TopicCategory).filter(TopicCategory.name == cat_name).first()
            if not cat:
                cat = TopicCategory(name=cat_name, description="Auto-generated")
                db.add(cat)
                db.commit()
                db.refresh(cat)
            cats_db[cat_name] = cat
            
        # Ensure Topic exists
        top_key = f"{cat_name}::{top_name}"
        if top_key not in tops_db:
            top = db.query(Topic).filter(Topic.name == top_name, Topic.category_id == cats_db[cat_name].id).first()
            if not top:
                top = Topic(name=top_name, category_id=cats_db[cat_name].id, description="Subtopic")
                db.add(top)
                db.commit()
                db.refresh(top)
            tops_db[top_key] = top
            
        # Insert Post without duplicating
        if not db.query(Post).filter(Post.reddit_id == reddit_id).first():
            new_post = Post(
                reddit_id=reddit_id,
                title=title,
                body=body,
                author=item.get("user_posted", "[deleted]"),
                score=item.get("num_upvotes", 0),
                topic_id=tops_db[top_key].id
            )
            db.add(new_post)
            inserted_count += 1
            
    db.commit()
    db.close()
    
    print(f"Processed and permanently stored {inserted_count} new posts into PostgreSQL Topic Database!")
    return {"received": True, "processed_count": len(posts), "inserted": inserted_count}

if __name__ == "__main__":
    import uvicorn
    # Start the fast API webhook listener!
    uvicorn.run(app, host="0.0.0.0", port=8000)
