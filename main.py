"""Arrow puzzle - Kivy UI. Core rules live in arrow_core.py."""
import json
import os
import random

from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, Ellipse, Line, RoundedRectangle, Triangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

from arrow_core import DIRS, Game, generate
from profile_store import ProfileStore

HEARTS = 3
HINTS_PER_LEVEL = 3
SLIDE_SPEED = 3.0  # progress per second (0 -> 1)
SCREEN_DIR = {"U": (0, 1), "D": (0, -1), "L": (-1, 0), "R": (1, 0)}  # y is up in Kivy

BG = (0.97, 0.97, 0.95, 1)
BOARD_BG = (0.92, 0.93, 0.91, 1)
INK = (0.15, 0.17, 0.2, 1)
HINT = (0.2, 0.7, 0.4, 1)
BAD = (0.9, 0.25, 0.25, 1)
PALETTE = [
    (0.91, 0.30, 0.24, 1),  # red
    (0.95, 0.61, 0.07, 1),  # orange
    (0.96, 0.80, 0.10, 1),  # yellow
    (0.18, 0.74, 0.38, 1),  # green
    (0.20, 0.60, 0.86, 1),  # blue
    (0.61, 0.35, 0.71, 1),  # purple
    (0.91, 0.39, 0.64, 1),  # pink
]


def level_params(level):
    size = min(4 + level // 3, 9)
    n_arrows = max(4, int(size * size * 0.55))
    bias = min(0.3 + 0.05 * level, 0.9)
    return size, n_arrows, bias


class BoardWidget(Widget):
    def __init__(self, on_tap, **kw):
        super().__init__(**kw)
        self.on_tap = on_tap
        self.game = None
        self.sliding = {}  # (r, c) -> [direction, progress]
        self.hint_cell = None
        self.flash = {}  # (r, c) -> seconds left
        self.bind(pos=self.redraw, size=self.redraw)
        Clock.schedule_interval(self.tick, 1 / 60)

    def set_game(self, game):
        self.game, self.sliding, self.hint_cell, self.flash = game, {}, None, {}
        cells = list(game.board.cells)
        random.shuffle(cells)
        self.colors = {cell: PALETTE[i % len(PALETTE)] for i, cell in enumerate(cells)}
        self.redraw()

    # geometry -------------------------------------------------------------
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

    # drawing --------------------------------------------------------------
    def draw_arrow(self, cx, cy, d, cs, color):
        dx, dy = SCREEN_DIR[d]
        px, py = -dy, dx
        Color(*color)
        Line(points=[cx - dx * 0.32 * cs, cy - dy * 0.32 * cs,
                     cx + dx * 0.12 * cs, cy + dy * 0.12 * cs],
             width=max(2, cs * 0.07), cap="round")
        tip = (cx + dx * 0.38 * cs, cy + dy * 0.38 * cs)
        bx, by = cx + dx * 0.08 * cs, cy + dy * 0.08 * cs
        w = 0.2 * cs
        Triangle(points=[*tip, bx + px * w, by + py * w, bx - px * w, by - py * w])

    def redraw(self, *_):
        self.canvas.clear()
        if not self.game:
            return
        b = self.game.board
        cs, ox, oy = self.metrics()
        with self.canvas:
            Color(*BOARD_BG)
            RoundedRectangle(pos=(ox, oy), size=(cs * b.cols, cs * b.rows), radius=[cs * 0.2])
            for (r, c), t in self.flash.items():
                cx, cy = self.center(r, c, cs, ox, oy)
                Color(*BAD[:3], min(1, t * 3))
                Ellipse(pos=(cx - cs * 0.45, cy - cs * 0.45), size=(cs * 0.9, cs * 0.9))
            if self.hint_cell:
                cx, cy = self.center(*self.hint_cell, cs, ox, oy)
                Color(*HINT[:3], 0.35)
                Ellipse(pos=(cx - cs * 0.45, cy - cs * 0.45), size=(cs * 0.9, cs * 0.9))
            for (r, c), d in b.cells.items():
                self.draw_arrow(*self.center(r, c, cs, ox, oy), d, cs, self.colors[(r, c)])
            for (r, c), (d, p) in self.sliding.items():
                cx, cy = self.center(r, c, cs, ox, oy)
                dr, dc = DIRS[d]
                steps = 1
                rr, cc = r + dr, c + dc
                while 0 <= rr < b.rows and 0 <= cc < b.cols:
                    steps, rr, cc = steps + 1, rr + dr, cc + dc
                off = p * p * steps * cs
                dx, dy = SCREEN_DIR[d]
                self.draw_arrow(cx + dx * off, cy + dy * off, d, cs, (*self.colors[(r, c)][:3], 1 - 0.6 * p))

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
    def build(self):
        self.profile_store = ProfileStore(self.profile_db_path())
        self.profile_name = self.profile_store.get_active_profile()
        self.level = self.load_level()
        self.game = None
        self.hints_left = 0
        self.advancing = False

        root = BoxLayout(orientation="vertical", padding=12, spacing=8)
        top = BoxLayout(size_hint_y=None, height=48)
        self.profile_btn = Button(text=f"Profile: {self.profile_name}", size_hint_x=None, width=180,
                                  on_release=lambda *_: self.show_profile_popup())
        self.level_lbl = Label(color=INK, font_size="20sp", bold=True)
        self.hearts_lbl = Label(color=INK, font_size="20sp")
        top.add_widget(self.profile_btn)
        top.add_widget(self.level_lbl)
        top.add_widget(self.hearts_lbl)
        self.status = Label(color=INK, size_hint_y=None, height=28, font_size="16sp")
        self.board = BoardWidget(self.handle_tap)
        bottom = BoxLayout(size_hint_y=None, height=56, spacing=8)
        self.hint_btn = Button(on_release=lambda *_: self.use_hint())
        bottom.add_widget(self.hint_btn)
        bottom.add_widget(Button(text="Restart", on_release=lambda *_: self.start_level()))
        for w in (top, self.status, self.board, bottom):
            root.add_widget(w)

        from kivy.core.window import Window
        Window.clearcolor = BG
        self.start_level()
        return root

    # persistence ----------------------------------------------------------
    def profile_db_path(self):
        return os.path.join(self.user_data_dir, "profiles.sqlite3")

    def load_level(self):
        return self.profile_store.get_level(self.profile_name)

    def save_level(self):
        self.profile_store.save_level(self.level, self.profile_name)
        self.profile_store.set_active_profile(self.profile_name)

    def set_profile(self, name):
        self.profile_name = self.profile_store.set_active_profile(name)
        self.level = self.load_level()
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

    # flow -----------------------------------------------------------------
    def start_level(self):
        size, n, bias = level_params(self.level)
        self.game = Game(generate(size, size, n, bias, seed=self.level), hearts=HEARTS)
        self.hints_left, self.advancing = HINTS_PER_LEVEL, False
        self.board.set_game(self.game)
        self.status.text = "Tap an arrow with a clear path"
        self.refresh_labels()

    def refresh_labels(self):
        self.profile_btn.text = f"Profile: {self.profile_name}"
        self.level_lbl.text = f"Level {self.level}"
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
            self.status.text = ""
        elif result == "blocked":
            self.board.flash[(r, c)] = 0.35
            self.status.text = "Blocked!"
        self.refresh_labels()
        self.board.redraw()
        if self.game.lost:
            self.status.text = "Out of lives - tap Restart"
        elif board.solved():
            self.advancing = True
            self.status.text = "Level clear!"
            Clock.schedule_once(self.next_level, 1.0)

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
            self.board.hint_cell = cell
            self.refresh_labels()
            self.board.redraw()


if __name__ == "__main__":
    ArrowApp().run()