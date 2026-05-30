from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts.nlp_topic_extraction import determine_topic
from db.database import SessionLocal
from db.models import TopicCategory, Topic, Post
from agents.realtime_swarm import live_swarm

from db.database import SessionLocal
from db.models import TopicCategory, Topic, Post

app = FastAPI(title="Reddit Swarm Dashboard API")

# Setup CORS to allow Vue UI communication locally seamlessly
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For local testing unrestricted access
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    query: str

@app.post("/api/ask")
async def ask_live_swarm_endpoint(req: QueryRequest):
    """Synchronous endpoint triggering the entire live web scraping architecture on-demand!"""
    print(f"\n[USER INITIATED]: {req.query}")
    
    result = live_swarm.invoke({
        "original_query": req.query,
        "search_keyword": "",
        "raw_scraped_data": [],
        "final_response": "",
        "log_messages": []
    })
    
    return {
        "response": result.get("final_response"),
        "logs": result.get("log_messages", [])
    }


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
    import subprocess
    import time
    import requests
    import atexit

    llm_proc = None

    def cleanup():
        if llm_proc:
            print("\n[SYSTEM] Shutting down local Qwen2.5 LLM server...")
            llm_proc.terminate()

    atexit.register(cleanup)

    print("\n[SYSTEM] Booting up local Qwen2.5 LLM engine...")
    cmd = [
        r"C:\Users\PC\Downloads\Learn-and-Rise\llama_server_vulkan\llama-server.exe",
        "-m", r"C:\Users\PC\Downloads\Learn-and-Rise\llama.cpp\qwen2.5-7b-q4_k_m.gguf",
        "--port", "8085",
        "-ngl", "999",
        "-c", "8192",
        "--host", "127.0.0.1"
    ]
    # We pipe outputs to DEVNULL to not spam the FastAPI terminal
    llm_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    print("[SYSTEM] Pinging LLM health check on port 8085...")
    for _ in range(45):
        try:
            r = requests.get("http://127.0.0.1:8085/health", timeout=1)
            if r.status_code == 200 or r.status_code == 503: # 503 means loading weights but server is up
                print("[SYSTEM] >>> LLM Engine is successfully ONLINE! <<<")
                break
        except:
            pass
        time.sleep(1)

    print("\n[SYSTEM] Starting FastAPI Web Server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
