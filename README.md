---
title: professionally-me
emoji: 💼
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: "5.33.0"
app_file: app.py
pinned: false
---

# Professionally Me

A personal career chatbot that impersonates you on your website. It answers questions about your background, skills, and experience, steers visitors toward leaving their contact details, and logs any unanswerable questions — all via a Gradio chat UI.

## How it works

- The bot stays in character using your LinkedIn profile as its knowledge base.
- When a visitor shares their email, a Pushover notification fires instantly.
- Questions the bot can't answer are also logged via Pushover.
- The LLM is accessed via [OpenRouter](https://openrouter.ai), so you can swap models in `config.json` without touching code.

## Setup (self-hosting)

```bash
uv sync
# edit config.json — set your name, LinkedIn URL, Apify actor ID, and model
# copy .env and fill in OPENROUTER_KEY, APIFY_TOKEN, PUSHOVER_TOKEN, PUSHOVER_USER
uv run python refresh_data.py   # scrape + clean your LinkedIn profile
uv run python app.py
```

## Tech stack

- [Gradio](https://gradio.app) — chat UI
- [OpenRouter](https://openrouter.ai) — LLM provider
- [Apify](https://apify.com) (`harvestapi/linkedin-profile-scraper`) — LinkedIn data
- [Pushover](https://pushover.net) — real-time notifications
