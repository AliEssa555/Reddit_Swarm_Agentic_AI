# Bright Data Webhook & Cost Management Integration

We have totally eliminated the need for manual CSV mapping or battling Reddit's API Rate limits. The new ingestion system leverages Bright Data's `discover` Webhook mechanism.

## 1. Safety Limits & Configuration
Your biggest protection against burning thousands of API credits instantly is the `config.py` file. I have implemented a hard global boundary variable.

Inside your `.env` file, please define:

```ini
BRIGHTDATA_API_KEY=your_key_here
BRIGHTDATA_MAX_POSTS_LIMIT=5    # Set very low (5) during development. Up to 500 when building the production DB!
WEBHOOK_URL=https://your-ngrok-or-webhook-site.com/webhook/reddit
```

## 2. Setting Up the Webhook Listener
The system operates asynchronously.
1. Our backend asks Bright Data: "Hey, fetch 500 posts from r/MachineLearning"
2. The python script immediately returns success (no frozen code).
3. Bright Data's server spins up real browsers, navigates the site, bypasses the firewalls, and extracts structured data.
4. When finished, they hit our FastAPI endpoint.

To capture this data on your personal computer:
1. Open a new terminal and run the API: `python api/main.py`. This starts local webserver on port `8000`.
2. To allow Bright Data to "see" your localhost across the internet, you can use [ngrok](https://ngrok.com/).
   ```bash
   ngrok http 8000
   ```
3. Ngrok gives you a public URL (e.g., `https://e843-12-32.ngrok-free.app`). Set this as your `WEBHOOK_URL` in the `.env` file (remember to add `/webhook/reddit` to the end)!

## 3. Triggering a Scrape Job
Whenever you want fresh database data, run:
`python services/brightdata_client.py`

This will trigger Bright Data over the boundary settings. 30 seconds later, you'll see your `api/main.py` terminal instantly ingest all of those elements straight through the NLP hierarchy logic and into the permanent SQL engine!
