"""
UAP Chat Example - Local Model Provider

A UAP Provider that loads a GGUF model locally via llama-cpp-python.
No server needed — runs inference directly in-process.

Requires: pip install llama-cpp-python

Configuration (local.yaml):
    provider: local
    model_path: ~/models/llama-3.2-3b-instruct.Q4_K_M.gguf
    n_ctx: 4096
    n_gpu_layers: -1
    temperature: 0.7
    system_prompt: "You are a helpful assistant."
    max_history_turns: 20
"""

from pathlib import Path


class LocalChatProvider:
    """
    UAP Provider backed by a local GGUF model via llama-cpp-python.

    Receives UAP messages (env.declare, env.observe, env.close)
    and runs inference locally.
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
        self.conversation_history = [
            {"role": "system", "content": self.config.system_prompt},
        ]

        model_name = Path(self.config.model_path).stem
        return {
            "uap": "0.2",
            "id": message["id"],
            "status": "ok",
            "result": {
                "env_id": self.env_declaration["env_id"],
                "understood": True,
                "summary": f"I'm {self.name} (local: {model_name}). Ready to chat.",
                "ready": True,
                "initial_input_request": ["message"],
            },
        }

    def _handle_observe(self, message: dict) -> dict:
        inputs = message["params"]["inputs"]
        user_msg = inputs.get("message", {})
        text = user_msg.get("text", "")

        self.conversation_history.append({"role": "user", "content": text})
        self._trim_history()

        try:
            response = self.llm.create_chat_completion(
                messages=self.conversation_history,
                temperature=self.config.temperature,
            )

            reply_text = response["choices"][0]["message"]["content"]
            self.conversation_history.append({"role": "assistant", "content": reply_text})

            usage = response.get("usage", {})

            return {
                "uap": "0.2",
                "id": message["id"],
                "status": "ok",
                "result": {
                    "env_id": message["params"]["env_id"],
                    "actions": [
                        {"id": "reply", "params": {"text": reply_text}},
                    ],
                    "status": "continue",
                    "next_input_request": ["message"],
                },
                "usage": {
                    "input_tokens": usage.get("prompt_tokens", 0),
                    "output_tokens": usage.get("completion_tokens", 0),
                },
            }

        except Exception as e:
            return self._error(message, "provider_error", str(e))

    def _handle_close(self, message: dict) -> dict:
        turns = (len(self.conversation_history) - 1) // 2
        self.conversation_history = []
        return {
            "uap": "0.2",
            "id": message["id"],
            "status": "ok",
            "result": {
                "env_id": message["params"]["env_id"],
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
            "uap": "0.2",
            "id": message.get("id"),
            "status": "error",
            "error": {"code": code, "message": msg},
        }
