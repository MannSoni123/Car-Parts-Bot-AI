import requests
import os
from dotenv import load_dotenv

load_dotenv()
SCRAPER_API_KEY = os.getenv("SCRAPER_API_KEY")

url = "https://partsouq.com/en/search/all?q=WBY22CF020CN37008"
payload = {"api_key": SCRAPER_API_KEY, "url": url, "render": "false", "keep_headers": "true"}

print(f"Testing ScraperAPI with key: {SCRAPER_API_KEY}")
resp = requests.get("http://api.scraperapi.com", params=payload)
print(f"Status Code: {resp.status_code}")
if resp.status_code == 200:
    print("Success! Key works!")
else:
    print(f"Failed. Content: {resp.text[:200]}")
