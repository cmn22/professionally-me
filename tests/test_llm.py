from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace
import unittest

import litellm

from src.llm import (
    DeploymentLogger,
    LLMConfig,
    LLMConfigurationError,
    LLMServiceError,
    LiteLLMClient,
)


class FakeMessage:
    def __init__(self, data):
        self.data = data

    def model_dump(self, exclude_none=True):
        if exclude_none:
            return {key: value for key, value in self.data.items() if value is not None}
        return self.data


class FakeRouter:
    def __init__(self, response, **kwargs):
        self.response = response
        self.init_kwargs = kwargs
        self.call_kwargs = None

    def completion(self, **kwargs):
        self.call_kwargs = kwargs
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def router_config():
    return {
        "llm": {
            "model_group": "career-chatbot",
            "model_list": [
                {
                    "model_name": "career-chatbot",
                    "litellm_params": {
                        "model": "openrouter/google/gemma-example:free",
                        "order": 1,
                    },
                },
                {
                    "model_name": "career-chatbot",
                    "litellm_params": {
                        "model": "gemini/gemini-example",
                        "order": 2,
                    },
                },
            ],
            "router_settings": {
                "num_retries": 2,
                "timeout": 60,
                "max_fallbacks": 1,
            },
        }
    }


class LLMConfigTests(unittest.TestCase):
    def test_preserves_native_router_configuration(self):
        config = LLMConfig.from_app_config(router_config())

        self.assertEqual(config.model_group, "career-chatbot")
        self.assertEqual(
            [item["litellm_params"]["order"] for item in config.model_list],
            [1, 2],
        )
        self.assertEqual(config.router_settings["num_retries"], 2)

    def test_requires_every_deployment_to_join_the_model_group(self):
        app_config = router_config()
        app_config["llm"]["model_list"][1]["model_name"] = "other-group"

        with self.assertRaises(LLMConfigurationError):
            LLMConfig.from_app_config(app_config)

    def test_requires_positive_order_values(self):
        app_config = router_config()
        app_config["llm"]["model_list"][1]["litellm_params"]["order"] = 0

        with self.assertRaises(LLMConfigurationError):
            LLMConfig.from_app_config(app_config)

    def test_client_uses_router_and_logical_model_group(self):
        response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=FakeMessage(
                        {
                            "role": "assistant",
                            "content": "Hello",
                            "tool_calls": None,
                        }
                    )
                )
            ]
        )
        created = {}

        def fake_router_factory(**kwargs):
            router = FakeRouter(response, **kwargs)
            created["router"] = router
            return router

        config = LLMConfig.from_app_config(router_config())
        client = LiteLLMClient(config, router_factory=fake_router_factory)
        message = client.complete(
            messages=[{"role": "user", "content": "Hi"}], tools=[]
        )

        router = created["router"]
        self.assertEqual(message, {"role": "assistant", "content": "Hello"})
        self.assertEqual(router.init_kwargs["model_list"], config.model_list)
        self.assertEqual(router.init_kwargs["num_retries"], 2)
        self.assertEqual(router.call_kwargs["model"], "career-chatbot")

    def test_service_unavailable_becomes_safe_application_error(self):
        provider_error = litellm.ServiceUnavailableError(
            message="provider unavailable",
            llm_provider="gemini",
            model="gemini-example",
        )

        def fake_router_factory(**kwargs):
            return FakeRouter(provider_error, **kwargs)

        config = LLMConfig.from_app_config(router_config())
        client = LiteLLMClient(config, router_factory=fake_router_factory)

        with self.assertRaisesRegex(LLMServiceError, "temporarily unavailable"):
            client.complete(messages=[], tools=[])

    def test_deployment_logger_excludes_prompts_and_keys(self):
        logger = DeploymentLogger(turn_off_message_logging=True)
        output = StringIO()
        secret = "do-not-log-this-key"

        with redirect_stdout(output):
            provider_error = litellm.ServiceUnavailableError(
                message="provider unavailable",
                llm_provider="gemini",
                model="gemini-example",
            )
            logger.log_failure_event(
                {
                    "model": "gemini/gemini-example",
                    "messages": [{"role": "user", "content": "private prompt"}],
                    "api_key": secret,
                    "exception": provider_error,
                },
                None,
                None,
                None,
            )

        logged = output.getvalue()
        self.assertIn("model=gemini/gemini-example", logged)
        self.assertIn("error=ServiceUnavailableError", logged)
        self.assertNotIn(secret, logged)
        self.assertNotIn("private prompt", logged)


if __name__ == "__main__":
    unittest.main()
