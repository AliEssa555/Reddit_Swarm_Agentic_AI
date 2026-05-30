import os
from dotenv import load_dotenv

# Load all variables from .env automatically
load_dotenv()

# --- BRIGHT DATA SAFETY CONFIGS ---
# This is a hard limit on how many posts to scrape per API trigger.
# To save you credits while testing, it defaults to a very cheap 5 posts.
# Change this to 100 or 500 in your .env (BRIGHTDATA_MAX_POSTS_LIMIT=500) when you are ready for production data.
TESTING_LIMIT = int(os.getenv('BRIGHTDATA_MAX_POSTS_LIMIT', 25))

# Your API Key from Bright Data Control Panel
BRIGHTDATA_API_KEY = os.getenv('BRIGHTDATA_API_KEY', '')

# Since you need a public URL for Webhooks:
# Set up an ngrok URL (e.g. https://xyz.ngrok.app/webhook/reddit) or a webhook.site testing URL
WEBHOOK_URL = os.getenv('WEBHOOK_URL', 'https://webhook.site/temp-url-here/webhook/reddit')
