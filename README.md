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

**Professionally Me** is a personal career chatbot that impersonates you on your website. It answers questions about your background, skills, and experience, steers visitors toward leaving their contact details, and logs any unanswerable questions.

## How it works

1. Your LinkedIn profile is scraped via [Apify](https://apify.com) and cleaned to remove noise, reducing token usage by ~80%.
2. The cleaned profile is injected into the LLM's system prompt.
3. The LLM uses two tools — `record_user_details` and `record_unknown_question` — to send you real-time Pushover notifications.
4. The chat UI is built with [Gradio](https://gradio.app) and can be embedded on any website.
5. The bot stays in character using your LinkedIn profile as its knowledge base.
6. When a visitor shares their email, a Pushover notification fires instantly.
7. Questions the bot can't answer are also logged via Pushover.

---

## Tech Stack

| Component | Tool |
|---|---|
| Chat UI | [Gradio](https://gradio.app) 5.33.0 |
| LLM Provider | [OpenRouter](https://openrouter.ai) |
| LinkedIn Scraping | [Apify](https://apify.com) — `harvestapi/linkedin-profile-scraper` |
| Push Notifications | [Pushover](https://pushover.net) |
| Package Manager | [uv](https://docs.astral.sh/uv/) |

---

## Prerequisites

Before getting started, you will need accounts and API keys for the following:

- **OpenRouter** — [openrouter.ai](https://openrouter.ai) → Create account → Keys → Create Key
- **Apify** — [apify.com](https://apify.com) → Settings → Integrations → API token
- **Pushover** — see detailed steps below

### Getting Pushover Credentials

Pushover sends instant notifications to your phone when someone interacts with the bot.

1. Go to [pushover.net](https://pushover.net) and create a free account.
2. After signing in, your **User Key** is shown on the dashboard — copy it. This is your `PUSHOVER_USER`.
3. Scroll down to **Your Applications** and click **Create an Application/API Token**.
4. Give it a name (e.g. `Professionally Me`) and click **Create Application**.
5. Copy the **API Token** shown on the next page. This is your `PUSHOVER_TOKEN`.
6. Install the Pushover app on your phone ([iOS](https://apps.apple.com/app/pushover-notifications/id506088175) / [Android](https://play.google.com/store/apps/details?id=net.superblock.pushover)) and log in.

---

## Local Setup

### 1. Clone the repository

```bash
git clone https://github.com/cmn22/professionally-me.git
cd professionally-me
```

### 2. Install dependencies

This project uses [uv](https://docs.astral.sh/uv/getting-started/installation/) as its package manager.

```bash
uv sync
```

### 3. Configure your identity

Edit `config.json` with your own details:

```json
{
  "name": "Your Full Name",
  "linkedin_url": "https://www.linkedin.com/in/your-profile",
  "apify_actor_id": "LpVuK3Zozwuipa5bp",
  "model": "openai/gpt-oss-120b:free"
}
```

> **Model**: Any model available on OpenRouter works here. Browse options at [openrouter.ai/models](https://openrouter.ai/models).

### 4. Set environment variables

Create a `.env` file in the project root:

```
OPENROUTER_KEY=your_openrouter_api_key
APIFY_TOKEN=your_apify_api_token
PUSHOVER_TOKEN=your_pushover_app_token
PUSHOVER_USER=your_pushover_user_key
```

### 5. Fetch your LinkedIn data

This scrapes your LinkedIn profile via Apify and generates the cleaned JSON the bot uses:

```bash
uv run python refresh_data.py
```

> Re-run this command any time your LinkedIn profile changes.

### 6. Run the app

```bash
uv run python app.py
```

Open [http://localhost:7860](http://localhost:7860) in your browser.

---

## Deploying to Hugging Face Spaces

Hugging Face Spaces offers free Gradio hosting and is the recommended way to make this publicly accessible.

### 1. Create a Space

1. Go to [huggingface.co](https://huggingface.co) and sign in.
2. Click your profile → **New Space**.
3. Fill in the name (e.g. `professionally-me`), select **Gradio** as the SDK, and set visibility to **Public**.
4. Select **Blank** as the template and choose **MIT** licence. Click **Create Space**.

### 2. Add your secrets

In your Space, go to **Settings → Variables and Secrets** and add the following as **Secrets**:

| Secret | Value |
|---|---|
| `OPENROUTER_KEY` | Your OpenRouter API key |
| `PUSHOVER_TOKEN` | Your Pushover app token |
| `PUSHOVER_USER` | Your Pushover user key |

> `APIFY_TOKEN` is only needed locally to run `refresh_data.py` — it is not required at runtime on HF Spaces.

### 3. Push your code

Add the HF Space as a git remote and push a clean single commit (no history) to avoid binary file issues:

```bash
git remote add space https://huggingface.co/spaces/<your-hf-username>/<your-space-name>
git checkout --orphan hf-deploy
git add -A
git commit -m "Deploy to HF Spaces"
git push space hf-deploy:main --force
git checkout master
git branch -D hf-deploy
```

The Space will build automatically. Watch the progress under the **App** tab's build logs.

### 4. Embed on your website

Once the Space is live, embed the chatbot on your website using Gradio's web component:

```html
<script type="module" src="https://gradio.s3-us-west-2.amazonaws.com/5.33.0/gradio.js"></script>
<gradio-app src="https://<your-hf-username>-<your-space-name>.hf.space"></gradio-app>
```

Or as a plain iframe:

```html
<iframe
  src="https://<your-hf-username>-<your-space-name>.hf.space"
  width="100%"
  height="600px"
  frameborder="0">
</iframe>
```
