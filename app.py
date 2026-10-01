from dotenv import load_dotenv
import json
import os
from pathlib import Path
import requests
import gradio as gr

from src.llm import LLMConfig, LLMServiceError, LiteLLMClient


load_dotenv(override=True)


def push(text):
    requests.post(
        "https://api.pushover.net/1/messages.json",
        data={
            "token": os.getenv("PUSHOVER_TOKEN"),
            "user": os.getenv("PUSHOVER_USER"),
            "message": text,
        },
        timeout=10,
    )


def record_user_details(email, name="Name not provided", notes="not provided"):
    push(f"Recording {name} with email {email} and notes {notes}")
    return {"recorded": "ok"}


def record_unknown_question(question):
    push(f"Recording {question}")
    return {"recorded": "ok"}

record_user_details_json = {
    "name": "record_user_details",
    "description": "Use this tool to record that a user is interested in being in touch and provided an email address",
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
        system_prompt = f"You are acting as {self.name}. You are answering questions on {self.name}'s website, \
            particularly questions related to {self.name}'s career, background, skills and experience. \
            Your responsibility is to represent {self.name} for interactions on the website as faithfully as possible. \
            You are given {self.name}'s LinkedIn profile which you can use to answer questions. \
            Be professional and engaging, as if talking to a potential client or future employer who came across the website. \
            If you don't know the answer to any question, use your record_unknown_question tool to record the question that you couldn't answer, even if it's about something trivial or unrelated to career. \
            If the user is engaging in discussion, try to steer them towards getting in touch via email; ask for their email and record it using your record_user_details tool. "

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
