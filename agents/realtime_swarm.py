import sys
import os
import requests
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from typing import TypedDict
from langgraph.graph import StateGraph, END
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from services.llm_client import get_llm
from config import BRIGHTDATA_API_KEY, TESTING_LIMIT, TESTING_COMMENTS_LIMIT
from db.database import SessionLocal
from db.models import BrightDataPost, BrightDataComment, AgentRun

class LiveSwarmState(TypedDict):
    original_query: str
    search_keyword: str
    raw_scraped_data: list
    raw_scraped_comments: list
    final_response: str
    log_messages: list

try:
    llm = get_llm(temperature=0.3)
except Exception as e:
    llm = None
    print(f"FAILED TO INITIATE LLM: {e}")

def keyword_extractor_node(state: LiveSwarmState):
    log = []
    log.append(">>> AGENT: Keyword Extractor Working...")
    
    if not llm:
        log.append("  -> CRITICAL ERROR: LLM is completely offline. Skipping extraction.")
        return {"search_keyword": "technology", "log_messages": state.get("log_messages", []) + log}
        
    prompt = ChatPromptTemplate.from_template(
        "You are an expert NLP keyword extractor. Analyze the user question and extract ONLY the core subject or entity (the 'about' part) in exactly ONE search keyword phrase in ENGLISH.\n"
        "Avoid meta-words like 'opinions', 'reddit', 'what', 'saying'. Focus on the topic itself (e.g. 'nuclear energy', 'quantum computing', 'US economy').\n"
        "User Question: {query}\n"
        "Keyword (ENGLISH ONLY, SUBJECT ONLY, NO QUOTES):"
    )
    chain = prompt | llm | StrOutputParser()
    try:
        kw = chain.invoke({"query": state["original_query"]}).strip()
        log.append(f"  -> Extracted Search Keyword: '{kw}'")
        return {"search_keyword": kw, "log_messages": [msg for msg in state.get("log_messages", [])] + log}
    except Exception as e:
        log.append(f"  -> ERROR LLM offline or rejecting: {e}")
        return {"search_keyword": "technology", "log_messages": [msg for msg in state.get("log_messages", [])] + log} 

def _poll_snapshot(snapshot_id: str, headers: dict, log: list) -> list:
    """BrightData's sync discover endpoints return a snapshot_id when they run over 60s.
    This polls their /snapshot endpoint until data is ready (max 20 minutes)."""
    import time
    log.append(f"  -> BrightData returned snapshot_id: {snapshot_id}. Polling for results...")
    poll_url = f"https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}?format=json"
    
    for attempt in range(120):  # Poll every 10s for up to 20 minutes
        time.sleep(10)
        try:
            r = requests.get(poll_url, headers=headers, timeout=30)
            if r.status_code == 200:
                try:
                    data = r.json()
                except Exception:
                    # Handle NDJSON streamed responses
                    raw_lines = r.text.strip().split('\n')
                    data = [json.loads(line) for line in raw_lines if line.strip()]
                if isinstance(data, list) and len(data) > 0:
                    log.append(f"  -> Snapshot ready! Received {len(data)} records after {(attempt+1)*10}s.")
                    return data
                # 200 but empty list means still preparing, keep polling
                log.append(f"  -> Snapshot processing... ({(attempt+1)*10}s elapsed)")
            elif r.status_code == 202:
                log.append(f"  -> Snapshot still processing... ({(attempt+1)*10}s elapsed)")
            else:
                log.append(f"  -> Snapshot poll error: {r.status_code} - {r.text[:100]}")
                break
        except Exception as e:
            log.append(f"  -> Poll attempt failed: {e}")
    
    log.append("  -> Snapshot polling exhausted with no data.")
    return []

def _post_brightdata(url: str, headers: dict, payload: dict, log: list, timeout: int = 90) -> list:
    """Makes a BrightData POST, handling both immediate results and snapshot_id fallback."""
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=timeout)
        try:
            # First try standard JSON array/object
            data = response.json()
        except Exception:
            # Fallback: BrightData often returns 'JSON Lines' (NDJSON) if results are streamed
            try:
                raw_lines = response.text.strip().split('\n')
                data = [json.loads(line) for line in raw_lines if line.strip()]
                log.append(f"  -> Successfully parsed {len(data)} records from multi-line JSON.")
            except Exception as e:
                log.append(f"  -> ERROR: Persistent JSON parsing failure. Status: {response.status_code}")
                preview = response.text[:200].replace('\n', ' ')
                log.append(f"  -> RAW RESPONSE PREVIEW: {preview}")
                return []

        # 200 with a list = data came back directly (fast path)
        if response.status_code == 200 and isinstance(data, list):
            return data

        # 200 or 202 with snapshot_id = job is still running, poll for it
        if isinstance(data, dict) and data.get("snapshot_id"):
            return _poll_snapshot(data["snapshot_id"], headers, log)

        log.append(f"  -> ERROR from BrightData: {response.status_code} {str(data)[:200]}")
    except requests.exceptions.Timeout:
        log.append(f"  -> Request timed out after {timeout}s. Try reducing BRIGHTDATA_MAX_POSTS_LIMIT in .env.")
    except Exception as e:
        log.append(f"  -> ERROR HTTP failure: {e}")
    return []

def scraper_node(state: LiveSwarmState):
    log = []
    log.append(f">>> TOOL: BrightData Scraper Initiated for keyword '{state.get('search_keyword')}'...")
    
    headers = {
        "Authorization": f"Bearer {BRIGHTDATA_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # 1. SCRAPE POSTS via keyword discovery
    fetch_limit = min(TESTING_LIMIT, 20)
    url_posts = "https://api.brightdata.com/datasets/v3/scrape?dataset_id=gd_lvz8ah06191smkebj4&notify=false&include_errors=true&type=discover_new&discover_by=keyword"
    payload_posts = {
        "input": [{"keyword": state.get("search_keyword", "news"), "date": "Past week", "num_of_posts": fetch_limit}]
    }
    
    scraped_posts = _post_brightdata(url_posts, headers, payload_posts, log)
    if scraped_posts:
        log.append(f"  -> Posts stage complete: {len(scraped_posts)} posts scraped.")

    # 2. SCRAPE COMMENTS from top post URLs
    scraped_comments = []
    if scraped_posts:
        log.append(f"  -> Fetching comments (limit {TESTING_COMMENTS_LIMIT}/post) from top 3 posts...")
        url_comments = "https://api.brightdata.com/datasets/v3/scrape?dataset_id=gd_lvzdpsdlw09j6t702&notify=false&include_errors=true"
        
        comments_input = []
        for p in scraped_posts[:3]:
            if p.get("url"):
                comments_input.append({
                    "url": p.get("url"),
                    "days_back": 180,
                    "load_all_replies": False,
                    "comment_limit": TESTING_COMMENTS_LIMIT
                })
        
        if comments_input:
            scraped_comments = _post_brightdata(url_comments, headers, {"input": comments_input}, log)
            if scraped_comments:
                log.append(f"  -> Comments stage complete: {len(scraped_comments)} comments scraped.")

    return {
        "raw_scraped_data": scraped_posts,
        "raw_scraped_comments": scraped_comments,
        "log_messages": state.get("log_messages", []) + log
    }

def database_writer_node(state: LiveSwarmState):
    log = []
    log.append(f">>> SYSTEM: Postgres Interactor Working...")
         
    try:
        db = SessionLocal()
        inserted_posts = 0
        inserted_comments = 0
        
        for item in state.get("raw_scraped_data", []):
            reddit_id = str(item.get("post_id", ""))
            title = item.get("title", "")
            
            if not db.query(BrightDataPost).filter(BrightDataPost.reddit_id == reddit_id).first():
                new_post = BrightDataPost(
                    reddit_id=reddit_id,
                    title=title[:255],
                    body=(item.get("description") or ""),
                    author=item.get("user_posted", "unknown"),
                    score=item.get("num_upvotes", 0),
                    snapshot_id="sync_discover_live"
                )
                db.add(new_post)
                inserted_posts += 1
                
        for item in state.get("raw_scraped_comments", []):
            comment_id = str(item.get("comment_id", ""))
            post_id = str(item.get("post_id", ""))
            if not db.query(BrightDataComment).filter(BrightDataComment.comment_id == comment_id).first():
                new_com = BrightDataComment(
                    comment_id=comment_id,
                    post_reddit_id=post_id,
                    body=item.get("comment", ""),
                    author=item.get("user_posted", "unknown"),
                    score=item.get("num_upvotes", 0),
                    snapshot_id="sync_discover_live"
                )
                db.add(new_com)
                inserted_comments += 1
                
        db.commit()
        db.close()
        log.append(f"  -> Wrote {inserted_posts} fresh posts and {inserted_comments} comments safely to PostgreSQL.")
    except Exception as e:
        log.append(f"  -> ERROR writing to DB: {e}")
        
    return {"log_messages": state.get("log_messages", []) + log}

def synthesizer_node(state: LiveSwarmState):
    log = []
    log.append(f">>> AGENT: Synthesizer Response Generator Working...")
    
    if not llm:
        log.append("  -> CRITICAL ERROR: LLM is completely offline. Skipping synthesis.")
        msg = f"Sorry, your local LLM server is disconnected. But I successfully scraped and saved {len(state.get('raw_scraped_data', []))} raw posts to your memory!"
        return {"final_response": msg, "log_messages": state.get("log_messages", []) + log}
        
    if not state.get("raw_scraped_data"):
        return {"final_response": "I'm sorry, I could not fetch any real-time data from Bright Data. Please check your API credits or the connection limit.", "log_messages": state.get("log_messages", []) + log}
        
    context_str = "--- TOP REDDIT POSTS ---\n"
    # Only feed top 5 posts into the LLM logic to avoid destroying local context windows
    for idx, post in enumerate(state["raw_scraped_data"][:5]): 
        context_str += f"Title: {post.get('title')}\nBodyText: {(post.get('description') or '')[:200]}...\nUpvotes: {post.get('num_upvotes')}\n\n"
        
    if state.get("raw_scraped_comments"):
        context_str += "--- TOP REDDIT COMMENTS (What users are saying) ---\n"
        for comment in state["raw_scraped_comments"][:15]:
            context_str += f"User '{comment.get('user_posted', 'anon')}' says: {comment.get('comment', '')[:200]} (Upvotes: {comment.get('num_upvotes')})\n"
            
    prompt = ChatPromptTemplate.from_template(
        "You are an analytical Reddit AI researcher. Based on the following real-time scraped posts and comments, answer the user's question directly and concisely.\n"
        "User Question: {query}\n\n"
        "Live Reddit Data:\n{context}\n\n"
        "Synthesize what redditors are saying accurately and concisely (Keep it tight):"
    )
    chain = prompt | llm | StrOutputParser()
    try:
        response = chain.invoke({"query": state["original_query"], "context": context_str})
        log.append(f"  -> Synthesized an intelligent, comment-aware analytical response for frontend display.")
        return {"final_response": response, "log_messages": state.get("log_messages", []) + log}
    except Exception as e:
        log.append(f"  -> ERROR LLM offline during synthesis: {e}")
        return {"final_response": f"Error: Local LLM threw an exception during synthesis: {e}", "log_messages": state.get("log_messages", []) + log}

def log_to_db_node(state: LiveSwarmState):
    """Stores the execution trace for the Vue evaluators."""
    try:
        db = SessionLocal()
        logs_joined = "\n".join(state.get("log_messages", []))
        
        new_run = AgentRun(
            agent_name="RealTime Sync Swarm",
            task=state.get("original_query", ""),
            result=state.get("final_response", ""),
            evaluation_result=logs_joined
        )
        db.add(new_run)
        db.commit()
        db.close()
    except Exception as e:
        pass # Not critical to frontend return flow
    return {}

workflow = StateGraph(LiveSwarmState)
workflow.add_node("keyword_extractor", keyword_extractor_node)
workflow.add_node("scraper", scraper_node)
workflow.add_node("db_writer", database_writer_node)
workflow.add_node("synthesizer", synthesizer_node)
workflow.add_node("logger", log_to_db_node)

workflow.set_entry_point("keyword_extractor")
workflow.add_edge("keyword_extractor", "scraper")
workflow.add_edge("scraper", "db_writer")
workflow.add_edge("db_writer", "synthesizer")
workflow.add_edge("synthesizer", "logger")
workflow.add_edge("logger", END)

# Expose compiled swarm for FastAPI execution
live_swarm = workflow.compile()
