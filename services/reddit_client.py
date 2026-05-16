import asyncpraw
import os
from dotenv import load_dotenv

load_dotenv()

async def get_reddit_client():
    reddit = asyncpraw.Reddit(
        client_id=os.getenv("REDDIT_CLIENT_ID"),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        user_agent=os.getenv("REDDIT_USER_AGENT", "windows:reddit-intelligence-swarm:v1.0 (by /u/YourUsername)")
    )
    return reddit

async def fetch_top_posts(subreddit_name: str, limit: int = 10):
    reddit = await get_reddit_client()
    subreddit = await reddit.subreddit(subreddit_name)
    posts = []
    
    async for submission in subreddit.top("week", limit=limit):
        posts.append({
            "reddit_id": submission.id,
            "title": submission.title,
            "body": submission.selftext,
            "author": submission.author.name if submission.author else "[deleted]",
            "score": submission.score,
            "created_utc": submission.created_utc
        })
        
    await reddit.close()
    return posts
