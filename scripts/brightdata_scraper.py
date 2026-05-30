import asyncio
from playwright.async_api import async_playwright

# You will get this from the Bright Data Control Panel (Browser API zone)
# Format: wss://brd-customer-<ID>-zone-<ZONE>:<PASSWORD>@brd.superproxy.io:9222
BRIGHTDATA_WS_URL = "wss://YOUR_BRIGHTDATA_WEBSOCKET_URL"

async def scrape_reddit_realtime(subreddit: str):
    print(f"Connecting to Bright Data Scraping Browser to fetch r/{subreddit}...")
    
    async with async_playwright() as p:
        try:
            # Connect to Bright Data's cloud browser (handles CAPTCHAs and Proxies automatically)
            browser = await p.chromium.connect_over_cdp(BRIGHTDATA_WS_URL)
            
            context = await browser.new_context()
            page = await context.new_page()
            
            # Go directly to the subreddit
            print(f"Navigating to https://www.reddit.com/r/{subreddit}/new/")
            await page.goto(f"https://www.reddit.com/r/{subreddit}/new/", timeout=60000)
            
            # Wait for posts to load
            await page.wait_for_selector('shreddit-post')
            
            # Extract POST details using Javascript evaluation
            posts_data = await page.evaluate('''() => {
                const posts = document.querySelectorAll('shreddit-post');
                const results = [];
                posts.forEach(post => {
                    results.push({
                        title: post.getAttribute('post-title'),
                        author: post.getAttribute('author'),
                        score: post.getAttribute('score'),
                        id: post.getAttribute('id'),
                        url: post.getAttribute('permalink')
                    });
                });
                return results;
            }''')
            
            print(f"\nSuccessfully bypassed bot-detection and extracted {len(posts_data)} real-time posts!")
            for idx, post in enumerate(posts_data[:3]):
                print(f"{idx+1}. {post['title']} (Score: {post['score']})")
                
            await browser.close()
            return posts_data
            
        except Exception as e:
            print(f"Failed to scrape: {e}")

if __name__ == "__main__":
    # Example usage
    asyncio.run(scrape_reddit_realtime("LocalLLaMA"))
