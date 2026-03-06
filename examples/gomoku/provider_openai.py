"""
UAP Gomoku Example - OpenAI Provider

A real UAP Provider that uses OpenAI API (or any compatible API)
to play gomoku. Translates UAP session.init/input messages into
OpenAI chat completions.

Supports any OpenAI-compatible endpoint (OpenAI, DeepSeek, local models, etc.)
via config or environment variables.

Configuration (provider.yaml):
    api_key: sk-...
    base_url: https://api.openai.com/v1
    model: gpt-4o
    temperature: 0.3
    system_prompt_extra: "You are an aggressive player..."
    max_history_turns: 20
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml_compat as yc
from openai import OpenAI


DEFAULT_STRATEGY_PROMPT = """\
Think carefully about strategy:
1. Check if you can win immediately (4 in a row with open end)
2. Check if opponent has a threat you must block
3. Try to build multiple threats simultaneously
4. Prefer center and positions near existing stones\
"""

DEFAULT_CONFIG = {
    "provider": "mock",
    "style": "balanced",
    "api_key": None,
    "base_url": None,
    "model": "gpt-4o",
    "temperature": 0.3,
    "max_history_turns": 20,
    "system_prompt_prefix": "",
    "system_prompt_suffix": "",
    "strategy_prompt": DEFAULT_STRATEGY_PROMPT,
    "response_format": "json",
    "model_path": None,
    "n_ctx": 4096,
    "n_gpu_layers": -1,
}


@dataclass
class ProviderConfig:
    provider: str = "mock"
    style: str = "balanced"
    api_key: str | None = None
    base_url: str | None = None
    model: str = "gpt-4o"
    temperature: float = 0.3
    max_history_turns: int = 20
    system_prompt_prefix: str = ""
    system_prompt_suffix: str = ""
    strategy_prompt: str = DEFAULT_STRATEGY_PROMPT
    response_format: str = "json"
    model_path: str | None = None
    n_ctx: int = 4096
    n_gpu_layers: int = -1

    @classmethod
    def load(cls, path: str | Path | None = None, overrides: dict | None = None) -> "ProviderConfig":
        """Load config from YAML file, env vars, and overrides (in priority order)."""
        data = dict(DEFAULT_CONFIG)

        # 1. Load from YAML file
        if path:
            p = Path(path)
            if p.exists():
                data.update(yc.load(p))

        # 2. Override from environment variables
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

        # 3. Override from explicit arguments
        if overrides:
            data.update({k: v for k, v in overrides.items() if v is not None})

        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class OpenAIProvider:
    """
    UAP Provider backed by OpenAI-compatible API.

    Receives UAP messages (session.init, input, session.close)
    and translates them into OpenAI chat completion calls.
    """

    def __init__(self, name: str = "AI", config: ProviderConfig | None = None, **kwargs):
        self.name = name
        self.config = config or ProviderConfig.load(overrides=kwargs)
        self.system_declaration = None
        self.conversation_history: list[dict] = []

        self.client = OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
        )

    def handle_message(self, message: dict) -> dict:
        method = message.get("method")
        if method == "session.init":
            return self._handle_session_init(message)
        elif method == "input":
            return self._handle_input(message)
        elif method == "session.close":
            return self._handle_close(message)
        else:
            return self._error(message, "not_found", f"Unknown method: {method}")

    def _handle_session_init(self, message: dict) -> dict:
        self.system_declaration = message["params"]["system"]
        self.conversation_history = []

        system_prompt = self._build_system_prompt()
        self.conversation_history.append({"role": "system", "content": system_prompt})

        return {
            "uap": "0.3",
            "id": message["id"],
            "status": "ok",
            "result": {
                "system_accepted": {
                    "understood": True,
                    "summary": f"I'm {self.name} (model: {self.config.model}). Ready to play.",
                    "ready": True,
                },
                "initial_input_request": ["board_state"],
            },
        }

    def _handle_input(self, message: dict) -> dict:
        board_state = message["params"]["data"]["board_state"]
        user_message = message["params"].get("message", "")

        content = self._format_board_message(board_state, user_message)
        self.conversation_history.append({"role": "user", "content": content})

        # Trim history to limit context size
        self._trim_history()

        try:
            create_kwargs = {
                "model": self.config.model,
                "messages": self.conversation_history,
                "temperature": self.config.temperature,
            }
            if self.config.response_format == "json":
                create_kwargs["response_format"] = {"type": "json_object"}

            response = self.client.chat.completions.create(**create_kwargs)

            assistant_text = response.choices[0].message.content
            self.conversation_history.append({"role": "assistant", "content": assistant_text})

            actions, thinking = self._parse_response(assistant_text)

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
                    "thinking": thinking,
                    "actions": actions,
                    "status": "continue",
                    "next_input_request": ["board_state"],
                },
                "usage": usage,
            }

        except Exception as e:
            return self._error(message, "provider_error", str(e))

    def _handle_close(self, message: dict) -> dict:
        self.conversation_history = []
        return {
            "uap": "0.3",
            "id": message["id"],
            "status": "ok",
            "result": {
                "summary": f"[{self.name}] Good game!",
                "stats": {},
            },
        }

    # --- Prompt Engineering ---

    def _build_system_prompt(self) -> str:
        decl = self.system_declaration
        description = decl.get("description", "")
        example = decl.get("example", {})

        parts = []

        # User-defined prefix
        if self.config.system_prompt_prefix:
            parts.append(self.config.system_prompt_prefix)

        # System description
        parts.append(f"You are playing a gomoku game. Here are the rules and environment:\n\n{description}")

        # Available actions
        action_lines = ["Available actions:"]
        for action in decl.get("actions", []):
            action_lines.append(f"- {action['id']}: {action.get('description', '')}")
        parts.append("\n".join(action_lines))

        # Example
        if example:
            parts.append(
                f"Example interaction:\n"
                f"- Input: {json.dumps(example.get('inputs', {}), ensure_ascii=False)}\n"
                f"- Your response: {json.dumps(example.get('actions', []), ensure_ascii=False)}"
            )

        # Response format
        parts.append(
            "IMPORTANT: You must respond in JSON format with exactly this structure:\n"
            "{\n"
            '  "thinking": "your analysis of the board position",\n'
            '  "action": "place_stone",\n'
            '  "x": <column 0-14>,\n'
            '  "y": <row 0-14>\n'
            "}\n\n"
            "Or to resign:\n"
            "{\n"
            '  "thinking": "reason for resigning",\n'
            '  "action": "resign"\n'
            "}"
        )

        # Strategy prompt (configurable)
        if self.config.strategy_prompt:
            parts.append(self.config.strategy_prompt)

        # User-defined suffix
        if self.config.system_prompt_suffix:
            parts.append(self.config.system_prompt_suffix)

        return "\n\n".join(parts)

    def _format_board_message(self, board_state: dict, extra_message: str = "") -> str:
        board = board_state["board"]
        current_turn = board_state["current_turn"]
        history = board_state.get("move_history", [])

        lines = ["Current board (0=empty, 1=black/X, 2=white/O):"]
        lines.append("   " + " ".join(f"{i:2d}" for i in range(len(board[0]))))
        for y, row in enumerate(board):
            symbols = []
            for cell in row:
                symbols.append({0: " .", 1: " X", 2: " O"}[cell])
            lines.append(f"{y:2d} {''.join(symbols)}")

        lines.append(f"\nYour color: {current_turn}")
        lines.append(f"Move count: {len(history)}")

        if history:
            last = history[-1]
            lines.append(f"Last move: {last['color']} at ({last['x']}, {last['y']})")

        if extra_message:
            lines.append(f"\n{extra_message}")

        lines.append("\nRespond with your move in JSON format.")
        return "\n".join(lines)

    def _trim_history(self):
        """Keep conversation history within max_history_turns to control token usage."""
        max_turns = self.config.max_history_turns
        # Each turn = 1 user + 1 assistant = 2 messages. Keep system prompt (index 0).
        max_messages = 1 + max_turns * 2
        if len(self.conversation_history) > max_messages:
            # Keep system prompt + last N turns
            self.conversation_history = (
                self.conversation_history[:1] + self.conversation_history[-(max_turns * 2):]
            )

    def _parse_response(self, text: str) -> tuple[list[dict], str]:
        """Parse AI response into UAP actions."""
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(text[start:end])
            else:
                return [], f"Failed to parse response: {text[:100]}"

        thinking = data.get("thinking", "")
        action = data.get("action", "place_stone")

        if action == "resign":
            return [{"id": "resign", "params": {}}], thinking

        x = data.get("x")
        y = data.get("y")
        if x is not None and y is not None:
            return [{"id": "place_stone", "params": {"x": int(x), "y": int(y)}}], thinking

        return [], f"Invalid response format: {text[:100]}"

    def _error(self, message: dict, code: str, msg: str) -> dict:
        return {
            "uap": "0.3",
            "id": message.get("id"),
            "status": "error",
            "error": {"code": code, "message": msg},
        }
