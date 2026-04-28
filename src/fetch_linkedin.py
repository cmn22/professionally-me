import json
import os
from apify_client import ApifyClient
from dotenv import load_dotenv

load_dotenv(override=True)

CONFIG_PATH = "config.json"
OUTPUT_PATH = "data/linkedin.json"


def fetch_linkedin_profile(linkedin_url: str, actor_id: str) -> list:
    client = ApifyClient(os.getenv("APIFY_TOKEN"))
    run = client.actor(actor_id).call(run_input={
        "queries": [linkedin_url],
        "profileScraperMode": "Profile details no email ($4 per 1k)",
    })
    return list(client.dataset(run["defaultDatasetId"]).iterate_items())


def main():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    linkedin_url = config["linkedin_url"]
    actor_id = config["apify_actor_id"]

    print(f"Scraping {linkedin_url} via Apify actor {actor_id} ...")
    profiles = fetch_linkedin_profile(linkedin_url, actor_id)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(profiles, f, indent=2, ensure_ascii=False)

    print(f"Saved {len(profiles)} profile(s) to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
