"""
UAP Chat Example - OpenAI Provider

A real UAP Provider that uses OpenAI API (or any compatible API) for chat.
Translates UAP messages (session.init, input, session.close) into OpenAI
chat completions.

Configuration (provider.yaml):
    provider: openai
    api_key: sk-...
    base_url: https://api.openai.com/v1
    model: gpt-4o
    temperature: 0.7
    system_prompt: "You are a helpful assistant."
    max_history_turns: 50
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path

import yaml_compat as yc


DEFAULT_SYSTEM_PROMPT = "You are a helpful, friendly AI assistant."

DEFAULT_CONFIG = {
    "provider": "mock",
    "api_key": None,
    "base_url": None,
    "model": "gpt-4o",
    "temperature": 0.7,
    "max_history_turns": 50,
    "system_prompt": DEFAULT_SYSTEM_PROMPT,
    "model_path": None,
    "n_ctx": 4096,
    "n_gpu_layers": -1,
}


@dataclass
class ProviderConfig:
    provider: str = "mock"
    api_key: str | None = None
    base_url: str | None = None
    model: str = "gpt-4o"
    temperature: float = 0.7
    max_history_turns: int = 50
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    model_path: str | None = None
    n_ctx: int = 4096
    n_gpu_layers: int = -1

    @classmethod
    def load(cls, path: str | Path | None = None, overrides: dict | None = None) -> "ProviderConfig":
        """Load config from YAML file, env vars, and overrides (in priority order)."""
        data = dict(DEFAULT_CONFIG)

        if path:
            p = Path(path)
            if p.exists():
                data.update(yc.load(p))

        env_map = {
            "OPENAI_API_KEY": "api_key",
            "OPENAI_BASE_URL": "base_url",
            "OPENAI_MODEL": "model",
            "OPENAI_TEMPERATURE": "temperature",
        }
        for env_key, config_key in env_map.items():
            val = os.environ.get(env_key)
            if val is not None:
                if config_key == "temperature":
                    val = float(val)
                data[config_key] = val

        if overrides:
            data.update({k: v for k, v in overrides.items() if v is not None})

        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class OpenAIChatProvider:
    """
    UAP Provider backed by OpenAI-compatible API for chat.

    Receives UAP messages (session.init, input, session.close)
    and translates them into OpenAI chat completion calls.
    """

    def __init__(self, name: str = "AI", config: ProviderConfig | None = None):
        self.name = name
        self.config = config or ProviderConfig.load()
        self.system_declaration = None
        self.conversation_history: list[dict] = []

        from openai import OpenAI
        self.client = OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
        )

    def handle_message(self, message: dict) -> dict:
        method = message.get("method")
        if method == "session.init":
            return self._handle_init(message)
        elif method == "input":
            return self._handle_input(message)
        elif method == "session.close":
            return self._handle_close(message)
        else:
            return self._error(message, "not_found", f"Unknown method: {method}")

    def _handle_init(self, message: dict) -> dict:
        self.system_declaration = message["params"].get("system", {})
        self.conversation_history = [
            {"role": "system", "content": self.config.system_prompt},
        ]

        return {
            "uap": "0.3",
            "id": message["id"],
            "status": "ok",
            "result": {
                "system_accepted": True,
                "summary": f"I'm {self.name} (model: {self.config.model}). Ready to chat.",
                "ready": True,
                "initial_input_request": ["message"],
            },
        }

    def _handle_input(self, message: dict) -> dict:
        data = message["params"]["data"]
        user_msg = data.get("message", {})
        text = user_msg.get("text", "")

        self.conversation_history.append({"role": "user", "content": text})
        self._trim_history()

        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=self.conversation_history,
                temperature=self.config.temperature,
            )

            reply_text = response.choices[0].message.content
            self.conversation_history.append({"role": "assistant", "content": reply_text})

            usage = {}
            if response.usage:
                usage = {
                    "input_tokens": response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens,
                }

            return {
                "uap": "0.3",
                "id": message["id"],
                "status": "ok",
                "result": {
                    "actions": [
                        {"id": "reply", "params": {"text": reply_text}},
                    ],
                    "status": "continue",
                    "next_input_request": ["message"],
                },
                "usage": usage,
            }

        except Exception as e:
            return self._error(message, "provider_error", str(e))

    def _handle_close(self, message: dict) -> dict:
        turns = (len(self.conversation_history) - 1) // 2  # exclude system prompt
        self.conversation_history = []
        return {
            "uap": "0.3",
            "id": message["id"],
            "status": "ok",
            "result": {
                "summary": f"[{self.name}] Chat ended. {turns} turns.",
                "stats": {"turns": turns},
            },
        }

    def _trim_history(self):
        max_turns = self.config.max_history_turns
        max_messages = 1 + max_turns * 2
        if len(self.conversation_history) > max_messages:
            self.conversation_history = (
                self.conversation_history[:1] + self.conversation_history[-(max_turns * 2):]
            )

    def _error(self, message: dict, code: str, msg: str) -> dict:
        return {
            "uap": "0.3",
            "id": message.get("id"),
            "status": "error",
            "error": {"code": code, "message": msg},
        }
