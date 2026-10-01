# Repository Guide

This file is the starting point for coding assistants working in this repository. Read it before scanning the codebase. Use `README.md` for user-facing setup and deployment instructions.

## Project purpose

Professionally Me is a Gradio career chatbot that answers as the profile owner using cleaned LinkedIn data. It uses LiteLLM for provider-agnostic model routing and a Slack incoming webhook for lead and unknown-question notifications.

## Architecture map

- `app.py`: Application entry point, Gradio UI, system prompt, chat/tool-call loop, and Slack notification tools.
- `src/llm.py`: LiteLLM configuration validation, Router construction, provider-error translation, and privacy-safe deployment logging.
- `config.json`: Identity, LinkedIn scraper settings, LiteLLM model group, ordered deployments, and Router settings.
- `refresh_data.py`: Runs the LinkedIn fetch and cleanup pipeline.
- `src/fetch_linkedin.py`: Fetches the configured LinkedIn profile through Apify into `data/linkedin.json`.
- `src/clean_linkedin.py`: Reduces the raw profile to `data/linkedin_clean.json` for prompt use.
- `tests/test_app.py`: Chat flow, tool execution, and safe-error tests using fake LLM clients.
- `tests/test_llm.py`: Router configuration, model aliasing, error handling, and secure logging tests.
- `.env.example`: Supported environment-variable names only; never put real credentials here.

## LLM routing design

The application calls one logical model group, currently `career-chatbot`. Every item in `llm.model_list` must use that same value as `model_name`.

Each deployment's `litellm_params.model` uses LiteLLM's native `<provider>/<model>` format. LiteLLM infers the provider and reads its standard environment variable. The deployment with the lowest positive integer `order` is primary; later orders are fallbacks. Retries, timeouts, cooldowns, and fallback limits belong in `llm.router_settings` and are passed directly to `litellm.Router`.

Default routing:

1. OpenRouter: `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free`
2. Google Gemini fallback: `gemini/gemini-3.8-flash`

Do not add provider-selection conditionals to application code. Add or reorder deployments in `config.json`; keep provider-neutral behavior in `src/llm.py`.

## Environment variables

The default runtime configuration requires:

- `OPENROUTER_API_KEY`: primary LLM deployment
- `GEMINI_API_KEY`: fallback LLM deployment
- `SLACK_WEBHOOK_URL`: runtime notifications through a Slack incoming webhook

Data refresh additionally requires `APIFY_TOKEN`. Other deployments use their LiteLLM-standard variables, such as `OPENAI_API_KEY` and `ANTHROPIC_API_KEY`.

The local `.env` is ignored by Git. Never read out, print, commit, or place secret values in logs, test output, documentation, or prompts.

## Common commands

Install or update dependencies:

```bash
uv sync
```

Run all offline tests:

```bash
uv run python -m unittest discover -s tests -v
```

Run fast syntax and whitespace checks:

```bash
uv run python -m compileall -q app.py src tests
git diff --check
```

Start the application in the visible terminal:

```bash
uv run python app.py
```

Then open `http://127.0.0.1:7860`. Stop it with Ctrl+C.

Refresh profile data only when requested, because this makes a paid/external Apify call:

```bash
uv run python refresh_data.py
```

## Change and verification rules

- Keep `app.py` dependent on the `LiteLLMClient` abstraction rather than a provider SDK.
- Preserve dependency injection (`llm_client` and `router_factory`) so offline tests do not call external services.
- Add or update tests for changes to routing, configuration validation, error mapping, or the tool-call loop.
- Automated tests must not make network calls or require real API keys.
- Live provider tests should be deliberate, use a harmless minimal prompt, and never include the LinkedIn profile or secrets unless the user specifically requests a full chatbot test.
- Routing logs may include model, exception class, and HTTP status only. They must not include prompts, responses, tool arguments, or API keys.
- Preserve the friendly `LLMServiceError` boundary so provider internals are not shown to chatbot users.
- The chat loop intentionally caps consecutive tool-call rounds at eight.
- `data/linkedin_clean.json` is preferred at runtime; `data/linkedin.json` is the fallback. Both files are tracked and can contain personal data, so avoid exposing their contents unnecessarily.
- Keep `README.md`, `.env.example`, and this guide synchronized when configuration or commands change.

## Definition of done

Before handing off a code change:

1. Run the offline test suite.
2. Run compilation and `git diff --check`.
3. Check `git status --short --branch` and report any pre-existing or new changes accurately.
4. For routing changes, perform a live primary/fallback test only when credentials are available and the user has authorized real provider calls.
5. Do not push, deploy, refresh LinkedIn data, or send test Slack notifications unless explicitly requested.
