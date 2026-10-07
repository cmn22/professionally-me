# Professionally Me

**Professionally Me** is a personal career chatbot that impersonates you on your website. It answers questions about your background, skills, and experience, steers visitors toward leaving their contact details, and logs any unanswerable questions.

## How it works

1. Your LinkedIn profile is scraped via [Apify](https://apify.com) and cleaned to remove noise, reducing token usage by ~80%.
2. The cleaned profile is injected into the LLM's system prompt.
3. [LiteLLM](https://docs.litellm.ai/) provides one interface for OpenAI, Anthropic, Google Gemini, OpenRouter, and other model providers.
4. The LLM uses two tools — `record_user_details` and `record_unknown_question` — to send real-time notifications to a Slack channel.
5. The chat UI is built with [Gradio](https://gradio.app) and can be embedded on any website.
6. The bot stays in character using your LinkedIn profile as its knowledge base.
7. Questions the bot can't answer are sent to Slack immediately, before asking the visitor for contact details.
8. The bot then offers a follow-up. If the visitor shares their email, a second Slack notification includes both their details and the unanswered question.
9. The system prompt includes today's date and interprets dated LinkedIn entries relative to it, avoiding stale claims that past work or education is still current.

---

## Tech Stack

| Component | Tool |
|---|---|
| Chat UI | [Gradio](https://gradio.app) 5.33.0 |
| LLM Interface | [LiteLLM](https://docs.litellm.ai/) |
| LLM Providers | OpenAI, Anthropic, Google Gemini, OpenRouter, and more |
| LinkedIn Scraping | [Apify](https://apify.com) — `harvestapi/linkedin-profile-scraper` |
| Notifications | [Slack incoming webhooks](https://api.slack.com/messaging/webhooks) |
| Package Manager | [uv](https://docs.astral.sh/uv/) |

---

## Prerequisites

Before getting started, you will need accounts and API keys for the following:

- **One LLM provider** — create an API key with OpenAI, Anthropic, Google Gemini, or OpenRouter
- **Apify** — [apify.com](https://apify.com) → Settings → Integrations → API token
- **Slack workspace** — see the incoming webhook steps below

### Getting a Slack Webhook URL

The app sends lead details and unanswered questions to a Slack channel using an incoming webhook.

1. Go to [Slack API: Your Apps](https://api.slack.com/apps) and create an app from scratch.
2. Select the Slack workspace that should receive notifications.
3. Open **Incoming Webhooks** and turn on **Activate Incoming Webhooks**.
4. Select **Add New Webhook to Workspace** and choose the destination channel.
5. Copy the generated webhook URL. Treat it as a secret because anyone with it can post to that channel.

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
  "llm": {
    "model_group": "career-chatbot",
    "model_list": [
      {
        "model_name": "career-chatbot",
        "litellm_params": {
          "model": "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free",
          "order": 1
        }
      },
      {
        "model_name": "career-chatbot",
        "litellm_params": {
          "model": "gemini/gemini-3.8-flash",
          "order": 2
        }
      }
    ],
    "router_settings": {
      "num_retries": 2,
      "timeout": 60,
      "allowed_fails": 1,
      "cooldown_time": 30,
      "max_fallbacks": 1
    }
  }
}
```

Every deployment uses the same logical `model_name` so LiteLLM groups them behind one application-facing model. The deployment with the lowest `order` is attempted first. If it remains unavailable after retries, LiteLLM moves to the next order, manages cooldowns, and later restores recovered deployments.

Models use LiteLLM's native `<provider>/<model>` identifiers. LiteLLM determines the provider and reads that provider's standard environment variable automatically.

### 4. Set environment variables

Create a `.env` file in the project root:

```
# Both keys are required for the default primary/fallback configuration:
OPENROUTER_API_KEY=your_openrouter_api_key
GEMINI_API_KEY=your_gemini_api_key

APIFY_TOKEN=your_apify_api_token
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/your/webhook/url
```

Use LiteLLM's standard key names. The previous `OPENROUTER_KEY` variable must be renamed to `OPENROUTER_API_KEY`. Add keys for any additional deployments you place in `model_list`, such as `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`.

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
| `OPENROUTER_API_KEY` | Primary OpenRouter deployment |
| `GEMINI_API_KEY` | Google Gemini fallback deployment |
| `SLACK_WEBHOOK_URL` | Incoming webhook for the Slack notification channel |

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
