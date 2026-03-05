"""
UAP Gomoku Example - Local Model Provider

A UAP Provider that loads a GGUF model locally via llama-cpp-python.
No server needed — runs inference directly in-process.

Requires: pip install llama-cpp-python

Configuration (local.yaml):
    provider: local
    model_path: ~/models/qwen2.5-7b-instruct.Q4_K_M.gguf
    n_ctx: 4096
    n_gpu_layers: -1
    temperature: 0.3
"""

import json
from pathlib import Path


class LocalGomokuProvider:
    """
    UAP Provider backed by a local GGUF model via llama-cpp-python.

    Receives UAP messages (env.declare, env.observe, env.close)
    and runs inference locally. Translates responses to gomoku actions.
    """

    def __init__(self, name: str = "Local", config=None):
        self.name = name
        self.config = config
        self.env_declaration = None
        self.conversation_history: list[dict] = []

        from llama_cpp import Llama

        model_path = str(Path(config.model_path).expanduser())
        self.llm = Llama(
            model_path=model_path,
            n_ctx=config.n_ctx,
            n_gpu_layers=config.n_gpu_layers,
            verbose=False,
        )

    def handle_message(self, message: dict) -> dict:
        method = message.get("method")
        if method == "env.declare":
            return self._handle_declare(message)
        elif method == "env.observe":
            return self._handle_observe(message)
        elif method == "env.close":
            return self._handle_close(message)
        else:
            return self._error(message, "not_found", f"Unknown method: {method}")

    def _handle_declare(self, message: dict) -> dict:
        self.env_declaration = message["params"]
        self.conversation_history = []

        system_prompt = self._build_system_prompt()
        self.conversation_history.append({"role": "system", "content": system_prompt})

        model_name = Path(self.config.model_path).stem
        return {
            "uap": "0.2",
            "id": message["id"],
            "status": "ok",
            "result": {
                "env_id": self.env_declaration["env_id"],
                "understood": True,
                "summary": f"I'm {self.name} (local: {model_name}). Ready to play.",
                "ready": True,
                "initial_input_request": ["board_state"],
            },
        }

    def _handle_observe(self, message: dict) -> dict:
        board_state = message["params"]["inputs"]["board_state"]
        user_message = message["params"].get("message", "")

        content = self._format_board_message(board_state, user_message)
        self.conversation_history.append({"role": "user", "content": content})
        self._trim_history()

        try:
            response = self.llm.create_chat_completion(
                messages=self.conversation_history,
                temperature=self.config.temperature,
                response_format={"type": "json_object"} if self.config.response_format == "json" else None,
            )

            assistant_text = response["choices"][0]["message"]["content"]
            self.conversation_history.append({"role": "assistant", "content": assistant_text})

            actions, thinking = self._parse_response(assistant_text)
            usage = response.get("usage", {})

            return {
                "uap": "0.2",
                "id": message["id"],
                "status": "ok",
                "result": {
                    "env_id": message["params"]["env_id"],
                    "thinking": thinking,
                    "actions": actions,
                    "status": "continue",
                    "next_input_request": ["board_state"],
                },
                "usage": {
                    "input_tokens": usage.get("prompt_tokens", 0),
                    "output_tokens": usage.get("completion_tokens", 0),
                },
            }

        except Exception as e:
            return self._error(message, "provider_error", str(e))

    def _handle_close(self, message: dict) -> dict:
        self.conversation_history = []
        return {
            "uap": "0.2",
            "id": message["id"],
            "status": "ok",
            "result": {
                "env_id": message["params"]["env_id"],
                "summary": f"[{self.name}] Good game!",
                "stats": {},
            },
        }

    # --- Prompt Engineering ---

    def _build_system_prompt(self) -> str:
        decl = self.env_declaration
        description = decl.get("description", "")
        example = decl.get("example", {})

        parts = [
            f"You are playing a gomoku game.\n\n{description}",
            "IMPORTANT: Respond in JSON:\n"
            '{"thinking": "your analysis", "action": "place_stone", "x": <0-14>, "y": <0-14>}\n'
            'Or to resign: {"thinking": "reason", "action": "resign"}',
        ]

        if example:
            parts.append(
                f"Example:\n- Input: {json.dumps(example.get('inputs', {}), ensure_ascii=False)}\n"
                f"- Response: {json.dumps(example.get('actions', []), ensure_ascii=False)}"
            )

        if self.config.strategy_prompt:
            parts.append(self.config.strategy_prompt)

        return "\n\n".join(parts)

    def _format_board_message(self, board_state: dict, extra_message: str = "") -> str:
        board = board_state["board"]
        current_turn = board_state["current_turn"]
        history = board_state.get("move_history", [])

        lines = ["Current board (0=empty, 1=black/X, 2=white/O):"]
        lines.append("   " + " ".join(f"{i:2d}" for i in range(len(board[0]))))
        for y, row in enumerate(board):
            symbols = [" ." if c == 0 else " X" if c == 1 else " O" for c in row]
            lines.append(f"{y:2d} {''.join(symbols)}")

        lines.append(f"\nYour color: {current_turn}")
        lines.append(f"Move count: {len(history)}")

        if history:
            last = history[-1]
            lines.append(f"Last move: {last['color']} at ({last['x']}, {last['y']})")

        if extra_message:
            lines.append(f"\n{extra_message}")

        lines.append("\nRespond with your move in JSON.")
        return "\n".join(lines)

    def _trim_history(self):
        max_turns = self.config.max_history_turns
        max_messages = 1 + max_turns * 2
        if len(self.conversation_history) > max_messages:
            self.conversation_history = (
                self.conversation_history[:1] + self.conversation_history[-(max_turns * 2):]
            )

    def _parse_response(self, text: str) -> tuple[list[dict], str]:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(text[start:end])
            else:
                return [], f"Failed to parse: {text[:100]}"

        thinking = data.get("thinking", "")
        action = data.get("action", "place_stone")

        if action == "resign":
            return [{"id": "resign", "params": {}}], thinking

        x = data.get("x")
        y = data.get("y")
        if x is not None and y is not None:
            return [{"id": "place_stone", "params": {"x": int(x), "y": int(y)}}], thinking

        return [], f"Invalid response: {text[:100]}"

    def _error(self, message: dict, code: str, msg: str) -> dict:
        return {
            "uap": "0.2",
            "id": message.get("id"),
            "status": "error",
            "error": {"code": code, "message": msg},
        }
