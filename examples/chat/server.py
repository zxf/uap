"""
UAP Chat Example - Terminal Client (Consumer)

A simple chat client demonstrating the UAP protocol for conversational AI.
Chat is just another environment: env.declare describes a conversation,
env.observe sends user messages, env.act returns AI replies.

Usage:
    uv run server.py                       # Chat with Mock AI
    uv run server.py --config openai.yaml  # Chat with OpenAI

Commands during chat:
    /clear  - Clear conversation and restart
    /quit   - Exit
"""

import argparse
import json
from pathlib import Path

from provider import MockChatProvider
from provider_openai import OpenAIChatProvider, ProviderConfig


# --- UAP Message Builders ---

def build_env_declare(env_id: str) -> dict:
    """Build the env.declare message for a chat environment."""
    return {
        "uap": "0.2",
        "id": "req_declare",
        "method": "env.declare",
        "params": {
            "env_id": env_id,
            "name": "Chat",
            "description": (
                "A conversational chat environment. "
                "You receive user messages and respond with helpful, clear replies. "
                "You can use markdown formatting in your responses."
            ),
            "example": {
                "inputs": {
                    "message": {"role": "user", "text": "What is the capital of France?"},
                },
                "actions": [
                    {"id": "reply", "params": {"text": "The capital of France is **Paris**."}},
                ],
            },
            "inputs": [
                {
                    "id": "message",
                    "type": "structured",
                    "description": "User message with role and text fields",
                },
            ],
            "actions": [
                {
                    "id": "reply",
                    "description": "Send a text reply to the user",
                    "params_schema": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string", "description": "Reply text"},
                        },
                        "required": ["text"],
                    },
                },
            ],
        },
    }


def build_env_observe(env_id: str, text: str, msg_id: int) -> dict:
    return {
        "uap": "0.2",
        "id": f"req_{msg_id:03d}",
        "method": "env.observe",
        "params": {
            "env_id": env_id,
            "inputs": {
                "message": {"role": "user", "text": text},
            },
        },
    }


def build_env_close(env_id: str, reason: str) -> dict:
    return {
        "uap": "0.2",
        "id": "req_close",
        "method": "env.close",
        "params": {"env_id": env_id, "reason": reason},
    }


# --- Provider Factory ---

def make_provider(name: str = "AI", config_file: str | None = None):
    config = ProviderConfig.load(path=config_file)
    if config.provider == "openai":
        return OpenAIChatProvider(name=name, config=config)
    elif config.provider == "local":
        from provider_local import LocalChatProvider
        return LocalChatProvider(name=name, config=config)
    return MockChatProvider(name=name)


# --- Chat Loop ---

def chat(config_file: str | None = None):
    env_id = "chat_01"
    provider = make_provider(name="AI", config_file=config_file)

    # env.declare
    declare_msg = build_env_declare(env_id)
    print("[UAP] -> env.declare")
    response = provider.handle_message(declare_msg)
    print(f"[UAP] <- {response['result']['summary']}\n")

    print("=" * 50)
    print("  UAP Chat  (/clear to reset, /quit to exit)")
    print("=" * 50)
    print()

    msg_id = 0

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue

        if user_input == "/quit":
            break

        if user_input == "/clear":
            # Close and re-declare
            close_msg = build_env_close(env_id, "user_clear")
            provider.handle_message(close_msg)
            response = provider.handle_message(declare_msg)
            msg_id = 0
            print("\n[Conversation cleared]\n")
            continue

        # env.observe -> env.act
        msg_id += 1
        observe_msg = build_env_observe(env_id, user_input, msg_id)
        response = provider.handle_message(observe_msg)

        if response["status"] == "error":
            print(f"\n[Error] {response['error']['message']}\n")
            continue

        result = response["result"]

        # Print usage if available
        usage = response.get("usage", {})
        usage_str = ""
        if usage:
            tokens_in = usage.get("input_tokens", 0)
            tokens_out = usage.get("output_tokens", 0)
            usage_str = f"  [{tokens_in}+{tokens_out} tokens]"

        # Execute actions
        for action in result.get("actions", []):
            if action["id"] == "reply":
                reply_text = action["params"]["text"]
                print(f"\nAI: {reply_text}{usage_str}\n")

    # env.close
    close_msg = build_env_close(env_id, "user_quit")
    response = provider.handle_message(close_msg)
    print(f"\n{response['result']['summary']}")


# --- Entry Point ---

def main():
    parser = argparse.ArgumentParser(description="UAP Chat Example")
    parser.add_argument("--config", type=str, default=None,
                        help="Provider config file (e.g., openai.yaml)")
    parser.add_argument("message", nargs="*",
                        help="Send a single message and exit (non-interactive)")
    args = parser.parse_args()

    # Non-interactive: single message mode
    if args.message:
        text = " ".join(args.message)
        provider = make_provider(config_file=args.config)
        env_id = "chat_single"

        provider.handle_message(build_env_declare(env_id))
        response = provider.handle_message(build_env_observe(env_id, text, 1))

        for action in response.get("result", {}).get("actions", []):
            if action["id"] == "reply":
                print(action["params"]["text"])

        provider.handle_message(build_env_close(env_id, "done"))
        return

    # Interactive mode
    chat(config_file=args.config)


if __name__ == "__main__":
    main()
