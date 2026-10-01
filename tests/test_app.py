import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from app import Me
from src.llm import LLMServiceError


class FakeLLMClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def complete(self, messages, tools):
        self.calls.append({"messages": list(messages), "tools": tools})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class ChatTests(unittest.TestCase):
    def make_me(self, temp_dir, client):
        root = Path(temp_dir)
        (root / "data").mkdir()
        (root / "data" / "linkedin_clean.json").write_text(
            json.dumps({"headline": "Software engineer"}), encoding="utf-8"
        )
        config_path = root / "config.json"
        config_path.write_text(
            json.dumps({
                "name": "Test Person",
                "llm": {
                    "model_group": "career-chatbot",
                    "model_list": [
                        {
                            "model_name": "career-chatbot",
                            "litellm_params": {
                                "model": "openai/test-model",
                                "order": 1,
                            },
                        }
                    ],
                    "router_settings": {},
                },
            }),
            encoding="utf-8",
        )
        return Me(config_path=config_path, llm_client=client)

    def test_returns_provider_response(self):
        client = FakeLLMClient([
            {"role": "assistant", "content": "Hello from the model."}
        ])
        with TemporaryDirectory() as temp_dir:
            me = self.make_me(temp_dir, client)
            result = me.chat("Hello", [])

        self.assertEqual(result, "Hello from the model.")
        self.assertEqual(client.calls[0]["messages"][-1]["content"], "Hello")

    def test_executes_tool_and_returns_followup(self):
        client = FakeLLMClient([
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": "call-1",
                    "type": "function",
                    "function": {
                        "name": "record_unknown_question",
                        "arguments": json.dumps({"question": "Unknown?"}),
                    },
                }],
            },
            {"role": "assistant", "content": "I don't know that yet."},
        ])

        with TemporaryDirectory() as temp_dir, patch(
            "app.record_unknown_question", return_value={"recorded": "ok"}
        ) as tool:
            me = self.make_me(temp_dir, client)
            result = me.chat("Unknown?", [])

        self.assertEqual(result, "I don't know that yet.")
        tool.assert_called_once_with(question="Unknown?")
        tool_result = client.calls[1]["messages"][-1]
        self.assertEqual(tool_result["role"], "tool")
        self.assertEqual(tool_result["tool_call_id"], "call-1")

    def test_returns_safe_provider_error(self):
        client = FakeLLMClient([LLMServiceError("Provider is unavailable.")])
        with TemporaryDirectory() as temp_dir:
            me = self.make_me(temp_dir, client)
            result = me.chat("Hello", [])

        self.assertIn("Provider is unavailable.", result)


if __name__ == "__main__":
    unittest.main()
