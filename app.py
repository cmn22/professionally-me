from dotenv import load_dotenv
from datetime import date
import json
import os
from pathlib import Path
import requests
import gradio as gr

from src.llm import LLMConfig, LLMServiceError, LiteLLMClient


load_dotenv(override=True)


def escape_slack_text(value):
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(
        ">", "&gt;"
    )


def send_slack_notification(text):
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url:
        print(
            "Slack notification skipped: SLACK_WEBHOOK_URL is not configured.",
            flush=True,
        )
        return False

    try:
        response = requests.post(
            webhook_url,
            json={"text": text},
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        print(
            f"Slack notification failed: {exc.__class__.__name__}",
            flush=True,
        )
        return False

    return True


def record_user_details(
    email,
    name="Name not provided",
    notes="not provided",
    question=None,
):
    message = (
        ":incoming_envelope: *New portfolio lead*\n\n"
        f"*Name:* {escape_slack_text(name)}\n"
        f"*Email:* {escape_slack_text(email)}\n"
        f"*Notes:* {escape_slack_text(notes)}"
    )
    if question:
        message += (
            "\n*Follow-up to unanswered question:* "
            f"{escape_slack_text(question)}"
        )
    delivered = send_slack_notification(message)
    return {"recorded": "ok" if delivered else "notification_failed"}


def record_unknown_question(question):
    message = (
        ":question: *Unanswered portfolio question*\n\n"
        f"*Question:* {escape_slack_text(question)}"
    )
    delivered = send_slack_notification(message)
    return {"recorded": "ok" if delivered else "notification_failed"}


record_user_details_json = {
    "name": "record_user_details",
    "description": (
        "Record contact details after a visitor provides an email address. If "
        "the details were provided after an unanswered question, include that "
        "question so the follow-up Slack notification has the full context."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "email": {
                "type": "string",
                "description": "The email address of this user"
            },
            "name": {
                "type": "string",
                "description": "The user's name, if they provided it"
            }
            ,
            "notes": {
                "type": "string",
                "description": "Any additional information about the conversation that's worth recording to give context"
            },
            "question": {
                "type": "string",
                "description": "The unanswered question these contact details relate to, when applicable"
            }
        },
        "required": ["email"],
        "additionalProperties": False
    }
}

record_unknown_question_json = {
    "name": "record_unknown_question",
    "description": "Always use this tool to record any question that couldn't be answered as you didn't know the answer",
    "parameters": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The question that couldn't be answered"
            },
        },
        "required": ["question"],
        "additionalProperties": False
    }
}

tools = [
    {"type": "function", "function": record_user_details_json},
    {"type": "function", "function": record_unknown_question_json},
]


class Me:
    def __init__(self, config_path="config.json", llm_client=None):
        config_path = Path(config_path)
        with config_path.open("r", encoding="utf-8") as f:
            config = json.load(f)
        self.name = config["name"]
        self.llm_config = LLMConfig.from_app_config(config)
        self.llm = llm_client or LiteLLMClient(self.llm_config)
        data_dir = config_path.parent / "data"
        try:
            with (data_dir / "linkedin_clean.json").open("r", encoding="utf-8") as f:
                self.linkedin = json.dumps(json.load(f), indent=2)
        except FileNotFoundError:
            with (data_dir / "linkedin.json").open("r", encoding="utf-8") as f:
                self.linkedin = json.dumps(json.load(f), indent=2)


    def handle_tool_call(self, tool_calls):
        results = []
        for tool_call in tool_calls:
            function = tool_call["function"]
            tool_name = function["name"]
            raw_arguments = function.get("arguments", "{}")
            arguments = (
                json.loads(raw_arguments)
                if isinstance(raw_arguments, str)
                else raw_arguments
            )
            print(f"Tool called: {tool_name}", flush=True)
            tool_registry = {
                "record_user_details": record_user_details,
                "record_unknown_question": record_unknown_question,
            }
            tool = tool_registry.get(tool_name)
            result = tool(**arguments) if tool else {"error": "Unknown tool"}
            results.append(
                {
                    "role": "tool",
                    "content": json.dumps(result),
                    "tool_call_id": tool_call["id"],
                }
            )
        return results

    def system_prompt(self):
        current_date = date.today().isoformat()
        system_prompt = f"Today is {current_date}. You are acting as {self.name}. You are answering questions on {self.name}'s website, \
            particularly questions related to {self.name}'s career, background, skills and experience. \
            Your responsibility is to represent {self.name} for interactions on the website as faithfully as possible. \
            You are given {self.name}'s LinkedIn profile which you can use to answer questions. \
            Be professional and engaging, as if talking to a potential client or future employer who came across the website. \
            Interpret all profile dates relative to today's date. Only describe a role, course, or activity as current when its dates explicitly indicate it is ongoing. If it has an end date before today, describe it in the past tense. Do not infer that something is current from the headline or summary when dated entries contradict it. \
            If you don't know the answer to any question, immediately use record_unknown_question to send the question, without waiting for contact details. After recording it, tell the visitor you don't have that information and ask for their name and email so {self.name} can follow up. If they decline or provide no details, do not ask repeatedly; the question has already been recorded. If they later provide an email, use record_user_details and include the unanswered question in the question field so a second Slack update links their contact information to it. \
            For other engaged visitors, you may invite them to get in touch by email; only call record_user_details after they actually provide an email address. "

        system_prompt += f"\n\n## LinkedIn Profile:\n{self.linkedin}\n\n"
        system_prompt += (
            "With this context, please chat with the user, always staying in "
            f"character as {self.name}."
        )
        return system_prompt

    def chat(self, message, history):
        messages = (
            [{"role": "system", "content": self.system_prompt()}]
            + history
            + [{"role": "user", "content": message}]
        )
        for _ in range(8):
            try:
                assistant_message = self.llm.complete(messages=messages, tools=tools)
            except LLMServiceError as exc:
                return f"I’m temporarily unable to respond. {exc}"

            tool_calls = assistant_message.get("tool_calls") or []
            if tool_calls:
                results = self.handle_tool_call(tool_calls)
                messages.append(assistant_message)
                messages.extend(results)
            else:
                return assistant_message.get("content") or ""

        return (
            "I’m temporarily unable to respond because too many tool calls "
            "were requested."
        )

if __name__ == "__main__":
    me = Me()
    gr.ChatInterface(me.chat, type="messages").launch()
