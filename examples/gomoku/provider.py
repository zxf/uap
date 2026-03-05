"""
UAP Gomoku Example - AI Provider

A mock UAP Provider that plays gomoku with configurable strategy.

In a real implementation, this would be replaced by an HTTP/WebSocket/stdio
connection to an actual AI service (OpenAI, Anthropic, etc.).
The Provider receives env.declare/env.observe messages and returns env.act responses.
"""

import random

BOARD_SIZE = 15
EMPTY, BLACK, WHITE = 0, 1, 2


class MockAIProvider:
    """
    Mock UAP Provider for gomoku.

    Implements the Provider side of the UAP protocol:
    - env.declare -> understand environment, return confirmation
    - env.observe -> analyze inputs, return actions (env.act)
    - env.close   -> return summary
    """

    def __init__(self, name: str = "AI", style: str = "balanced"):
        self.name = name
        self.style = style  # "aggressive", "defensive", "balanced"
        self.env_declaration = None
        self.my_color = None
        self.my_stone = None
        self.opp_stone = None

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
        desc = self.env_declaration["description"]

        if "BLACK" in desc or "black" in desc.split("play as")[-1][:10]:
            self.my_color = "black"
            self.my_stone = BLACK
            self.opp_stone = WHITE
        else:
            self.my_color = "white"
            self.my_stone = WHITE
            self.opp_stone = BLACK

        return {
            "uap": "0.2",
            "id": message["id"],
            "status": "ok",
            "result": {
                "env_id": self.env_declaration["env_id"],
                "understood": True,
                "summary": (
                    f"I'm {self.name}, playing as {self.my_color.upper()}. "
                    f"Strategy: {self.style}. "
                    f"Available actions: place_stone(x, y) and resign."
                ),
                "ready": True,
                "initial_input_request": ["board_state"],
            },
        }

    def _handle_observe(self, message: dict) -> dict:
        board_state = message["params"]["inputs"]["board_state"]
        board = board_state["board"]
        current_turn = board_state["current_turn"]

        # Not my turn
        if current_turn != self.my_color:
            return self._act(message, [], "continue", thinking="Waiting for opponent.")

        x, y = self._find_best_move(board)
        thinking = self._explain_move(board, x, y)

        return self._act(
            message,
            [{"id": "place_stone", "params": {"x": x, "y": y}}],
            "continue",
            thinking=thinking,
        )

    def _handle_close(self, message: dict) -> dict:
        reason = message["params"].get("reason", "unknown")
        if "wins" in reason:
            winner = reason.replace("_wins", "")
            if winner == self.my_color:
                summary = f"[{self.name}] I won! Good game."
            else:
                summary = f"[{self.name}] I lost. Well played!"
        elif reason == "draw":
            summary = f"[{self.name}] It's a draw. Intense game!"
        else:
            summary = f"[{self.name}] Game ended."

        return {
            "uap": "0.2",
            "id": message["id"],
            "status": "ok",
            "result": {
                "env_id": message["params"]["env_id"],
                "summary": summary,
                "stats": {},
            },
        }

    # --- Response Helpers ---

    def _act(self, message: dict, actions: list, status: str, thinking: str = "") -> dict:
        result = {
            "env_id": message["params"]["env_id"],
            "actions": actions,
            "status": status,
            "next_input_request": ["board_state"],
        }
        if thinking:
            result["thinking"] = thinking
        return {
            "uap": "0.2",
            "id": message["id"],
            "status": "ok",
            "result": result,
            "usage": {"input_tokens": 500, "output_tokens": 20},
        }

    def _error(self, message: dict, code: str, msg: str) -> dict:
        return {
            "uap": "0.2",
            "id": message.get("id"),
            "status": "error",
            "error": {"code": code, "message": msg},
        }

    # --- Move Strategy ---

    def _find_best_move(self, board: list[list[int]]) -> tuple[int, int]:
        center = BOARD_SIZE // 2

        if all(board[y][x] == EMPTY for y in range(BOARD_SIZE) for x in range(BOARD_SIZE)):
            return center, center

        best_score = -1
        best_moves = [(center, center)]

        for y in range(BOARD_SIZE):
            for x in range(BOARD_SIZE):
                if board[y][x] != EMPTY:
                    continue
                if not self._has_neighbor(board, x, y):
                    continue
                score = self._evaluate_move(board, x, y)
                if score > best_score:
                    best_score = score
                    best_moves = [(x, y)]
                elif score == best_score:
                    best_moves.append((x, y))

        return random.choice(best_moves)

    def _has_neighbor(self, board: list[list[int]], x: int, y: int, radius: int = 2) -> bool:
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE and board[ny][nx] != EMPTY:
                    return True
        return False

    def _evaluate_move(self, board: list[list[int]], x: int, y: int) -> int:
        score = 0
        directions = [(1, 0), (0, 1), (1, 1), (1, -1)]

        attack_weight, defense_weight = {
            "aggressive": (20, 10),
            "defensive": (10, 18),
            "balanced": (15, 13),
        }.get(self.style, (15, 13))

        for dx, dy in directions:
            for stone, weight in [(self.my_stone, attack_weight), (self.opp_stone, defense_weight)]:
                count, open_ends = self._count_line(board, x, y, dx, dy, stone)

                if count >= 4:
                    score += 100000 * weight
                elif count == 3 and open_ends == 2:
                    score += 10000 * weight
                elif count == 3 and open_ends == 1:
                    score += 1000 * weight
                elif count == 2 and open_ends == 2:
                    score += 500 * weight
                elif count == 2 and open_ends == 1:
                    score += 100 * weight
                elif count == 1 and open_ends == 2:
                    score += 10 * weight

        # Center preference
        center = BOARD_SIZE // 2
        distance = abs(x - center) + abs(y - center)
        score += max(0, 15 - distance)

        return score

    def _count_line(self, board: list[list[int]], x: int, y: int,
                    dx: int, dy: int, stone: int) -> tuple[int, int]:
        """Count consecutive stones and open ends in a direction."""
        count = 0
        open_ends = 0

        for sign in (1, -1):
            nx, ny = x + dx * sign, y + dy * sign
            while 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE and board[ny][nx] == stone:
                count += 1
                nx += dx * sign
                ny += dy * sign
            # Check if the end is open
            if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE and board[ny][nx] == EMPTY:
                open_ends += 1

        return count, open_ends

    def _explain_move(self, board: list[list[int]], x: int, y: int) -> str:
        directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
        dir_names = ["horizontal", "vertical", "diagonal", "anti-diagonal"]

        # Check if winning
        for (dx, dy), name in zip(directions, dir_names):
            count, _ = self._count_line(board, x, y, dx, dy, self.my_stone)
            if count >= 4:
                return f"Winning move at ({x},{y})! Five in a row {name}."

        # Check if blocking
        for (dx, dy), name in zip(directions, dir_names):
            count, open_ends = self._count_line(board, x, y, dx, dy, self.opp_stone)
            if count >= 3 and open_ends >= 1:
                return f"Blocking opponent's {name} threat at ({x},{y})."

        # Check if extending
        for (dx, dy), name in zip(directions, dir_names):
            count, open_ends = self._count_line(board, x, y, dx, dy, self.my_stone)
            if count >= 2:
                return f"Extending my {name} line to {count + 1} at ({x},{y})."

        return f"Playing at ({x},{y})."
