from fastapi import FastAPI, Request, HTTPException
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
import json

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

class CategoryCreate(BaseModel):
    name: str
    description: str = ""
    subtopics: str = ""

@app.post("/api/ask")
async def ask_db_swarm_endpoint(req: QueryRequest):
    """Synchronous endpoint triggering the Database QA Text-to-SQL architecture."""
    print(f"\n[USER INITIATED]: {req.query}")
    
    from agents.sql_swarm import sql_swarm
    
    result = sql_swarm.invoke({
        "original_query": req.query,
        "extracted_json": "",
        "generated_sql": "",
        "raw_db_results": "",
        "final_summary": "",
        "error": ""
    })
    
    # Format the log messages for the UI
    result_rows = result.get('raw_db_results', '')
    row_count = len(result_rows.splitlines()) - 1 if "No rows returned" not in result_rows and result_rows else 0
    
    logs = [
        f"EXTRACTOR (JSON Topics): {result.get('extracted_json', 'None')}",
        f"SQL GENERATOR: {result.get('generated_sql', 'None')}",
        f"DB EXECUTOR: {row_count} rows fetched and fed to Synthesizer."
    ]
    
    if result.get("error"):
        logs.append(f"ERROR: {result.get('error')}")
        
    return {
        "response": result.get("final_summary", "No final response generated."),
        "logs": logs
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

@app.post("/api/category")
async def create_category(req: CategoryCreate):
    db = SessionLocal()
    # Check if exists
    existing = db.query(TopicCategory).filter(TopicCategory.name == req.name).first()
    if existing:
        db.close()
        raise HTTPException(status_code=400, detail="Category already exists")
    
    new_cat = TopicCategory(name=req.name, description=req.description)
    db.add(new_cat)
    db.commit()
    db.refresh(new_cat)
    
    # Process user-defined subtopics or default to 'General'
    if req.subtopics.strip():
        subtopics_list = [s.strip() for s in req.subtopics.split(',') if s.strip()]
        for sub in subtopics_list:
            new_topic = Topic(name=sub, description=f"Initial topic: {sub}", category_id=new_cat.id)
            db.add(new_topic)
    else:
        # Create a default "General" topic so scraping and analysis have a target
        default_topic = Topic(name="General", description=f"General posts for {req.name}", category_id=new_cat.id)
        db.add(default_topic)
        
    db.commit()
    
    cat_id = new_cat.id
    cat_name = new_cat.name
    db.close()
    return {"id": cat_id, "name": cat_name, "message": "Category created successfully with default topic."}

class BatchCategoryItem(BaseModel):
    name: str
    description: str = ""
    subtopics: str = ""  # Comma-separated

class BatchCategoryCreate(BaseModel):
    categories: list[BatchCategoryItem]
    # Scrape settings applied to all categories
    num_posts: int = 50
    num_comments: int = 5
    time_filter: str = "Past month"

@app.post("/api/batch-categories")
async def batch_create_categories(req: BatchCategoryCreate):
    """
    Batch create multiple categories (with subtopics) and immediately scrape
    BrightData for each one sequentially.

    Postman Body (JSON):
    {
        "num_posts": 30,
        "num_comments": 5,
        "time_filter": "Past month",
        "categories": [
            {"name": "AI & ML", "subtopics": "LLMs, Computer Vision, NLP"},
            {"name": "Geopolitics", "subtopics": "Middle East, Eastern Europe"},
            {"name": "Climate", "subtopics": ""}
        ]
    }
    """
    headers = {
        "Authorization": f"Bearer {BRIGHTDATA_API_KEY}",
        "Content-Type": "application/json"
    }
    url_posts = "https://api.brightdata.com/datasets/v3/scrape?dataset_id=gd_lvz8ah06191smkebj4&notify=false&include_errors=true&type=discover_new&discover_by=keyword"
    url_comments = "https://api.brightdata.com/datasets/v3/scrape?dataset_id=gd_lvzdpsdlw09j6t702&notify=false&include_errors=true"

    results = []
    skipped = []

    for item in req.categories:
        db = SessionLocal()
        try:
            # --- Step 1: Create category if not exists ---
            existing = db.query(TopicCategory).filter(TopicCategory.name == item.name).first()
            if existing:
                skipped.append(item.name)
                db.close()
                continue

            new_cat = TopicCategory(name=item.name, description=item.description)
            db.add(new_cat)
            db.commit()
            db.refresh(new_cat)

            subtopic_names = []
            if item.subtopics.strip():
                subtopics_list = [s.strip() for s in item.subtopics.split(',') if s.strip()]
                for sub in subtopics_list:
                    db.add(Topic(name=sub, description=f"Initial topic: {sub}", category_id=new_cat.id))
                    subtopic_names.append(sub)
            else:
                db.add(Topic(name="General", description=f"General posts for {item.name}", category_id=new_cat.id))
                subtopic_names.append("General")

            db.commit()

            cat_id = new_cat.id
            cat_name = new_cat.name
            target_topic = db.query(Topic).filter(Topic.category_id == cat_id).first()
            target_topic_id = target_topic.id if target_topic else None
            db.close()

            print(f"\n[BATCH SCRAPE] Starting scrape for '{cat_name}' ({req.num_posts} posts)")

            # --- Step 2: Scrape posts ---
            log = []
            payload_posts = {
                "input": [{"keyword": cat_name, "date": req.time_filter, "num_of_posts": req.num_posts}]
            }
            scraped_posts = _post_brightdata(url_posts, headers, payload_posts, log, timeout=2400)
            for msg in log:
                print(f"  [BD-POSTS] {msg}")
            log.clear()

            posts_saved = 0
            comments_saved = 0
            scraped_comments = []

            if scraped_posts:
                # --- Step 3: Scrape comments for top posts ---
                if req.num_comments > 0:
                    comments_input = [
                        {"url": p.get("url"), "days_back": 180, "load_all_replies": False, "comment_limit": req.num_comments}
                        for p in scraped_posts[:3] if p.get("url")
                    ]
                    if comments_input:
                        scraped_comments = _post_brightdata(url_comments, headers, {"input": comments_input}, log, timeout=2400)
                        for msg in log:
                            print(f"  [BD-COMMENTS] {msg}")

                # --- Step 4: Save to DB ---
                db2 = SessionLocal()
                try:
                    from db.models import BrightDataPost, BrightDataComment
                    import re as _re

                    for post_item in scraped_posts:
                        reddit_id = post_item.get("id")
                        if not reddit_id or str(reddit_id).lower() in ("none", "null", ""):
                            url_val = post_item.get("url", "")
                            match = _re.search(r'/comments/([a-z0-9]+)', url_val)
                            reddit_id = match.group(1) if match else None
                        if not reddit_id:
                            continue

                        existing_post = db2.query(BrightDataPost).filter(BrightDataPost.reddit_id == str(reddit_id)).first()
                        if existing_post:
                            continue

                        db2.add(BrightDataPost(
                            reddit_id=str(reddit_id),
                            title=post_item.get("title", ""),
                            url=post_item.get("url", ""),
                            body=post_item.get("body", ""),
                            author=post_item.get("author", ""),
                            score=int(post_item.get("score", 0) or 0),
                            num_comments=int(post_item.get("num_comments", 0) or 0),
                            topic_id=target_topic_id,
                            snapshot_id=post_item.get("snapshot_id", "batch")
                        ))
                        posts_saved += 1

                    for c in (scraped_comments or []):
                        post_rid = c.get("post_id") or c.get("post_reddit_id")
                        if not post_rid or str(post_rid).lower() in ("none", "null", ""):
                            post_url = c.get("post_url", "")
                            match = _re.search(r'/comments/([a-z0-9]+)', post_url)
                            post_rid = match.group(1) if match else None

                        db2.add(BrightDataComment(
                            comment_id=c.get("id", ""),
                            post_reddit_id=str(post_rid) if post_rid else None,
                            body=c.get("body", ""),
                            author=c.get("author", ""),
                            score=int(c.get("score", 0) or 0),
                            snapshot_id="batch"
                        ))
                        comments_saved += 1

                    db2.commit()
                finally:
                    db2.close()

            results.append({
                "name": cat_name,
                "id": cat_id,
                "subtopics": subtopic_names,
                "posts_scraped": posts_saved,
                "comments_scraped": comments_saved
            })
            print(f"[BATCH DONE] '{cat_name}': {posts_saved} posts, {comments_saved} comments saved.")

        except Exception as e:
            print(f"[BATCH ERROR] Failed for '{item.name}': {e}")
            results.append({"name": item.name, "error": str(e)})
            try:
                db.close()
            except Exception:
                pass

    return {
        "results": results,
        "skipped_duplicates": skipped,
        "summary": f"{len(results)} categories processed, {len(skipped)} skipped as duplicates."
    }

@app.delete("/api/category/{category_id}")
async def delete_category(category_id: int):
    db = SessionLocal()
    cat = db.query(TopicCategory).filter(TopicCategory.id == category_id).first()
    if not cat:
        db.close()
        raise HTTPException(status_code=404, detail="Category not found")
    
    cat_name = cat.name  # Save name before deletion
    
    # 1. Find all topics in this category
    topics = db.query(Topic).filter(Topic.category_id == category_id).all()
    topic_ids = [t.id for t in topics]
    
    # 2. Delete associated BrightData data (Comments first for FK)
    # BrightDataComment doesn't have a direct topic_id, but it has post_reddit_id
    posts = db.query(BrightDataPost).filter(BrightDataPost.topic_id.in_(topic_ids)).all()
    post_reddit_ids = [p.reddit_id for p in posts]
    
    db.query(BrightDataComment).filter(BrightDataComment.post_reddit_id.in_(post_reddit_ids)).delete(synchronize_session=False)
    db.query(BrightDataPost).filter(BrightDataPost.topic_id.in_(topic_ids)).delete(synchronize_session=False)
    
    # 3. Delete normal posts/topics
    db.query(Topic).filter(Topic.category_id == category_id).delete(synchronize_session=False)
    db.query(TopicCategory).filter(TopicCategory.id == category_id).delete(synchronize_session=False)
    
    db.commit()
    db.close()
    return {"message": f"Category '{cat_name}' and all associated data deleted successfully."}

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

@app.get("/api/category/{category_id}/subtopics")
async def extract_subtopics(category_id: int):
    """Uses LLM to analyze category posts and extract structured subtopics for a Pie Chart."""
    db = SessionLocal()
    cat = db.query(TopicCategory).filter(TopicCategory.id == category_id).first()
    if not cat:
        db.close()
        return {"error": "Category not found."}
        
    topics = db.query(Topic).filter(Topic.category_id == cat.id).all()
    topic_ids = [t.id for t in topics]
    
    posts = db.query(Post).filter(Post.topic_id.in_(topic_ids)).limit(30).all()
    bd_posts = db.query(BrightDataPost).filter(BrightDataPost.topic_id.in_(topic_ids)).limit(30).all()
    
    all_posts = posts + bd_posts
    
    if len(all_posts) == 0:
        db.close()
        return {"error": "Not enough data available to extract subtopics."}
        
    context_str = "\n".join([f"- {post.title}" for post in all_posts[:30]])
    db.close()
    
    llm = get_llm()
    prompt = ChatPromptTemplate.from_template(
        "You are an analytical AI categorizer. Based on the following post titles in the '{category_name}' category, group them into 3 to 6 distinct subtopics.\n\n"
        "Post Titles:\n{context}\n\n"
        "Return the result STRICTLY as a raw JSON object where keys are the subtopic names (strings) and values are the estimated number of posts belonging to that subtopic (integers).\n"
        "Do NOT include any markdown formatting, backticks, or other text. Just the raw JSON object.\n"
        "Example:\n{{\"Server Config\": 5, \"Networking\": 2}}"
    )
    chain = prompt | llm | StrOutputParser()
    try:
        response = chain.invoke({"category_name": cat.name, "context": context_str})
        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        response = response.strip()
        
        data = json.loads(response)
        
        labels = list(data.keys())
        counts = list(data.values())
        
        return {
            "labels": labels,
            "datasets": [{
                "label": "Subtopics",
                "data": counts,
                "backgroundColor": ["#ff6384", "#36a2eb", "#cc65fe", "#ffce56", "#4bc0c0", "#9966ff"]
            }]
        }
    except Exception as e:
        return {"error": f"LLM parsing error. Could not extract valid subtopics. Details: {e}"}

@app.get("/api/category/{category_id}/metrics")
async def category_metrics(category_id: int):
    """Returns post counts per subtopic for visualizations."""
    db = SessionLocal()
    cat = db.query(TopicCategory).filter(TopicCategory.id == category_id).first()
    if not cat:
        db.close()
        return {"error": "Category not found."}
        
    topics = db.query(Topic).filter(Topic.category_id == cat.id).all()
    
    labels = []
    counts = []
    
    for t in topics:
        # Count in Post
        count1 = db.query(Post).filter(Post.topic_id == t.id).count()
        # Count in BrightDataPost
        count2 = db.query(BrightDataPost).filter(BrightDataPost.topic_id == t.id).count()
        labels.append(t.name)
        counts.append(count1 + count2)
        
    db.close()
    return {
        "labels": labels,
        "datasets": [
            {
                "label": "Total Posts",
                "data": counts,
                "backgroundColor": "#4facfe"
            }
        ]
    }

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
    if not cat:
        db.close()
        return {"error": "Category not found."}
        
    log = []
    headers = {
        "Authorization": f"Bearer {BRIGHTDATA_API_KEY}",
        "Content-Type": "application/json"
    }
    url_posts = "https://api.brightdata.com/datasets/v3/scrape?dataset_id=gd_lvz8ah06191smkebj4&notify=false&include_errors=true&type=discover_new&discover_by=keyword"
    payload_posts = {
        "input": [{"keyword": cat.name, "date": req.time_filter, "num_of_posts": req.num_posts}]
    }
    
    print(f"[SCRAPE] Starting batch scrape for '{cat.name}' ({req.num_posts} posts, filter: {req.time_filter})")
    
    # Identify a target topic for association (default to the first one found)
    target_topic = db.query(Topic).filter(Topic.category_id == cat.id).first()
    target_topic_id = target_topic.id if target_topic else None
    
    scraped_posts = _post_brightdata(url_posts, headers, payload_posts, log, timeout=2400)
    for msg in log:
        print(f"[BRIGHTDATA] {msg}")
    log.clear()  # reset for comments phase
    scraped_comments = []
    
    if scraped_posts:
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
                scraped_comments = _post_brightdata(url_comments, headers, {"input": comments_input}, log, timeout=2400)
        
        # Save to DB
        for item in scraped_posts:
            reddit_id = str(item.get("post_id", ""))
            title = item.get("title", "")
            if not db.query(BrightDataPost).filter(BrightDataPost.reddit_id == reddit_id).first():
                new_post = BrightDataPost(
                    reddit_id=reddit_id,
                    title=title[:255],
                    body=(item.get("description") or ""),
                    author=item.get("user_posted", "unknown"),
                    score=item.get("num_upvotes", 0),
                    topic_id=target_topic_id
                )
                db.add(new_post)
        
        for item in scraped_comments:
            comment_id = str(item.get("comment_id", ""))
            
            raw_pid = item.get("post_id")
            if raw_pid is None:
                # Try to extract from URL if BrightData didn't provide post_id
                post_url = item.get("url", "")
                if "/comments/" in post_url:
                    raw_pid = post_url.split("/comments/")[1].split("/")[0]
                    
            post_id = str(raw_pid) if raw_pid else None
            
            if not db.query(BrightDataComment).filter(BrightDataComment.comment_id ==comment_id).first():
                new_com = BrightDataComment(
                    comment_id=comment_id,
                    post_reddit_id=post_id,
                    body=item.get("comment", ""),
                    author=item.get("user_posted", "unknown"),
                    score=item.get("num_upvotes", 0)
                )
                db.add(new_com)
                
        db.commit()
        db.close()
        print(f"[SCRAPE] Done: {len(scraped_posts)} posts, {len(scraped_comments)} comments saved.")
        return {"message": f"Successfully scraped {len(scraped_posts)} posts and {len(scraped_comments)} comments."}
        
    db.close()
    raise HTTPException(status_code=400, detail=f"BrightData returned 0 posts for '{cat.name}'. Check the Python terminal for detailed logs. Try a broader time filter or different category name.")


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
