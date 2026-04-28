"""Fetch and clean LinkedIn data from scratch.

Run this once before starting the app, or any time you want to refresh your profile data.

    uv run python refresh_data.py

Reads config.json for your LinkedIn URL and Apify actor, then:
  1. Scrapes LinkedIn via Apify  →  data/linkedin.json
  2. Cleans the raw JSON         →  data/linkedin_clean.json
"""
from src.fetch_linkedin import main as fetch
from src.clean_linkedin import main as clean

if __name__ == "__main__":
    fetch()
    clean()
