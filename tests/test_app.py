import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

import requests

from app import (
    Me,
    record_unknown_question,
    record_user_details,
    send_slack_notification,
)
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

    def test_system_prompt_is_date_aware_and_requires_two_stage_followup(self):
        client = FakeLLMClient([])
        with TemporaryDirectory() as temp_dir:
            me = self.make_me(temp_dir, client)
            prompt = me.system_prompt()

        self.assertIn("Today is ", prompt)
        self.assertIn("Only describe a role, course, or activity as current", prompt)
        self.assertIn("without waiting for contact details", prompt)
        self.assertIn("a second Slack update", prompt)

    def test_contact_tool_accepts_unanswered_question_context(self):
        client = FakeLLMClient([])
        with TemporaryDirectory() as temp_dir, patch(
            "app.record_user_details", return_value={"recorded": "ok"}
        ) as tool:
            me = self.make_me(temp_dir, client)
            me.handle_tool_call([{
                "id": "call-2",
                "type": "function",
                "function": {
                    "name": "record_user_details",
                    "arguments": json.dumps({
                        "email": "visitor@example.com",
                        "question": "Unknown?",
                    }),
                },
            }])

        tool.assert_called_once_with(
            email="visitor@example.com",
            question="Unknown?",
        )

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


class SlackNotificationTests(unittest.TestCase):
    @patch("app.requests.post")
    def test_sends_notification_to_configured_webhook(self, post):
        response = Mock()
        post.return_value = response

        with patch.dict(
            os.environ,
            {"SLACK_WEBHOOK_URL": "https://hooks.slack.test/services/example"},
            clear=True,
        ):
            delivered = send_slack_notification("Test notification")

        self.assertTrue(delivered)
        post.assert_called_once_with(
            "https://hooks.slack.test/services/example",
            json={"text": "Test notification"},
            timeout=10,
        )
        response.raise_for_status.assert_called_once_with()

    @patch("app.requests.post")
    def test_does_not_send_without_webhook(self, post):
        with patch.dict(os.environ, {}, clear=True):
            delivered = send_slack_notification("Test notification")

        self.assertFalse(delivered)
        post.assert_not_called()

    @patch("app.requests.post", side_effect=requests.RequestException("failed"))
    def test_handles_delivery_failure(self, post):
        with patch.dict(
            os.environ,
            {"SLACK_WEBHOOK_URL": "https://hooks.slack.test/services/example"},
            clear=True,
        ):
            delivered = send_slack_notification("Test notification")

        self.assertFalse(delivered)
        post.assert_called_once()

    @patch("app.send_slack_notification", return_value=True)
    def test_formats_lead_notification_and_escapes_slack_markup(self, send):
        result = record_user_details(
            "visitor@example.com",
            name="Visitor <!channel>",
            notes="Interested in R&D",
        )

        self.assertEqual(result, {"recorded": "ok"})
        send.assert_called_once_with(
            ":incoming_envelope: *New portfolio lead*\n\n"
            "*Name:* Visitor &lt;!channel&gt;\n"
            "*Email:* visitor@example.com\n"
            "*Notes:* Interested in R&amp;D"
        )

    @patch("app.send_slack_notification", return_value=True)
    def test_links_contact_notification_to_unanswered_question(self, send):
        result = record_user_details(
            "visitor@example.com",
            question="What is the <secret> project?",
        )

        self.assertEqual(result, {"recorded": "ok"})
        send.assert_called_once_with(
            ":incoming_envelope: *New portfolio lead*\n\n"
            "*Name:* Name not provided\n"
            "*Email:* visitor@example.com\n"
            "*Notes:* not provided\n"
            "*Follow-up to unanswered question:* What is the &lt;secret&gt; project?"
        )

    @patch("app.send_slack_notification", return_value=False)
    def test_reports_unknown_question_delivery_failure(self, send):
        result = record_unknown_question("Unknown?")

        self.assertEqual(result, {"recorded": "notification_failed"})
        send.assert_called_once_with(
            ":question: *Unanswered portfolio question*\n\n"
            "*Question:* Unknown?"
        )


if __name__ == "__main__":
    unittest.main()
