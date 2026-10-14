"""Arrow puzzle - Kivy UI. Core rules live in arrow_core.py."""
import json
import os
import random
import sys
from datetime import datetime

from kivy.app import App
from kivy.clock import Clock
from kivy.core.image import Image as CoreImage
from kivy.graphics import Color, Ellipse, Line, Rectangle, RoundedRectangle, Triangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(__file__))

from arrow_core import DIRS, Game, generate
from profile_store import ProfileStore

HEARTS = 3
HINTS_PER_LEVEL = 3
SLIDE_SPEED = 3.0
SCREEN_DIR = {"U": (0, 1), "D": (0, -1), "L": (-1, 0), "R": (1, 0)}

BG = (0.843, 0.909, 0.804, 1.0)
BOARD_BG = (0.97, 0.99, 0.95, 1)
BOARD_FRAME = (0.66, 0.54, 0.38, 1)
BOARD_SHADOW = (0.36, 0.27, 0.19, 0.18)
GRID_DOT = (0.72, 0.80, 0.72, 0.80)
INK = (0.14, 0.17, 0.20, 1)
HINT = (0.18, 0.72, 0.50, 1)
BAD = (0.88, 0.28, 0.28, 1)
PALETTE = [
    (0.96, 0.42, 0.37, 1),
    (0.33, 0.76, 0.53, 1),
    (0.24, 0.62, 0.90, 1),
    (0.95, 0.69, 0.20, 1),
    (0.85, 0.53, 0.78, 1),
    (0.96, 0.78, 0.22, 1),
    (0.93, 0.57, 0.88, 1),
]

BOARD_THEME_DIR = os.path.join(os.path.dirname(__file__), "images")
BOARD_THEME_FILES = []
if os.path.isdir(BOARD_THEME_DIR):
    BOARD_THEME_FILES = [
        os.path.join(BOARD_THEME_DIR, name)
        for name in sorted(os.listdir(BOARD_THEME_DIR))
        if name.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
    ]


def level_params(level):
    size = min(4 + level // 3, 9)
    n_arrows = max(4, int(size * size * 0.55))
    bias = min(0.3 + 0.05 * level, 0.9)
    return size, n_arrows, bias


def board_theme_path(level):
    if not BOARD_THEME_FILES:
        return None
    return BOARD_THEME_FILES[(level - 1) % len(BOARD_THEME_FILES)]


class BoardWidget(Widget):
    def __init__(self, on_tap, **kw):
        super().__init__(**kw)
        self.on_tap = on_tap
        self.game = None
        self.theme_path = None
        self.sliding = {}
        self.hint_cell = None
        self.flash = {}
        self.bind(pos=self.redraw, size=self.redraw)
        Clock.schedule_interval(self.tick, 1 / 60)

    def set_game(self, game, theme_path=None):
        self.game = game
        self.theme_path = theme_path
        self.sliding, self.hint_cell, self.flash = {}, None, {}
        cells = list(game.board.cells)
        random.shuffle(cells)
        self.colors = {cell: PALETTE[i % len(PALETTE)] for i, cell in enumerate(cells)}
        self.redraw()

    def metrics(self):
        b = self.game.board
        cs = min(self.width / b.cols, self.height / b.rows)
        ox = self.x + (self.width - cs * b.cols) / 2
        oy = self.y + (self.height - cs * b.rows) / 2
        return cs, ox, oy

    def center(self, r, c, cs, ox, oy):
        b = self.game.board
        return ox + (c + 0.5) * cs, oy + (b.rows - 1 - r + 0.5) * cs

    def cell_at(self, x, y):
        b = self.game.board
        cs, ox, oy = self.metrics()
        c, r = int((x - ox) // cs), b.rows - 1 - int((y - oy) // cs)
        return (r, c) if 0 <= r < b.rows and 0 <= c < b.cols else None

    def draw_cell(self, cx, cy, cs, color, alpha=1.0):
        # No box: keep only a subtle floating shadow under the arrow.
        shadow_size = cs * 0.42
        Color(0.24, 0.25, 0.27, 0.12)
        Ellipse(pos=(cx - shadow_size / 2, cy - shadow_size / 2 - cs * 0.06), size=(shadow_size, shadow_size * 0.62))

    def draw_arrow(self, cx, cy, d, cs, color):
        dx, dy = SCREEN_DIR[d]
        px, py = -dy, dx

        # Clean, standard arrow: easy to read, fun but not gimmicky.
        shaft_start = (cx - dx * 0.18 * cs, cy - dy * 0.18 * cs)
        shaft_end = (cx + dx * 0.10 * cs, cy + dy * 0.10 * cs)
        tip = (cx + dx * 0.30 * cs, cy + dy * 0.30 * cs)
        left = (cx + dx * 0.10 * cs + px * 0.12 * cs, cy + dy * 0.10 * cs + py * 0.12 * cs)
        right = (cx + dx * 0.10 * cs - px * 0.12 * cs, cy + dy * 0.10 * cs - py * 0.12 * cs)

        Color(*color)
        Line(points=[*shaft_start, *shaft_end], width=max(3, cs * 0.10), cap='round', round=True)
        Triangle(points=[tip[0], tip[1], left[0], left[1], right[0], right[1]])

        # soft top highlight to keep it polished but not dark/ugly
        Color(1, 1, 1, 0.16)
        Line(points=[
            cx - dx * 0.12 * cs, cy - dy * 0.12 * cs,
            cx + dx * 0.04 * cs, cy + dy * 0.04 * cs,
        ], width=max(1, cs * 0.025), cap='round', round=True)


    def redraw(self, *_):
        self.canvas.clear()
        if not self.game:
            return
        b = self.game.board
        cs, ox, oy = self.metrics()
        with self.canvas:
            Color(*BOARD_SHADOW)
            RoundedRectangle(pos=(ox + 8, oy - 12), size=(cs * b.cols + 4, cs * b.rows + 4), radius=[cs * 0.30])

            Color(*BOARD_FRAME)
            RoundedRectangle(pos=(ox - 10, oy - 10), size=(cs * b.cols + 20, cs * b.rows + 20), radius=[cs * 0.28])

            Color(*BOARD_BG)
            RoundedRectangle(pos=(ox, oy), size=(cs * b.cols, cs * b.rows), radius=[cs * 0.22])

            # faint curved row accents for a playful learning board feel
            Color(0.67, 0.82, 0.67, 0.18)
            for i in range(1, max(2, min(b.rows, 5))):
                y = oy + (i / max(2, min(b.rows, 5))) * (cs * b.rows)
                points = []
                for x in range(int(b.cols + 1)):
                    px = ox + x * cs
                    wave = 0.12 * cs * (1 if x % 2 == 0 else -1)
                    points.extend([px, y + wave])
                Line(points=points, width=1.1, close=False)

            # subtle inner grid glow
            Color(1, 1, 1, 0.08)
            RoundedRectangle(pos=(ox + cs * 0.04, oy + cs * 0.04), size=(cs * b.cols - cs * 0.08, cs * b.rows - cs * 0.08), radius=[cs * 0.18])

            dot_color = GRID_DOT
            for r in range(b.rows + 1):
                y = oy + r * cs
                for c in range(b.cols + 1):
                    x = ox + c * cs
                    Color(*dot_color)
                    Ellipse(pos=(x - 2.8, y - 2.8), size=(5.6, 5.6))

            for (r, c), t in self.flash.items():
                cx, cy = self.center(r, c, cs, ox, oy)
                Color(*BAD[:3], min(1, t * 3))
                Ellipse(pos=(cx - cs * 0.42, cy - cs * 0.42), size=(cs * 0.84, cs * 0.84))

            if self.hint_cell:
                cx, cy = self.center(*self.hint_cell, cs, ox, oy)
                Color(*HINT[:3], 0.32)
                Ellipse(pos=(cx - cs * 0.40, cy - cs * 0.40), size=(cs * 0.80, cs * 0.80))

            for (r, c), d in b.cells.items():
                cx, cy = self.center(r, c, cs, ox, oy)
                self.draw_cell(cx, cy, cs, self.colors[(r, c)], alpha=0.95)
                self.draw_arrow(cx, cy, d, cs, self.colors[(r, c)])

            for (r, c), (d, p) in self.sliding.items():
                cx, cy = self.center(r, c, cs, ox, oy)
                dr, dc = DIRS[d]
                steps = 1
                rr, cc = r + dr, c + dc
                while 0 <= rr < b.rows and 0 <= cc < b.cols:
                    steps, rr, cc = steps + 1, rr + dr, cc + dc
                off = p * p * steps * cs
                dx, dy = SCREEN_DIR[d]
                self.draw_cell(cx + dx * off, cy + dy * off, cs, self.colors[(r, c)], alpha=0.78)
                self.draw_arrow(cx + dx * off, cy + dy * off, d, cs, (*self.colors[(r, c)][:3], 1 - 0.5 * p))

    def tick(self, dt):
        if not self.game:
            return
        dirty = False
        for cell in list(self.sliding):
            self.sliding[cell][1] += dt * SLIDE_SPEED
            dirty = True
            if self.sliding[cell][1] >= 1:
                del self.sliding[cell]
        for cell in list(self.flash):
            self.flash[cell] -= dt
            dirty = True
            if self.flash[cell] <= 0:
                del self.flash[cell]
        if dirty:
            self.redraw()

    def on_touch_down(self, touch):
        if not self.game or not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        cell = self.cell_at(*touch.pos)
        if cell:
            self.on_tap(*cell)
        return True


class ArrowApp(App):
    def profile_db_path(self):
        return os.path.join(self.user_data_dir, "arrow_logic_profiles.db")

    def load_level(self):
        return self.profile_store.get_level(self.profile_name)

    def save_level(self):
        self.profile_store.save_level(self.level, self.profile_name)

    def build(self):
        self.profile_store = ProfileStore(self.profile_db_path())
        self.profile_name = self.profile_store.get_active_profile()
        self.level = self.load_level()
        self.game = None
        self.hints_left = 0
        self.advancing = False
        self.start_time = datetime.utcnow()
        self.session_hints = 0
        self.session_stars = 0
        self.session_seconds = 0

        self.root = BoxLayout(orientation="vertical", padding=12, spacing=8)
        self.menu_screen = MenuScreen(self)
        self.reward_screen = RewardScreen(self)
        self.game_screen = GameScreen(self)
        self.bind_game_screen()
        self.root.add_widget(self.menu_screen)
        self.show_intro_if_needed()
        return self.root

    def bind_game_screen(self):
        self.profile_btn = self.game_screen.profile_btn
        self.level_lbl = self.game_screen.level_lbl
        self.hearts_lbl = self.game_screen.hearts_lbl
        self.status = self.game_screen.status
        self.board = self.game_screen.board
        self.hint_btn = self.game_screen.hint_btn

    def open_menu(self):
        self.root.clear_widgets()
        self.root.add_widget(self.menu_screen)

    def open_game(self):
        self.bind_game_screen()
        self.root.clear_widgets()
        self.root.add_widget(self.game_screen)
        self.start_level()

    def set_profile(self, name):
        self.profile_name = self.profile_store.set_active_profile(name)
        self.level = self.load_level()
        if self.game is not None:
            self.start_level()
        self.refresh_labels()
        if getattr(self, "profile_popup", None):
            self.profile_popup.dismiss()

    def show_profile_popup(self):
        content = BoxLayout(orientation="vertical", spacing=10, padding=10)
        content.add_widget(Label(text="Player name"))
        self.profile_input = TextInput(text=self.profile_name, multiline=False)
        content.add_widget(self.profile_input)
        content.add_widget(Button(text="Use this profile", on_release=lambda *_: self.set_profile(self.profile_input.text)))

        profiles = BoxLayout(orientation="vertical", spacing=6)
        for name in self.profile_store.list_profiles():
            profiles.add_widget(Button(text=name, on_release=lambda _, value=name: self.set_profile(value)))
        content.add_widget(Label(text="Saved profiles"))
        content.add_widget(profiles)

        popup = Popup(title="Profile", content=content, size_hint=(0.8, 0.8))
        self.profile_popup = popup
        popup.open()

    def show_intro_if_needed(self):
        stats = self.profile_store.get_stats(self.profile_name)
        if stats["levels_completed"] > 0:
            return
        content = BoxLayout(orientation="vertical", spacing=10, padding=20)
        content.add_widget(Label(text="Welcome to Arrow Logic!", bold=True, font_size="22sp"))
        content.add_widget(Label(text="Tap a glowing arrow that can be removed safely."))
        content.add_widget(Label(text="Try a few moves and watch the board clear!"))
        content.add_widget(Button(text="Start Learning", on_release=lambda *_: self.intro_popup.dismiss()))
        self.intro_popup = Popup(title="How to play", content=content, size_hint=(0.8, 0.8))
        self.intro_popup.open()

    def start_level(self):
        size, n, bias = level_params(self.level)
        self.game = Game(generate(size, size, n, bias, seed=self.level), hearts=HEARTS)
        self.hints_left, self.advancing = HINTS_PER_LEVEL, False
        self.start_time = datetime.utcnow()
        self.board.set_game(self.game, board_theme_path(self.level))
        self.status.text = "Tap an arrow with a clear path"
        self.refresh_labels()

    def refresh_labels(self):
        if not hasattr(self, "profile_btn"):
            return
        self.profile_btn.text = f"Profile: {self.profile_name}"
        self.level_lbl.text = f"Level {self.level}"
        if self.game is None:
            self.hearts_lbl.text = "Lives: --"
            self.hint_btn.text = "Hint (0)"
            return
        self.hearts_lbl.text = f"Lives: {self.game.hearts}/{HEARTS}"
        self.hint_btn.text = f"Hint ({self.hints_left})"

    def handle_tap(self, r, c):
        if self.advancing:
            return
        board = self.game.board
        d = board.cells.get((r, c))
        self.board.hint_cell = None
        result = self.game.tap(r, c)
        if result == "removed":
            self.board.sliding[(r, c)] = [d, 0.0]
            self.status.text = "Nice move!"
        elif result == "blocked":
            self.board.flash[(r, c)] = 0.35
            self.status.text = "Blocked! Try another arrow."
        self.refresh_labels()
        self.board.redraw()
        if self.game.lost:
            self.status.text = "Out of lives - tap Restart"
            self.show_game_over_popup()
        elif board.solved():
            self.advancing = True
            self.status.text = "Level clear!"
            self.finish_level_success()

    def show_game_over_popup(self):
        content = BoxLayout(orientation="vertical", spacing=10, padding=20)
        content.add_widget(Label(text="Game Over", bold=True, font_size="22sp", color=INK))
        content.add_widget(Label(text="You used all your lives. Try this level again!", halign="center", text_size=(300, None), color=INK))
        buttons = BoxLayout(size_hint_y=None, height=48, spacing=10)
        restart_btn = Button(text="Restart", on_release=lambda *_: self.close_game_over_popup())
        menu_btn = Button(text="Menu", on_release=lambda *_: self.close_game_over_popup(menu=True))
        buttons.add_widget(restart_btn)
        buttons.add_widget(menu_btn)
        content.add_widget(buttons)

        popup = Popup(title="Try again!", content=content, size_hint=(0.8, 0.5), auto_dismiss=False)
        self.game_over_popup = popup
        popup.open()

    def close_game_over_popup(self, menu=False):
        if getattr(self, "game_over_popup", None):
            self.game_over_popup.dismiss()
            self.game_over_popup = None
        if menu:
            self.open_menu()
            return
        self.start_level()

    def finish_level_success(self):
        elapsed = max(1, int((datetime.utcnow() - self.start_time).total_seconds()))
        stars = 3 if self.hints_left >= 2 else 2 if self.hints_left >= 1 else 1
        self.session_hints = max(0, HINTS_PER_LEVEL - self.hints_left)
        self.session_seconds = elapsed
        self.session_stars = stars
        self.profile_store.record_level_result(self.profile_name, self.level, stars=stars, hints_used=self.session_hints, play_time_seconds=elapsed)
        self.status.text = f"Level clear! You earned {stars} star(s)!"
        self.show_level_complete_popup(stars)

    def show_level_complete_popup(self, stars):
        message = (
            f"Amazing job! You cleared Level {self.level} with {stars} star(s).\n"
            "Ready for the next puzzle?"
        )
        content = BoxLayout(orientation="vertical", spacing=10, padding=20)
        content.add_widget(Label(text="Level Complete!", bold=True, font_size="22sp", color=INK))
        content.add_widget(Label(text=message, halign="center", valign="middle", text_size=(300, None), color=INK))

        buttons = BoxLayout(size_hint_y=None, height=48, spacing=10)
        next_btn = Button(text="Next Level", on_release=lambda *_: self.close_level_complete_popup("next"))
        restart_btn = Button(text="Restart", on_release=lambda *_: self.close_level_complete_popup("restart"))
        buttons.add_widget(next_btn)
        buttons.add_widget(restart_btn)
        content.add_widget(buttons)

        popup = Popup(title="Well done!", content=content, size_hint=(0.8, 0.5), auto_dismiss=False)
        self.level_popup = popup
        popup.open()

    def close_level_complete_popup(self, action):
        if getattr(self, "level_popup", None):
            self.level_popup.dismiss()
            self.level_popup = None
        if action == "next":
            self.level += 1
            self.save_level()
            self.start_level()
        elif action == "restart":
            self.start_level()
        self.advancing = False

    def next_level(self, *_):
        self.level += 1
        self.save_level()
        self.start_level()

    def use_hint(self):
        if self.advancing or self.game.lost or self.hints_left <= 0:
            return
        cell = self.game.hint()
        if cell:
            self.hints_left -= 1
            self.session_hints += 1
            self.board.hint_cell = cell
            self.status.text = "Hint used: look for the safe arrow."
            self.refresh_labels()
            self.board.redraw()

    def show_stats(self):
        stats = self.profile_store.get_stats(self.profile_name)
        content = BoxLayout(orientation="vertical", spacing=10, padding=20)
        content.add_widget(Label(text=f"Player: {self.profile_name}", bold=True))
        content.add_widget(Label(text=f"Best level: {stats['best_level']}"))
        content.add_widget(Label(text=f"Stars: {stats['total_stars']}"))
        content.add_widget(Label(text=f"Levels completed: {stats['levels_completed']}"))
        content.add_widget(Label(text=f"Hints used: {stats['total_hints_used']}"))
        content.add_widget(Button(text="Close", on_release=lambda *_: self.stats_popup.dismiss()))
        self.stats_popup = Popup(title="Progress", content=content, size_hint=(0.7, 0.7))
        self.stats_popup.open()


class MenuScreen(BoxLayout):
    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        self.orientation = "vertical"
        self.spacing = 16
        self.padding = 20
        self.size_hint = (1, 1)

        title = Label(text="Arrow Logic Kids", font_size="28sp", bold=True, color=INK)
        subtitle = Label(text="Think, plan, and clear the board!", font_size="18sp", color=INK)
        play = Button(text="Play", size_hint_y=None, height=56, on_release=lambda *_: self.app.open_game())
        stats = Button(text="Progress", size_hint_y=None, height=56, on_release=lambda *_: self.app.show_stats())
        profile = Button(text="Profile", size_hint_y=None, height=56, on_release=lambda *_: self.app.show_profile_popup())
        self.add_widget(title)
        self.add_widget(subtitle)
        self.add_widget(play)
        self.add_widget(stats)
        self.add_widget(profile)


class GameScreen(BoxLayout):
    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        self.orientation = "vertical"
        self.padding = 12
        self.spacing = 8

        top = BoxLayout(size_hint_y=None, height=52)
        self.profile_btn = Button(text=f"Profile: {app.profile_name}", size_hint_x=None, width=180,
                                  on_release=lambda *_: app.show_profile_popup())
        self.level_lbl = Label(color=INK, font_size="20sp", bold=True)
        self.hearts_lbl = Label(color=INK, font_size="20sp")
        top.add_widget(self.profile_btn)
        top.add_widget(self.level_lbl)
        top.add_widget(self.hearts_lbl)

        self.status = Label(color=INK, size_hint_y=None, height=30, font_size="16sp")
        self.board = BoardWidget(app.handle_tap)
        bottom = BoxLayout(size_hint_y=None, height=56, spacing=8)
        self.hint_btn = Button(on_release=lambda *_: app.use_hint())
        bottom.add_widget(self.hint_btn)
        bottom.add_widget(Button(text="Restart", on_release=lambda *_: app.start_level()))
        bottom.add_widget(Button(text="Menu", on_release=lambda *_: app.open_menu()))

        self.add_widget(top)
        self.add_widget(self.status)
        self.add_widget(self.board)
        self.add_widget(bottom)


class RewardScreen(BoxLayout):
    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        self.orientation = "vertical"
        self.spacing = 12
        self.padding = 20

        self.title = Label(text="Progress", font_size="24sp", bold=True, color=INK)
        self.summary = Label(color=INK, font_size="18sp")
        continue_btn = Button(text="Back to Menu", size_hint_y=None, height=56, on_release=lambda *_: app.open_menu())
        self.add_widget(self.title)
        self.add_widget(self.summary)
        self.add_widget(continue_btn)

    def refresh(self):
        stats = self.app.profile_store.get_stats(self.app.profile_name)
        self.summary.text = (
            f"Best level: {stats['best_level']}\n"
            f"Stars: {stats['total_stars']}\n"
            f"Levels cleared: {stats['levels_completed']}\n"
            f"Hints used: {stats['total_hints_used']}"
        )


if __name__ == "__main__":
    ArrowApp().run()
