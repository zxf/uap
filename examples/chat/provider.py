"""
UAP Chat Example - Mock Provider

A mock UAP Provider that echoes back messages with simple canned responses.
Demonstrates the Provider side of the UAP protocol for chat scenarios.
"""

import random


RESPONSES = [
    "That's an interesting point. Tell me more.",
    "I see what you mean. Have you considered another perspective?",
    "Great question! Let me think about that...",
    "That reminds me of something I read recently.",
    "Could you elaborate on that?",
    "I agree with your reasoning.",
    "Hmm, that's a complex topic. Let's break it down.",
    "Interesting! What made you think of that?",
]


class MockChatProvider:
    """
    Mock UAP Provider for chat.

    Implements the Provider side of the UAP protocol:
    - env.declare -> understand environment, return confirmation
    - env.observe -> receive user message, return reply (env.act)
    - env.close   -> return summary
    """

    def __init__(self, name: str = "MockChat"):
        self.name = name
        self.env_declaration = None
        self.message_count = 0

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
        self.message_count = 0
        return {
            "uap": "0.2",
            "id": message["id"],
            "status": "ok",
            "result": {
                "env_id": self.env_declaration["env_id"],
                "understood": True,
                "summary": f"I'm {self.name}, a mock chat provider. Ready to chat!",
                "ready": True,
                "initial_input_request": ["message"],
            },
        }

    def _handle_observe(self, message: dict) -> dict:
        inputs = message["params"]["inputs"]
        user_msg = inputs.get("message", {})
        text = user_msg.get("text", "")
        self.message_count += 1

        # Generate a mock reply
        if "hello" in text.lower() or "hi" in text.lower():
            reply = f"Hello! I'm {self.name}. How can I help you today?"
        elif "bye" in text.lower():
            reply = "Goodbye! It was nice chatting with you."
        elif "?" in text:
            reply = f"That's a great question about '{text[:50]}'. " + random.choice(RESPONSES)
        else:
            reply = random.choice(RESPONSES)

        return {
            "uap": "0.2",
            "id": message["id"],
            "status": "ok",
            "result": {
                "env_id": message["params"]["env_id"],
                "thinking": f"Processing message #{self.message_count}",
                "actions": [
                    {"id": "reply", "params": {"text": reply}},
                ],
                "status": "continue",
                "next_input_request": ["message"],
            },
            "usage": {"input_tokens": len(text) * 2, "output_tokens": len(reply) * 2},
        }

    def _handle_close(self, message: dict) -> dict:
        return {
            "uap": "0.2",
            "id": message["id"],
            "status": "ok",
            "result": {
                "env_id": message["params"]["env_id"],
                "summary": f"[{self.name}] Chat ended. {self.message_count} messages exchanged.",
                "stats": {"messages": self.message_count},
            },
        }

    def _error(self, message: dict, code: str, msg: str) -> dict:
        return {
            "uap": "0.2",
            "id": message.get("id"),
            "status": "error",
            "error": {"code": code, "message": msg},
        }
