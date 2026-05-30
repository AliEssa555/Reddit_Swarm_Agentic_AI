import requests
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import BRIGHTDATA_API_KEY, WEBHOOK_URL, TESTING_LIMIT

def trigger_subreddit_discovery(subreddit: str):
    """
    Submits an asynchronous bulk scrape job to Bright Data.
    Bright Data will extract 'TESTING_LIMIT' network requests worth of posts and POST them 
    back to your WEBHOOK_URL when it's done solving captchas and rendering JS.
    """
    print(f"Triggering BrightData Async Scrape for r/{subreddit} (Limit: {TESTING_LIMIT} posts) -> Delivery to {WEBHOOK_URL}")
    
    url = f"https://api.brightdata.com/datasets/v3/trigger"
    params = {
        "dataset_id": "gd_lvz8ah06191smkebj4",  # Posts, Discover endpoint
        "format": "json",
        "type": "discover_new",
        "discover_by": "subreddit_url",
        "webhook": WEBHOOK_URL,
        "uncompressed_webhook": "true" # Required so FastAPI receives flat JSON instead of Gzip
    }
    
    headers = {
        "Authorization": f"Bearer {BRIGHTDATA_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # We heavily restrict cost utilizing the num_of_posts parameter.
    payload = [
        {"url": f"https://www.reddit.com/r/{subreddit}/", "num_of_posts": TESTING_LIMIT}
    ]
    
    response = requests.post(url, params=params, headers=headers, json=payload)
    
    if response.status_code == 200:
        data = response.json()
        snapshot_id = data.get("snapshot_id")
        print(f"Success! Job triggered. Snapshot ID: {snapshot_id}")
        print("Now wait for the Bright Data Webhook to hit your FastAPI server!")
        return snapshot_id
    else:
        print(f"Error accessing BrightData API: {response.text}")
        return None

if __name__ == "__main__":
    # Test triggering a small scrape for r/technology
    trigger_subreddit_discovery("technology")
