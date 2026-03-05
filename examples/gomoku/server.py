"""
UAP Gomoku Example - Game Server (Consumer)

A gomoku (five-in-a-row) game server that uses UAP protocol.
Supports human vs AI, and AI vs AI modes.
Provider type and settings are configured via YAML/JSON config files.

Usage:
    uv run server.py                                    # Human vs Mock AI (default)
    uv run server.py --config openai.yaml               # Human vs OpenAI
    uv run server.py --ai-vs-ai                         # Mock AI vs Mock AI
    uv run server.py --ai-vs-ai --config-black openai.yaml  # OpenAI vs Mock
"""

import argparse
import json
import time
from dataclasses import dataclass, field

from provider import MockAIProvider
from provider_openai import OpenAIProvider


BOARD_SIZE = 15
EMPTY, BLACK, WHITE = 0, 1, 2
SYMBOLS = {EMPTY: ".", BLACK: "X", WHITE: "O"}


# --- Game Logic ---

@dataclass
class GomokuGame:
    board: list[list[int]] = field(default_factory=lambda: [[EMPTY] * BOARD_SIZE for _ in range(BOARD_SIZE)])
    current_turn: str = "black"
    move_history: list[dict] = field(default_factory=list)
    game_status: str = "playing"

    def place_stone(self, x: int, y: int) -> dict:
        if self.game_status != "playing":
            return {"success": False, "error": "Game is over"}
        if not (0 <= x < BOARD_SIZE and 0 <= y < BOARD_SIZE):
            return {"success": False, "error": f"Coordinates ({x},{y}) out of range"}
        if self.board[y][x] != EMPTY:
            return {"success": False, "error": f"Position ({x},{y}) is occupied"}

        stone = BLACK if self.current_turn == "black" else WHITE
        self.board[y][x] = stone
        self.move_history.append({"x": x, "y": y, "color": self.current_turn})

        if self._check_win(x, y, stone):
            self.game_status = f"{self.current_turn}_wins"
        elif len(self.move_history) >= BOARD_SIZE * BOARD_SIZE:
            self.game_status = "draw"
        else:
            self.current_turn = "white" if self.current_turn == "black" else "black"

        return {"success": True}

    def _check_win(self, x: int, y: int, stone: int) -> bool:
        directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
        for dx, dy in directions:
            count = 1
            for sign in (1, -1):
                nx, ny = x + dx * sign, y + dy * sign
                while 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE and self.board[ny][nx] == stone:
                    count += 1
                    nx += dx * sign
                    ny += dy * sign
            if count >= 5:
                return True
        return False

    def to_state(self) -> dict:
        return {
            "board": [row[:] for row in self.board],
            "current_turn": self.current_turn,
            "move_history": list(self.move_history),
            "game_status": self.game_status,
        }

    def print_board(self):
        print("\n   " + " ".join(f"{i:2d}" for i in range(BOARD_SIZE)))
        for y in range(BOARD_SIZE):
            row = ""
            for x in range(BOARD_SIZE):
                s = SYMBOLS[self.board[y][x]]
                # Highlight last move
                if self.move_history and self.move_history[-1]["x"] == x and self.move_history[-1]["y"] == y:
                    s = f"\033[1;33m{s}\033[0m"  # yellow bold
                row += f"  {s}"
            print(f"{y:2d} {row}")
        print()


# --- UAP Message Builders ---

def build_env_declare(env_id: str, ai_color: str) -> dict:
    """Build the env.declare message for gomoku."""
    return {
        "uap": "0.2",
        "id": "req_declare",
        "method": "env.declare",
        "params": {
            "env_id": env_id,
            "name": "Gomoku",
            "description": (
                f"15x15 standard gomoku (five-in-a-row). You play as {ai_color.upper()} "
                f"({'1' if ai_color == 'black' else '2'}). "
                "The board is a 15x15 2D array: 0=empty, 1=black, 2=white. "
                "Coordinates start from top-left (0,0), x=column, y=row. "
                "First player to form 5 consecutive stones in a row/column/diagonal wins. "
                "You can only place stones on empty positions. Black and white alternate turns."
            ),
            "example": {
                "inputs": {
                    "board_state": {
                        "board": [
                            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                            [0, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0],
                            [0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0],
                            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                        ],
                        "current_turn": ai_color,
                        "move_history": [
                            {"x": 6, "y": 3, "color": "black"},
                            {"x": 7, "y": 2, "color": "white"},
                        ],
                        "game_status": "playing",
                    }
                },
                "actions": [{"id": "place_stone", "params": {"x": 7, "y": 3}}],
            },
            "inputs": [
                {"id": "board_state", "type": "structured", "description": "Current board state"},
            ],
            "actions": [
                {
                    "id": "place_stone",
                    "description": "Place a stone on an empty position",
                    "params_schema": {
                        "type": "object",
                        "properties": {
                            "x": {"type": "integer", "minimum": 0, "maximum": 14},
                            "y": {"type": "integer", "minimum": 0, "maximum": 14},
                        },
                        "required": ["x", "y"],
                    },
                },
                {"id": "resign", "description": "Resign the game"},
            ],
            "constraints": {"turn_timeout_ms": 30000, "max_turns": 225},
        },
    }


def build_env_observe(env_id: str, game: GomokuGame, message: str = "") -> dict:
    msg = {
        "uap": "0.2",
        "id": f"req_{len(game.move_history) + 10:03d}",
        "method": "env.observe",
        "params": {
            "env_id": env_id,
            "inputs": {"board_state": game.to_state()},
        },
    }
    if message:
        msg["params"]["message"] = message
    return msg


def build_env_close(env_id: str, reason: str) -> dict:
    return {
        "uap": "0.2",
        "id": "req_close",
        "method": "env.close",
        "params": {"env_id": env_id, "reason": reason, "summary_request": True},
    }


# --- Execute AI Actions ---

def execute_actions(game: GomokuGame, response: dict, label: str) -> bool:
    """Execute actions from an env.act response. Returns True if game should continue."""
    result = response["result"]
    thinking = result.get("thinking", "")
    if thinking:
        print(f"[{label}] Thinking: {thinking}")

    for action in result.get("actions", []):
        if action["id"] == "place_stone":
            x, y = action["params"]["x"], action["params"]["y"]
            place_result = game.place_stone(x, y)
            if place_result["success"]:
                print(f"[{label}] Places stone at ({x}, {y})")
            else:
                print(f"[{label}] Invalid move ({x},{y}): {place_result['error']}")
                return False
        elif action["id"] == "resign":
            print(f"[{label}] Resigns!")
            winner = "white" if game.current_turn == "black" else "black"
            game.game_status = f"{winner}_wins"

    return True


# --- Human Input ---

def human_move(game: GomokuGame) -> bool:
    """Get a move from human player. Returns False if user wants to quit."""
    color = game.current_turn.upper()
    symbol = "X" if game.current_turn == "black" else "O"

    while True:
        user_input = input(f"Your move ({color}/{symbol}), 'quit' to exit: ").strip()
        if user_input == "quit":
            return False
        try:
            parts = user_input.replace(",", " ").split()
            x, y = int(parts[0]), int(parts[1])
            result = game.place_stone(x, y)
            if result["success"]:
                print(f"[You] Places stone at ({x}, {y})")
                return True
            print(f"  Invalid: {result['error']}")
        except (ValueError, IndexError):
            print("  Format: x y (e.g., '7 7')")


# --- Game Modes ---

def make_provider(name: str = "AI", config_file: str | None = None):
    from provider_openai import ProviderConfig
    config = ProviderConfig.load(path=config_file)
    if config.provider == "openai":
        return OpenAIProvider(name=name, config=config)
    elif config.provider == "local":
        from provider_local import LocalGomokuProvider
        return LocalGomokuProvider(name=name, config=config)
    return MockAIProvider(name=name, style=config.style)


def play_human_vs_ai(ai_color: str = "black", config: str | None = None):
    """Human vs AI mode."""
    game = GomokuGame()
    env_id = "gomoku_hva"
    provider = make_provider(name="AI", config_file=config)

    human_color = "white" if ai_color == "black" else "black"
    human_symbol = "O" if human_color == "white" else "X"
    ai_symbol = "X" if ai_color == "black" else "O"

    print(f"=== Gomoku: Human ({human_color.upper()}/{human_symbol}) vs AI ({ai_color.upper()}/{ai_symbol}) ===")
    print("Enter moves as: x y (e.g., '7 7' for center)")
    print("Type 'quit' to exit\n")

    # env.declare
    declare_msg = build_env_declare(env_id, ai_color)
    print(f"[UAP] -> env.declare")
    response = provider.handle_message(declare_msg)
    print(f"[UAP] <- {response['result']['summary']}\n")

    # If AI goes first (black)
    if ai_color == "black":
        observe_msg = build_env_observe(env_id, game, "Game starts. Your turn.")
        print(f"[UAP] -> env.observe")
        response = provider.handle_message(observe_msg)
        print(f"[UAP] <- env.act")
        execute_actions(game, response, "AI")
        game.print_board()

    # Game loop
    while game.game_status == "playing":
        # Human turn
        if not human_move(game):
            close_msg = build_env_close(env_id, "user_quit")
            provider.handle_message(close_msg)
            print("Game ended by user.")
            return
        game.print_board()

        if game.game_status != "playing":
            break

        # AI turn
        observe_msg = build_env_observe(env_id, game)
        print(f"[UAP] -> env.observe")
        response = provider.handle_message(observe_msg)
        print(f"[UAP] <- env.act")
        execute_actions(game, response, "AI")
        game.print_board()

    # Game over
    print(f"\n=== Game Over: {game.game_status.replace('_', ' ').title()} ===")
    print(f"Total moves: {len(game.move_history)}")

    close_msg = build_env_close(env_id, game.game_status)
    response = provider.handle_message(close_msg)
    print(f"[UAP] <- {response['result']['summary']}")


def play_ai_vs_ai(delay: float = 0.5,
                   config_black: str | None = None, config_white: str | None = None):
    """AI vs AI mode. Two separate UAP providers play against each other."""
    game = GomokuGame()
    env_id_black = "gomoku_black"
    env_id_white = "gomoku_white"

    provider_black = make_provider(name="AI-Black", config_file=config_black)
    provider_white = make_provider(name="AI-White", config_file=config_white)

    print("=== Gomoku: AI-Black (X) vs AI-White (O) ===\n")

    # Declare environments for both AIs
    for env_id, provider, color in [
        (env_id_black, provider_black, "black"),
        (env_id_white, provider_white, "white"),
    ]:
        declare_msg = build_env_declare(env_id, color)
        print(f"[UAP] -> env.declare ({provider.name})")
        response = provider.handle_message(declare_msg)
        print(f"[UAP] <- {response['result']['summary']}")

    print()
    game.print_board()

    move_num = 0
    while game.game_status == "playing":
        move_num += 1
        if game.current_turn == "black":
            provider, env_id, label = provider_black, env_id_black, "AI-Black"
        else:
            provider, env_id, label = provider_white, env_id_white, "AI-White"

        observe_msg = build_env_observe(env_id, game)
        print(f"[Move {move_num}] {label}'s turn")
        print(f"[UAP] -> env.observe ({label})")
        response = provider.handle_message(observe_msg)
        print(f"[UAP] <- env.act")

        if not execute_actions(game, response, label):
            break

        game.print_board()
        time.sleep(delay)

    # Game over
    print(f"\n=== Game Over: {game.game_status.replace('_', ' ').title()} ===")
    print(f"Total moves: {len(game.move_history)}")

    for env_id, provider in [(env_id_black, provider_black), (env_id_white, provider_white)]:
        close_msg = build_env_close(env_id, game.game_status)
        response = provider.handle_message(close_msg)
        print(f"[{provider.name}] {response['result']['summary']}")


# --- Entry Point ---

def main():
    parser = argparse.ArgumentParser(description="UAP Gomoku Example (terminal)")
    parser.add_argument("--ai-vs-ai", action="store_true", help="AI vs AI mode")
    parser.add_argument("--ai-color", choices=["black", "white"], default="black",
                        help="AI's color in human vs AI mode (default: black)")
    parser.add_argument("--delay", type=float, default=0.5,
                        help="Delay between AI moves in AI-vs-AI mode (seconds)")
    parser.add_argument("--config", type=str, default=None,
                        help="Provider config file (human-vs-AI or default for both)")
    parser.add_argument("--config-black", type=str, default=None,
                        help="Black player's config in AI-vs-AI mode")
    parser.add_argument("--config-white", type=str, default=None,
                        help="White player's config in AI-vs-AI mode")
    args = parser.parse_args()

    if args.ai_vs_ai:
        play_ai_vs_ai(
            delay=args.delay,
            config_black=args.config_black or args.config,
            config_white=args.config_white or args.config,
        )
    else:
        play_human_vs_ai(ai_color=args.ai_color, config=args.config)


if __name__ == "__main__":
    main()
