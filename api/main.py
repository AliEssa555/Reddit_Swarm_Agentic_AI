from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts.nlp_topic_extraction import determine_topic
from db.models import TopicCategory, Topic, Post, Base, AgentRun, BrightDataPost, BrightDataComment
from agents.realtime_swarm import live_swarm, _post_brightdata
from db.database import SessionLocal, engine
from services.llm_client import get_llm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from config import BRIGHTDATA_API_KEY
import config

# Ensure all tables (including BrightData ones) are created in Postgres on startup
Base.metadata.create_all(bind=engine)

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

@app.get("/api/topics")
async def get_topics():
    """Fetch the hierarchical topic structure."""
    db = SessionLocal()
    categories = db.query(TopicCategory).all()
    results = []
    for cat in categories:
        topics = db.query(Topic).filter(Topic.category_id == cat.id).all()
        results.append({
            "id": cat.id,
            "name": cat.name,
            "description": cat.description,
            "topics": [{"id": t.id, "name": t.name, "description": t.description} for t in topics]
        })
    db.close()
    return results

@app.get("/api/history")
async def get_history():
    """Fetch recent swarm execution runs for the observability page."""
    db = SessionLocal()
    runs = db.query(AgentRun).order_by(AgentRun.created_at.desc()).limit(20).all()
    results = []
    for run in runs:
        results.append({
            "id": run.id,
            "agent_name": run.agent_name,
            "task": run.task,
            "result": run.result,
            "evaluation": run.evaluation_result,
            "latency": run.latency,
            "created_at": run.created_at
        })
    db.close()
    return results

@app.get("/api/category/{category_id}/analysis")
async def analyze_category(category_id: int):
    """Feeds historical category data to the LLM for synthesis."""
    db = SessionLocal()
    cat = db.query(TopicCategory).filter(TopicCategory.id == category_id).first()
    if not cat:
        db.close()
        return {"error": "Category not found."}
    
    topics = db.query(Topic).filter(Topic.category_id == cat.id).all()
    topic_ids = [t.id for t in topics]
    
    posts = db.query(Post).filter(Post.topic_id.in_(topic_ids)).limit(20).all()
    bd_posts = db.query(BrightDataPost).filter(BrightDataPost.topic_id.in_(topic_ids)).limit(20).all()
    
    all_posts = posts + bd_posts
    
    if len(all_posts) < 5:
        db.close()
        return {"response": "Not enough data available to form a comprehensive analysis."}
        
    context_str = f"--- HISTORICAL POSTS FOR TOPIC: {cat.name} ---\n"
    for post in all_posts[:20]:
        context_str += f"Title: {post.title}\nBody: {(post.body or '')[:200]}...\n\n"
        
    db.close()
    
    llm = get_llm()
    prompt = ChatPromptTemplate.from_template(
        "You are an analytical Reddit AI. Based on the following historical posts in the '{category_name}' category, synthesize what the topics being discussed are and what people's views on them are. Keep it analytical and structured.\n"
        "Historical Data:\n{context}\n\n"
        "Synthesized Analysis:"
    )
    chain = prompt | llm | StrOutputParser()
    try:
        response = chain.invoke({"category_name": cat.name, "context": context_str})
        return {"response": response}
    except Exception as e:
        return {"response": f"LLM Error: {e}"}

class ScrapeRequest(BaseModel):
    category_id: int
    num_posts: int
    num_comments: int
    time_filter: str

@app.post("/api/category/scrape")
async def batch_scrape_category(req: ScrapeRequest):
    """Trigger a batch BrightData scrape specifically targeting a Category."""
    db = SessionLocal()
    cat = db.query(TopicCategory).filter(TopicCategory.id == req.category_id).first()
    db.close()
    if not cat:
        return {"error": "Category not found."}
        
    # We would ideally run this in a background task, but for MVP synchronous is okay if short limits.
    # We will trigger the BrightData Discover directly.
    import threading
    def background_scrape():
        log = []
        headers = {
            "Authorization": f"Bearer {BRIGHTDATA_API_KEY}",
            "Content-Type": "application/json"
        }
        url_posts = "https://api.brightdata.com/datasets/v3/scrape?dataset_id=gd_lvz8ah06191smkebj4&notify=false&include_errors=true&type=discover_new&discover_by=keyword"
        payload_posts = {
            "input": [{"keyword": cat.name, "date": req.time_filter, "num_of_posts": req.num_posts}]
        }
        
        scraped_posts = _post_brightdata(url_posts, headers, payload_posts, log, timeout=120)
        
        if scraped_posts:
            scraped_comments = []
            if req.num_comments > 0:
                url_comments = "https://api.brightdata.com/datasets/v3/scrape?dataset_id=gd_lvzdpsdlw09j6t702&notify=false&include_errors=true"
                comments_input = []
                for p in scraped_posts[:3]: # limit to top 3 for speed
                    if p.get("url"):
                        comments_input.append({
                            "url": p.get("url"),
                            "days_back": 180,
                            "load_all_replies": False,
                            "comment_limit": req.num_comments
                        })
                if comments_input:
                    scraped_comments = _post_brightdata(url_comments, headers, {"input": comments_input}, log, timeout=120)
            
            # Save to DB
            db_inner = SessionLocal()
            for item in scraped_posts:
                reddit_id = str(item.get("post_id", ""))
                title = item.get("title", "")
                if not db_inner.query(BrightDataPost).filter(BrightDataPost.reddit_id == reddit_id).first():
                    new_post = BrightDataPost(
                        reddit_id=reddit_id,
                        title=title[:255],
                        body=(item.get("description") or ""),
                        author=item.get("user_posted", "unknown"),
                        score=item.get("num_upvotes", 0),
                        topic_id=None # We could parse topic here using determine_topic
                    )
                    db_inner.add(new_post)
            
            for item in scraped_comments:
                comment_id = str(item.get("comment_id", ""))
                post_id = str(item.get("post_id", ""))
                if not db_inner.query(BrightDataComment).filter(BrightDataComment.comment_id == comment_id).first():
                    new_com = BrightDataComment(
                        comment_id=comment_id,
                        post_reddit_id=post_id,
                        body=item.get("comment", ""),
                        author=item.get("user_posted", "unknown"),
                        score=item.get("num_upvotes", 0)
                    )
                    db_inner.add(new_com)
                    
            db_inner.commit()
            db_inner.close()

    thread = threading.Thread(target=background_scrape)
    thread.start()
    
    return {"message": f"Background scraping task started for '{cat.name}' with {req.num_posts} target posts."}


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
