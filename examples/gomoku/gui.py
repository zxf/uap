"""
UAP Gomoku Example - GUI (pygame)

Graphical interface for gomoku that uses UAP protocol underneath.
Features a menu screen to select game mode and providers.
Providers are auto-discovered from config files (*.yaml / *.json) in the working directory.

Usage:
    uv run gui.py

Create provider configs like openai.yaml, deepseek.yaml, etc.
See provider.example.yaml for all available options.
"""

import sys
import threading
import time
from pathlib import Path

import pygame

from provider import MockAIProvider
from provider_openai import OpenAIProvider, ProviderConfig

# --- Constants ---

BOARD_SIZE = 15
CELL_SIZE = 40
MARGIN = 40
BOARD_PX = CELL_SIZE * (BOARD_SIZE - 1)
WINDOW_W = BOARD_PX + MARGIN * 2
WINDOW_H = BOARD_PX + MARGIN * 2 + 50  # extra space for status bar

MENU_W = 480
MENU_H = 520

EMPTY, BLACK, WHITE = 0, 1, 2

# Colors
BG_COLOR = (220, 179, 92)
LINE_COLOR = (50, 40, 20)
BLACK_STONE = (20, 20, 20)
WHITE_STONE = (240, 240, 240)
HIGHLIGHT = (220, 50, 50)
TEXT_COLOR = (30, 30, 30)
STATUS_BG = (180, 140, 60)
MENU_BG = (45, 45, 55)
MENU_TEXT = (230, 230, 230)
MENU_ACCENT = (100, 180, 255)
MENU_BTN = (70, 70, 85)
MENU_BTN_HOVER = (90, 90, 110)
MENU_BTN_ACTIVE = (100, 180, 255)


# --- Game Logic (same as server.py) ---

class GomokuGame:
    def __init__(self):
        self.board = [[EMPTY] * BOARD_SIZE for _ in range(BOARD_SIZE)]
        self.current_turn = "black"
        self.move_history = []
        self.game_status = "playing"

    def place_stone(self, x: int, y: int) -> dict:
        if self.game_status != "playing":
            return {"success": False, "error": "Game is over"}
        if not (0 <= x < BOARD_SIZE and 0 <= y < BOARD_SIZE):
            return {"success": False, "error": "Out of range"}
        if self.board[y][x] != EMPTY:
            return {"success": False, "error": "Occupied"}

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


# --- UAP Message Builders ---

def build_env_declare(env_id: str, ai_color: str) -> dict:
    return {
        "uap": "0.2",
        "id": "req_declare",
        "method": "env.declare",
        "params": {
            "env_id": env_id,
            "name": "Gomoku",
            "description": (
                f"15x15 standard gomoku. You play as {ai_color.upper()} "
                f"({'1' if ai_color == 'black' else '2'}). "
                "Board: 0=empty, 1=black, 2=white. "
                "Coordinates: top-left (0,0), x=column, y=row. "
                "5 in a row wins. Only empty positions. Alternate turns."
            ),
            "example": {
                "inputs": {
                    "board_state": {
                        "board": [[0]*15 for _ in range(5)],
                        "current_turn": ai_color,
                        "move_history": [{"x": 7, "y": 7, "color": "black"}],
                        "game_status": "playing",
                    }
                },
                "actions": [{"id": "place_stone", "params": {"x": 7, "y": 8}}],
            },
            "inputs": [{"id": "board_state", "type": "structured", "description": "Board state"}],
            "actions": [
                {"id": "place_stone", "description": "Place stone at (x,y)"},
                {"id": "resign", "description": "Resign"},
            ],
        },
    }


def build_env_observe(env_id: str, game: GomokuGame, message: str = "") -> dict:
    msg = {
        "uap": "0.2",
        "id": f"req_{len(game.move_history):03d}",
        "method": "env.observe",
        "params": {"env_id": env_id, "inputs": {"board_state": game.to_state()}},
    }
    if message:
        msg["params"]["message"] = message
    return msg


# --- Provider Discovery ---

# "Human" is represented as None in the players list
HUMAN_PLAYER = {"name": "Human", "config_file": None, "is_human": True}


def discover_players() -> list[dict]:
    """Scan for provider configs. Returns list with Human + all discovered AI providers."""
    players = [
        HUMAN_PLAYER,
        {"name": "Mock AI (default)", "config_file": None, "is_human": False},
    ]

    for pattern in ("*.yaml", "*.yml", "*.json"):
        for p in sorted(Path(".").glob(pattern)):
            if p.name.startswith(".") or "example" in p.name:
                continue
            try:
                config = ProviderConfig.load(path=str(p))
                if config.provider == "openai":
                    label = f"{p.stem} [{config.model}]"
                elif config.provider == "local":
                    model_name = Path(config.model_path).stem if config.model_path else "?"
                    label = f"{p.stem} [local/{model_name}]"
                else:
                    label = f"{p.stem} [mock/{config.style}]"
                players.append({"name": label, "config_file": str(p), "is_human": False})
            except Exception:
                pass

    return players


def make_provider(name: str = "AI", config_file: str | None = None):
    config = ProviderConfig.load(path=config_file)
    if config.provider == "openai":
        return OpenAIProvider(name=name, config=config)
    elif config.provider == "local":
        from provider_local import LocalGomokuProvider
        return LocalGomokuProvider(name=name, config=config)
    return MockAIProvider(name=name, style=config.style)


# --- Menu Screen ---

class MenuScreen:
    """Select who plays Black and who plays White: Human or any AI provider."""

    def __init__(self):
        self.players = discover_players()
        self.black_idx = 0  # 0 = Human
        self.white_idx = 1  # 1 = Mock AI

    def run(self, screen, clock) -> dict | None:
        font = pygame.font.SysFont("Arial", 18)
        font_title = pygame.font.SysFont("Arial", 32, bold=True)
        font_small = pygame.font.SysFont("Arial", 14)

        while True:
            mouse_pos = pygame.mouse.get_pos()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return None
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    result = self._handle_click(mouse_pos)
                    if result is not None:
                        return result
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        return self._build_config()
                    elif event.key == pygame.K_ESCAPE:
                        return None

            self._draw(screen, font, font_title, font_small, mouse_pos)
            pygame.display.flip()
            clock.tick(30)

    def _handle_click(self, pos) -> dict | None:
        x, y = pos
        mid = MENU_W // 2
        left = 30
        right = MENU_W - 30

        # Black player list (left column)
        base_y = 120
        for i in range(len(self.players)):
            by = base_y + i * 35
            if by <= y <= by + 30 and left <= x <= mid - 10:
                self.black_idx = i
                return None

        # White player list (right column)
        for i in range(len(self.players)):
            by = base_y + i * 35
            if by <= y <= by + 30 and mid + 10 <= x <= right:
                self.white_idx = i
                return None

        # Start button
        btn_y = MENU_H - 80
        btn_rect = pygame.Rect(mid - 80, btn_y, 160, 45)
        if btn_rect.collidepoint(pos):
            return self._build_config()

        return None

    def _build_config(self) -> dict:
        return {
            "black": self.players[self.black_idx],
            "white": self.players[self.white_idx],
        }

    def _draw(self, screen, font, font_title, font_small, mouse_pos):
        screen.fill(MENU_BG)
        left = 30
        right = MENU_W - 30
        mid = MENU_W // 2

        # Title
        title = font_title.render("UAP Gomoku", True, MENU_ACCENT)
        screen.blit(title, (mid - title.get_width() // 2, 20))

        subtitle = font_small.render("Unified AI Protocol Example", True, (150, 150, 160))
        screen.blit(subtitle, (mid - subtitle.get_width() // 2, 58))

        # Column headers
        header_y = 90
        hb = font.render("Black (X)", True, MENU_TEXT)
        hw = font.render("White (O)", True, MENU_TEXT)
        screen.blit(hb, (left + (mid - 10 - left - hb.get_width()) // 2, header_y))
        screen.blit(hw, (mid + 10 + (right - mid - 10 - hw.get_width()) // 2, header_y))

        # Player lists
        base_y = 120
        self._draw_player_list(screen, font_small, base_y, left, mid - 10,
                               self.black_idx, mouse_pos)
        self._draw_player_list(screen, font_small, base_y, mid + 10, right,
                               self.white_idx, mouse_pos)

        # Start button
        btn_y = MENU_H - 80
        btn_rect = pygame.Rect(mid - 80, btn_y, 160, 45)
        hover = btn_rect.collidepoint(mouse_pos)
        pygame.draw.rect(screen, MENU_ACCENT if hover else MENU_BTN, btn_rect, border_radius=8)
        t = font.render("Start Game", True, (255, 255, 255) if hover else MENU_TEXT)
        screen.blit(t, (mid - t.get_width() // 2, btn_y + 12))

        # Summary
        bp = self.players[self.black_idx]["name"]
        wp = self.players[self.white_idx]["name"]
        summary = font_small.render(f"{bp}  vs  {wp}", True, MENU_ACCENT)
        screen.blit(summary, (mid - summary.get_width() // 2, btn_y - 25))

        # Hint
        hint = font_small.render("Enter to start / Esc to quit", True, (100, 100, 110))
        screen.blit(hint, (mid - hint.get_width() // 2, MENU_H - 25))

    def _draw_player_list(self, screen, font, base_y, x0, x1, selected_idx, mouse_pos):
        for i, p in enumerate(self.players):
            by = base_y + i * 35
            rect = pygame.Rect(x0, by, x1 - x0, 30)

            if i == selected_idx:
                color = MENU_BTN_ACTIVE
            elif rect.collidepoint(mouse_pos):
                color = MENU_BTN_HOVER
            else:
                color = MENU_BTN

            pygame.draw.rect(screen, color, rect, border_radius=4)
            t = font.render(p["name"], True,
                            (255, 255, 255) if i == selected_idx else MENU_TEXT)
            screen.set_clip(rect)
            screen.blit(t, (x0 + 8, by + (30 - t.get_height()) // 2))
            screen.set_clip(None)


# --- Game GUI ---

class GomokuGUI:
    def __init__(self, black: dict, white: dict, delay: float = 0.5):
        """black/white: player dicts from MenuScreen (name, config_file, is_human)."""
        self.game = GomokuGame()
        self.status_text = ""
        self.thinking_text = ""
        self.ai_thinking = False
        self.hover_pos = None
        self.delay = delay

        self._black_cfg = black
        self._white_cfg = white

        # Build players: None means human, otherwise a provider instance
        self.players = {"black": None, "white": None}

        if not black["is_human"]:
            self.players["black"] = make_provider("Black", black["config_file"])
            self._declare_env("gomoku_b", self.players["black"], "black")

        if not white["is_human"]:
            self.players["white"] = make_provider("White", white["config_file"])
            self._declare_env("gomoku_w", self.players["white"], "white")

        self.status_text = f"Black(X): {black['name']}  |  White(O): {white['name']}"

    def _is_human(self, color: str) -> bool:
        return self.players[color] is None

    def _declare_env(self, env_id: str, provider, color: str):
        msg = build_env_declare(env_id, color)
        provider.handle_message(msg)

    def _ai_move(self, color: str) -> dict | None:
        provider = self.players[color]
        env_id = "gomoku_b" if color == "black" else "gomoku_w"
        observe_msg = build_env_observe(env_id, self.game)
        response = provider.handle_message(observe_msg)
        result = response.get("result", {})

        self.thinking_text = result.get("thinking", "")

        for action in result.get("actions", []):
            if action["id"] == "place_stone":
                x, y = action["params"]["x"], action["params"]["y"]
                self.game.place_stone(x, y)
                return action
            elif action["id"] == "resign":
                winner = "white" if color == "black" else "black"
                self.game.game_status = f"{winner}_wins"
        return None

    def run(self, screen, clock):
        screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
        pygame.display.set_caption("UAP Gomoku")
        font = pygame.font.SysFont("Arial", 16)
        font_large = pygame.font.SysFont("Arial", 28, bold=True)

        # If first player is AI, make its move
        if not self._is_human("black"):
            self.ai_thinking = True
            self._ai_move("black")
            self.ai_thinking = False

        # Start auto-play thread if no humans
        if not self._is_human("black") and not self._is_human("white"):
            threading.Thread(target=self._auto_play_loop, daemon=True).start()

        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "quit"
                elif event.type == pygame.MOUSEMOTION:
                    self.hover_pos = self._pixel_to_board(event.pos)
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self._handle_click(event.pos)
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_r:
                        self._restart()
                    elif event.key == pygame.K_ESCAPE:
                        return "menu"

            self._draw(screen, font, font_large)
            pygame.display.flip()
            clock.tick(30)

    def _handle_click(self, pos):
        if self.ai_thinking or self.game.game_status != "playing":
            return
        turn = self.game.current_turn
        if not self._is_human(turn):
            return

        board_pos = self._pixel_to_board(pos)
        if board_pos is None:
            return
        x, y = board_pos

        result = self.game.place_stone(x, y)
        if not result["success"]:
            return

        # If the next player is AI, trigger its move
        next_turn = self.game.current_turn
        if self.game.game_status == "playing" and not self._is_human(next_turn):
            self.ai_thinking = True
            threading.Thread(target=self._do_ai_move, args=(next_turn,), daemon=True).start()

    def _do_ai_move(self, color: str):
        time.sleep(0.3)
        self._ai_move(color)
        self.ai_thinking = False
        # If the next player is also AI (shouldn't happen in human-involved game, but safe)
        next_turn = self.game.current_turn
        if self.game.game_status == "playing" and not self._is_human(next_turn):
            self.ai_thinking = True
            self._do_ai_move(next_turn)

    def _auto_play_loop(self):
        """Both players are AI."""
        while self.game.game_status == "playing":
            time.sleep(self.delay)
            self._ai_move(self.game.current_turn)

    def _restart(self):
        self.game = GomokuGame()
        self.thinking_text = ""
        self.ai_thinking = False

        # Re-init first AI move or auto-play
        if not self._is_human("black"):
            if not self._is_human("white"):
                threading.Thread(target=self._auto_play_loop, daemon=True).start()
            else:
                self.ai_thinking = True
                threading.Thread(target=self._do_ai_move, args=("black",), daemon=True).start()

    def _pixel_to_board(self, pos) -> tuple[int, int] | None:
        px, py = pos
        x = round((px - MARGIN) / CELL_SIZE)
        y = round((py - MARGIN) / CELL_SIZE)
        if 0 <= x < BOARD_SIZE and 0 <= y < BOARD_SIZE:
            return x, y
        return None

    def _board_to_pixel(self, x: int, y: int) -> tuple[int, int]:
        return MARGIN + x * CELL_SIZE, MARGIN + y * CELL_SIZE

    def _draw(self, screen, font, font_large):
        screen.fill(BG_COLOR)

        # Grid lines
        for i in range(BOARD_SIZE):
            px = MARGIN + i * CELL_SIZE
            pygame.draw.line(screen, LINE_COLOR, (px, MARGIN), (px, MARGIN + BOARD_PX), 1)
            pygame.draw.line(screen, LINE_COLOR, (MARGIN, px), (MARGIN + BOARD_PX, px), 1)

        # Star points
        for sy in (3, 7, 11):
            for sx in (3, 7, 11):
                px, py = self._board_to_pixel(sx, sy)
                pygame.draw.circle(screen, LINE_COLOR, (px, py), 4)

        # Stones
        last_move = self.game.move_history[-1] if self.game.move_history else None
        for y in range(BOARD_SIZE):
            for x in range(BOARD_SIZE):
                stone = self.game.board[y][x]
                if stone == EMPTY:
                    continue
                px, py = self._board_to_pixel(x, y)
                color = BLACK_STONE if stone == BLACK else WHITE_STONE
                pygame.draw.circle(screen, color, (px, py), CELL_SIZE // 2 - 2)
                if stone == WHITE:
                    pygame.draw.circle(screen, (100, 100, 100), (px, py), CELL_SIZE // 2 - 2, 1)
                if last_move and last_move["x"] == x and last_move["y"] == y:
                    pygame.draw.circle(screen, HIGHLIGHT, (px, py), 5)

        # Hover indicator for human turn
        turn = self.game.current_turn
        if (self._is_human(turn) and self.hover_pos and not self.ai_thinking
                and self.game.game_status == "playing"):
            hx, hy = self.hover_pos
            if self.game.board[hy][hx] == EMPTY:
                px, py = self._board_to_pixel(hx, hy)
                color = BLACK_STONE if turn == "black" else WHITE_STONE
                s = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)
                pygame.draw.circle(s, (*color, 100), (CELL_SIZE // 2, CELL_SIZE // 2), CELL_SIZE // 2 - 2)
                screen.blit(s, (px - CELL_SIZE // 2, py - CELL_SIZE // 2))

        # Coordinate labels
        for i in range(BOARD_SIZE):
            px = MARGIN + i * CELL_SIZE
            label = font.render(str(i), True, TEXT_COLOR)
            screen.blit(label, (px - label.get_width() // 2, MARGIN - 25))
            screen.blit(label, (MARGIN - 25, px - label.get_height() // 2))

        # Status bar
        status_y = MARGIN * 2 + BOARD_PX + 5
        pygame.draw.rect(screen, STATUS_BG, (0, status_y - 5, WINDOW_W, 50))

        if self.game.game_status != "playing":
            status = self.game.game_status.replace("_", " ").title()
            text = font_large.render(f"Game Over: {status}  (R restart / Esc menu)", True, HIGHLIGHT)
        elif self.ai_thinking:
            text = font.render(f"AI thinking... {self.thinking_text}", True, TEXT_COLOR)
        elif self.thinking_text and self.game.move_history:
            turn_label = "BLACK(X)" if turn == "black" else "WHITE(O)"
            who = self._black_cfg["name"] if turn == "black" else self._white_cfg["name"]
            text = font.render(f"{turn_label} {who}'s turn | {self.thinking_text}", True, TEXT_COLOR)
        else:
            text = font.render(self.status_text + "  (Esc: menu)", True, TEXT_COLOR)

        screen.blit(text, (10, status_y + 2))

        move_text = font.render(f"Move: {len(self.game.move_history)}", True, TEXT_COLOR)
        screen.blit(move_text, (WINDOW_W - move_text.get_width() - 10, status_y + 2))


# --- Main Loop ---

def main():
    pygame.init()
    screen = pygame.display.set_mode((MENU_W, MENU_H))
    pygame.display.set_caption("UAP Gomoku")
    clock = pygame.time.Clock()

    while True:
        menu = MenuScreen()
        screen = pygame.display.set_mode((MENU_W, MENU_H))
        pygame.display.set_caption("UAP Gomoku - Menu")
        config = menu.run(screen, clock)
        if config is None:
            break

        gui = GomokuGUI(**config)
        result = gui.run(screen, clock)
        if result == "quit":
            break

    pygame.quit()


if __name__ == "__main__":
    main()
