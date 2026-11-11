"""Star Sweep: catch falling stars, dodge meteors. Run: python game.py"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import time
import tkinter as tk

from logic import (
    H, LASER_LEN, SHIP_Y, W, Game, Thing, autopilot, autopilot_aim, autopilot_fire, bearing,
    direction, ship_relative,
)
from guide import PAGES
from sounds import Sounds

FIRE_KEYS = ("space",)

BG = "#0b1026"
FONT = "Segoe UI"


def save_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    path = os.path.join(base, "StarSweep")
    os.makedirs(path, exist_ok=True)
    return path


def load_high_score() -> int:
    try:
        with open(os.path.join(save_dir(), "highscore.json"), encoding="utf-8") as f:
            return int(json.load(f).get("high_score", 0))
    except Exception:
        return 0


def save_high_score(score: int) -> None:
    try:
        with open(os.path.join(save_dir(), "highscore.json"), "w", encoding="utf-8") as f:
            json.dump({"high_score": score}, f)
    except Exception:
        pass


def star_points(x: float, y: float, r: float, angle: float) -> list[float]:
    pts: list[float] = []
    for i in range(10):
        rad = r if i % 2 == 0 else r * 0.45
        a = angle + i * math.pi / 5 - math.pi / 2
        pts += [x + rad * math.cos(a), y + rad * math.sin(a)]
    return pts


def rock_points(x: float, y: float, r: float, angle: float, seed: int) -> list[float]:
    rng = random.Random(seed)
    n = 9
    pts: list[float] = []
    for i in range(n):
        a = angle + i * math.tau / n
        rad = r * rng.uniform(0.72, 1.08)
        pts += [x + rad * math.cos(a), y + rad * math.sin(a)]
    return pts


class App:
    def __init__(self, root: tk.Tk, demo: bool = False, frames: int | None = None,
                 report: str | None = None, seconds: float | None = None) -> None:
        self.root = root
        self.demo = demo
        self.frame_limit = frames
        self.report = report
        self.quit_at = time.perf_counter() + seconds if seconds else None
        self.frames = 0
        self.errors: list[str] = []

        root.title("Star Sweep")
        root.resizable(False, False)
        self._set_icon()
        root.configure(bg=BG)
        self.canvas = tk.Canvas(root, width=W, height=H, bg=BG, highlightthickness=0)
        self.canvas.pack()

        self.sounds = Sounds()
        if demo or frames:
            self.sounds.muted = True
        first_run = not os.path.exists(os.path.join(save_dir(), "highscore.json"))
        self.game = Game(high_score=load_high_score())
        self.page = 0  # How to Play page
        self.guide_return = "title"  # where Esc leaves the guide to
        if demo or frames:
            self.state = "playing"
        else:
            self.state = "guide" if first_run else "title"  # teach new players first

        self.keys: set[str] = set()
        self.mouse_x: float | None = None
        self.mouse_y: float | None = None
        self.mouse_active = False
        self.mouse_down = False
        self.thrust = 0  # 1 forward, -1 back: sizes the exhaust flame

        self._make_background()
        root.bind("<KeyPress>", self.on_key)
        root.bind("<KeyRelease>", lambda e: self.keys.discard(e.keysym.lower()))
        self.canvas.bind("<Motion>", self.on_mouse)
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<ButtonRelease-1>", lambda e: setattr(self, "mouse_down", False))
        root.protocol("WM_DELETE_WINDOW", self.close)

        self.last = time.perf_counter()
        self.tick()

    def _set_icon(self) -> None:
        # Next to the script, or inside the .exe's unpack folder.
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base, "icon.png")
        if os.path.exists(path):
            try:
                self._icon = tk.PhotoImage(file=path)
                self.root.iconphoto(True, self._icon)
            except tk.TclError:
                pass

    # --- background starfield: three layers drifting at different speeds ---
    def _make_background(self) -> None:
        rng = random.Random(7)
        self.bg: list[tuple[int, float]] = []
        for speed, size, color, count in ((12, 1, "#2a3566", 60), (28, 1.5, "#4a5a9a", 35), (55, 2, "#9fb0ff", 18)):
            for _ in range(count):
                x, y = rng.uniform(0, W), rng.uniform(0, H)
                item = self.canvas.create_oval(x, y, x + size, y + size, fill=color, outline="")
                self.bg.append((item, speed))

    def _drift_background(self, dt: float) -> None:
        slow = 0.5 if self.game.slow > 0 else 1.0
        for item, speed in self.bg:
            self.canvas.move(item, 0, speed * dt * slow)
            x0, y0, x1, y1 = self.canvas.coords(item)
            if y0 > H:
                self.canvas.move(item, 0, -H - (y1 - y0))

    # --- input --------------------------------------------------------------
    def on_key(self, event: tk.Event | None, name: str | None = None) -> None:
        key = name or event.keysym.lower()
        if key in ("q", "e"):
            self.mouse_active = False  # keyboard aiming until the mouse moves again
        self.keys.add(key)
        if self.state == "guide":
            self.keys.discard(key)  # guide keys never reach the game
            self.guide_key(key)
            return
        if key == "m":
            self.sounds.muted = not self.sounds.muted
        elif key == "h" and self.state in ("title", "paused", "over"):
            self.open_guide()
        elif key in ("space", "return"):
            if self.state in ("title", "over"):
                self.keys.discard("space")  # the start press shouldn't also fire
                self.start()
            elif self.state == "paused":
                self.state = "playing"
        elif key in ("p", "escape"):
            if self.state == "playing":
                self.state = "paused"
            elif self.state == "paused":
                self.state = "playing"
        elif key == "r" and self.state in ("over", "paused"):
            self.start()

    def open_guide(self) -> None:
        self.guide_return = self.state
        self.page = 0
        self.state = "guide"

    def guide_key(self, key: str) -> None:
        last = len(PAGES) - 1
        if key in ("left", "a", "prior"):
            self.page = max(0, self.page - 1)
        elif key in ("right", "d", "next", "space", "return"):
            if self.page < last:
                self.page += 1
            elif key in ("space", "return"):
                # The last page's Space starts a game (or resumes one paused).
                if self.guide_return == "paused":
                    self.state = "paused"
                else:
                    self.start()
        elif key in ("escape", "h"):
            self.state = self.guide_return if self.guide_return != "guide" else "title"
        elif key == "m":
            self.sounds.muted = not self.sounds.muted

    def on_press(self, event: tk.Event) -> None:
        if self.state == "playing":
            self.mouse_down = True  # hold to fire
        else:
            self.on_key(None, "space")

    def on_mouse(self, event: tk.Event) -> None:
        self.mouse_x = event.x
        self.mouse_y = event.y
        self.mouse_active = True  # the ship faces the pointer

    def start(self) -> None:
        high = self.game.high_score
        self.game = Game(high_score=high)
        self.state = "playing"
        self.sounds.play("start")

    @property
    def autoplay(self) -> bool:
        return bool(self.demo or self.frame_limit)

    def close(self) -> None:
        if not self.autoplay:  # the computer's scores don't count
            save_high_score(self.game.high_score)
        self._write_report()
        self.root.destroy()

    def _write_report(self) -> None:
        if not self.report:
            return
        g = self.game
        data = {
            "frames": self.frames, "score": g.score, "lives": g.lives, "caught": g.caught,
            "level": g.level, "over": g.over, "time": round(g.time, 2), "errors": self.errors,
            "meteors_shot": g.meteors_shot,
        }
        with open(self.report, "w", encoding="utf-8") as f:
            json.dump(data, f)

    # --- main loop ------------------------------------------------------------
    def tick(self) -> None:
        now = time.perf_counter()
        dt = min(0.05, now - self.last)
        self.last = now
        if self.frame_limit:
            dt = 1 / 60  # smoke test: fixed steps, as fast as possible
        try:
            self.update(dt)
            self.draw()
        except Exception as exc:  # keep a broken frame from killing the game silently
            self.errors.append(repr(exc))
            if self.frame_limit or self.demo:
                self.close()
                return
            raise
        self.frames += 1
        if self.frame_limit and self.frames >= self.frame_limit:
            self.close()
            return
        if self.quit_at and now >= self.quit_at:
            self.close()
            return
        self.root.after(1 if self.frame_limit else 15, self.tick)

    def update(self, dt: float) -> None:
        self._drift_background(dt)
        g = self.game
        if self.state != "playing":
            g._update_effects(dt)
            return
        if self.autoplay:
            g.step(dt, target_x=autopilot(g), target_y=SHIP_Y, aim=autopilot_aim(g), firing=autopilot_fire(g))
            if g.over:  # keep the demo going; its scores are never saved
                high = g.high_score
                g.reset()
                g.high_score = high
        else:
            k = self.keys
            # Controls are relative to the ship: forward goes where the nose points.
            strafe = ("right" in k or "d" in k) - ("left" in k or "a" in k)
            forward = ("up" in k or "w" in k) - ("down" in k or "s" in k)
            self.thrust = forward
            mx, my = ship_relative(forward, strafe, g.aim)
            turn = ("e" in k) - ("q" in k)
            aim = None
            if self.mouse_active and self.mouse_x is not None and self.mouse_y is not None:
                aim = bearing(g.ship_x, g.ship_y, self.mouse_x, self.mouse_y)
            firing = self.mouse_down or any(f in k for f in FIRE_KEYS)
            g.step(dt, move=float(mx), move_y=float(my), aim=aim, turn=float(turn), firing=firing)
        for ev in g.events:
            self.sounds.play(ev)
        g.events.clear()
        if g.over:
            self.state = "over"
            if not self.autoplay:
                save_high_score(g.high_score)

    # --- drawing ----------------------------------------------------------------
    def draw(self) -> None:
        c = self.canvas
        c.delete("dyn")
        g = self.game

        if self.state == "title":
            self._draw_title()
            return
        if self.state == "guide":
            self._draw_guide()
            return

        for t in g.things:
            self._draw_thing(t)
        for b in g.lasers:
            tx, ty = b.x - b.dx * LASER_LEN, b.y - b.dy * LASER_LEN
            c.create_line(tx, ty, b.x, b.y, fill="#ff2a6d", width=6, capstyle="round", tags="dyn")
            c.create_line(tx + b.dx, ty + b.dy, b.x - b.dx, b.y - b.dy, fill="#ffd6e4", width=2, capstyle="round", tags="dyn")
        for p in g.particles:
            s = 2.5 * max(0.3, p.life)
            c.create_oval(p.x - s, p.y - s, p.x + s, p.y + s, fill=p.color, outline="", tags="dyn")
        self._draw_ship()
        for pop in g.popups:
            c.create_text(pop.x, pop.y, text=pop.text, fill=pop.color, font=(FONT, 12, "bold"), tags="dyn")
        if g.flash > 0:
            c.create_rectangle(0, 0, W, H, fill="#ff2a2a", stipple="gray25", outline="", tags="dyn")
        self._draw_hud()

        if self.state == "paused":
            self._panel("PAUSED", ["P or Space to resume", "R to restart", "H how to play", "M sound on/off"])
        elif self.state == "over":
            lines = [
                f"Score  {g.score}",
                f"Stars caught  {g.caught}   Best combo  {g.best_combo}",
                f"Meteors blasted  {g.meteors_shot}",
            ]
            if g.new_high:
                lines.insert(0, "NEW HIGH SCORE!")
            lines.append("Space to play again    H how to play")
            self._panel("GAME OVER", lines)

    def _draw_thing(self, t) -> None:
        c = self.canvas
        if t.kind == "star":
            glow = t.r * 1.6
            c.create_oval(t.x - glow, t.y - glow, t.x + glow, t.y + glow, fill="#3a3410", outline="", tags="dyn")
            c.create_polygon(star_points(t.x, t.y, t.r, t.angle), fill="#ffe066", outline="#fff3b0", tags="dyn")
        elif t.kind == "meteor":
            c.create_polygon(rock_points(t.x, t.y, t.r, t.angle, t.seed), fill="#6b4e3d", outline="#a8785a", width=2, tags="dyn")
            c.create_oval(t.x - t.r * 0.3, t.y - t.r * 0.35, t.x + t.r * 0.05, t.y, fill="#523b2e", outline="", tags="dyn")
        else:
            color = {"heart": "#ff7aa8", "shield": "#7cf7ff", "slow": "#c49bff"}[t.kind]
            pulse = 1 + 0.12 * math.sin(time.perf_counter() * 8)
            r = t.r * pulse
            c.create_oval(t.x - r, t.y - r, t.x + r, t.y + r, outline=color, width=2, tags="dyn")
            if t.kind == "heart":
                c.create_text(t.x, t.y + 1, text="♥", fill=color, font=(FONT, 13, "bold"), tags="dyn")
            elif t.kind == "shield":
                hexa = [v for i in range(6) for v in (t.x + 7 * math.cos(i * math.pi / 3), t.y + 7 * math.sin(i * math.pi / 3))]
                c.create_polygon(hexa, fill="", outline=color, width=2, tags="dyn")
            else:
                c.create_line(t.x, t.y, t.x, t.y - 7, fill=color, width=2, tags="dyn")
                c.create_line(t.x, t.y, t.x + 5, t.y + 3, fill=color, width=2, tags="dyn")

    def _draw_ship(self, x: float | None = None, y: float | None = None, aim: float | None = None,
                   thrust: int | None = None, shield: float | None = None) -> None:
        """Draws the player's ship, or (for the guide's pictures) a ship wherever asked."""
        c, g = self.canvas, self.game
        x = g.ship_x if x is None else x
        y = g.ship_y if y is None else y
        aim = g.aim if aim is None else aim
        thrust = self.thrust if thrust is None else thrust
        shield = g.shield if shield is None else shield
        t = time.perf_counter()
        hull, trim, glow = "#c9d6e8", "#f2f7ff", "#5ad1ff"
        ca, sa = math.cos(aim), math.sin(aim)

        # The ship is drawn nose-up around (0, 0), then turned to face its aim.
        def pts(*local: tuple[float, float]) -> list[float]:
            out: list[float] = []
            for lx, ly in local:
                out += [x + lx * ca - ly * sa, y + lx * sa + ly * ca]
            return out

        def ellipse(cy: float, rx: float, ry: float, n: int = 20) -> list[float]:
            return pts(*[(rx * math.cos(i * math.tau / n), cy + ry * math.sin(i * math.tau / n)) for i in range(n)])

        def dot(lx: float, ly: float, r: float, fill: str, outline: str = "") -> None:
            px, py = pts((lx, ly))
            c.create_oval(px - r, py - r, px + r, py + r, fill=fill, outline=outline, tags="dyn")

        # Twin thrusters with flickering exhaust.
        for side in (-9, 9):
            boost = {1: 2.2, -1: 0.4}.get(thrust, 1.0)  # long flame forward, short in reverse
            flame = (5 + 5 * abs(math.sin(t * 30 + side))) * boost
            c.create_polygon(pts((side - 4, 11), (side + 4, 11), (side, 11 + flame)), fill="#ff9f43", outline="", tags="dyn")
            c.create_polygon(pts((side - 4, 5), (side + 4, 5), (side + 4, 12), (side - 4, 12)), fill="#7d8aa3", outline=trim, tags="dyn")

        # Swept fins with lit wingtips.
        for side in (-1, 1):
            c.create_polygon(pts((side * 10, -2), (side * 28, 9), (side * 24, 13), (side * 12, 6)), fill="#93a4bf", outline=trim, tags="dyn")
            dot(side * 25, 11, 3, glow if int(t * 3 + (side > 0)) % 2 else "#ff7aa8")

        # Saucer hull with a pointed prow.
        c.create_polygon(pts((-6, -9), (0, -23), (6, -9)), fill=hull, outline=trim, tags="dyn")
        c.create_polygon(ellipse(-2, 18, 11), fill=hull, outline=trim, width=2, tags="dyn")
        c.create_polygon(ellipse(-2, 12, 7), fill="", outline="#93a4bf", tags="dyn")
        # Ring of hull lights and the glowing bridge dome.
        for i in range(6):
            a = t * 2 + i * math.tau / 6
            dot(15 * math.cos(a), -2 + 8 * math.sin(a), 1.2, glow)
        dot(0, -3, 5, glow, trim)
        if shield > 0 and (shield > 1.5 or int(shield * 8) % 2 == 0):
            c.create_oval(x - 34, y - 34, x + 34, y + 34, outline="#7cf7ff", width=2, tags="dyn")

    def _draw_hud(self) -> None:
        c, g = self.canvas, self.game
        c.create_text(12, 12, anchor="nw", text=f"{g.score}", fill="white", font=(FONT, 20, "bold"), tags="dyn")
        c.create_text(12, 44, anchor="nw", text=f"Best {g.high_score}   Level {g.level}", fill="#9fb0ff", font=(FONT, 10), tags="dyn")
        if g.multiplier > 1:
            c.create_text(12, 62, anchor="nw", text=f"x{g.multiplier} combo", fill="#ffe066", font=(FONT, 11, "bold"), tags="dyn")
        c.create_text(W - 12, 14, anchor="ne", text="♥" * g.lives, fill="#ff7aa8", font=(FONT, 16), tags="dyn")
        bar_y = 44
        for left, total, color, label in ((g.shield, 6.0, "#7cf7ff", "shield"), (g.slow, 5.0, "#c49bff", "slow-mo")):
            if left > 0:
                c.create_text(W - 112, bar_y, anchor="ne", text=label, fill=color, font=(FONT, 9), tags="dyn")
                c.create_rectangle(W - 108, bar_y + 2, W - 12, bar_y + 10, outline=color, tags="dyn")
                c.create_rectangle(W - 108, bar_y + 2, W - 108 + 96 * left / total, bar_y + 10, fill=color, outline="", tags="dyn")
                bar_y += 16
        # Laser heat gauge, bottom left.
        if g.heat > 0 or g.overheated:
            color = "#ff4a4a" if g.overheated else ("#ff9f43" if g.heat > 0.7 else "#ff2a6d")
            label = "OVERHEAT" if g.overheated else "laser"
            c.create_text(12, H - 26, anchor="sw", text=label, fill=color, font=(FONT, 9, "bold" if g.overheated else "normal"), tags="dyn")
            c.create_rectangle(12, H - 22, 112, H - 14, outline=color, tags="dyn")
            c.create_rectangle(12, H - 22, 12 + 100 * g.heat, H - 14, fill=color, outline="", tags="dyn")
        if self.sounds.muted and not (self.demo or self.frame_limit):
            c.create_text(W - 12, H - 10, anchor="se", text="muted (M)", fill="#4a5a9a", font=(FONT, 9), tags="dyn")
        if self.demo:
            c.create_text(W / 2, H - 14, text="DEMO", fill="#4a5a9a", font=(FONT, 10, "bold"), tags="dyn")

    def _panel(self, title: str, lines: list[str]) -> None:
        c = self.canvas
        h = 90 + 26 * len(lines)
        top = H / 2 - h / 2
        c.create_rectangle(50, top, W - 50, top + h, fill="#141c3d", outline="#5ad1ff", width=2, tags="dyn")
        c.create_text(W / 2, top + 36, text=title, fill="white", font=(FONT, 24, "bold"), tags="dyn")
        for i, line in enumerate(lines):
            color = "#ffe066" if "HIGH" in line else "#d6f4ff"
            c.create_text(W / 2, top + 78 + 26 * i, text=line, fill=color, font=(FONT, 12), tags="dyn")

    # --- How to Play guide ------------------------------------------------------
    def _draw_guide(self) -> None:
        c = self.canvas
        page = PAGES[self.page]
        c.create_text(W / 2, 34, text="HOW TO PLAY", fill="#5ad1ff", font=(FONT, 11, "bold"), tags="dyn")
        c.create_text(W / 2, 70, text=page["title"], fill="white", font=(FONT, 24, "bold"), tags="dyn")
        # Picture area.
        c.create_rectangle(40, 104, W - 40, 300, fill="#10173a", outline="#26305e", tags="dyn")
        getattr(self, f"_art_{page['art']}")()
        for i, line in enumerate(page["lines"]):
            c.create_text(W / 2, 330 + 26 * i, text=line, fill="#d6f4ff", font=(FONT, 12), tags="dyn")
        # Page dots and hints.
        n = len(PAGES)
        for i in range(n):
            px = W / 2 + (i - (n - 1) / 2) * 18
            fill = "#ffe066" if i == self.page else "#2a3566"
            c.create_oval(px - 4, H - 66, px + 4, H - 58, fill=fill, outline="", tags="dyn")
        last = self.page == n - 1
        hint = "Space: start the game!" if last and self.guide_return != "paused" else (
            "Space: back to the game" if last else "Space or →: next page")
        c.create_text(W / 2, H - 38, text=hint, fill="#ffe066", font=(FONT, 12, "bold"), tags="dyn")
        c.create_text(W / 2, H - 16, text="← previous    Esc close", fill="#4a5a9a", font=(FONT, 10), tags="dyn")

    def _arrow(self, x0: float, y0: float, x1: float, y1: float, label: str = "", color: str = "#ffe066") -> None:
        c = self.canvas
        c.create_line(x0, y0, x1, y1, fill=color, width=3, arrow="last", arrowshape=(10, 12, 5), tags="dyn")
        if label:
            c.create_text(x1 + (x1 - x0) * 0.35, y1 + (y1 - y0) * 0.35, text=label, fill=color, font=(FONT, 11, "bold"), tags="dyn")

    def _art_mission(self) -> None:
        t = time.perf_counter()
        bob = 6 * math.sin(t * 2)
        for x, y in ((150, 160 + bob), (250, 140 - bob), (340, 175)):
            self._draw_thing(Thing("star", x, y, 0, 13, angle=t))
        self._draw_thing(Thing("meteor", 360, 240, 0, 18, angle=t * 0.5, seed=11))
        self._draw_ship(240, 250, 0.0, 1, 0)

    def _art_flying(self) -> None:
        t = time.perf_counter()
        aim = 0.7 * math.sin(t * 0.9)  # the ship slowly turns to show the controls turn with it
        x, y = 240, 205
        fx, fy = direction(aim)
        rx, ry = math.cos(aim), math.sin(aim)
        self._arrow(x + fx * 34, y + fy * 34, x + fx * 74, y + fy * 74, "W")
        self._arrow(x - fx * 30, y - fy * 30, x - fx * 66, y - fy * 66, "S", "#9fb0ff")
        self._arrow(x - rx * 38, y - ry * 38, x - rx * 78, y - ry * 78, "A", "#9fb0ff")
        self._arrow(x + rx * 38, y + ry * 38, x + rx * 78, y + ry * 78, "D", "#9fb0ff")
        self._draw_ship(x, y, aim, 1, 0)
        self.canvas.create_text(52, 288, anchor="sw", text="turns with the mouse or Q / E", fill="#4a5a9a", font=(FONT, 9), tags="dyn")

    def _art_laser(self) -> None:
        c = self.canvas
        t = time.perf_counter()
        aim = 0.55
        x, y = 150, 260
        dx, dy = direction(aim)
        for k in range(3):
            d = 40 + ((t * 260 + k * 70) % 210)
            bx, by = x + dx * d, y + dy * d
            c.create_line(bx - dx * LASER_LEN, by - dy * LASER_LEN, bx, by, fill="#ff2a6d", width=6, capstyle="round", tags="dyn")
            c.create_line(bx - dx * (LASER_LEN - 1), by - dy * (LASER_LEN - 1), bx - dx, by - dy, fill="#ffd6e4", width=2, capstyle="round", tags="dyn")
        self._draw_ship(x, y, aim, 0, 0)
        # A heat bar that fills and empties.
        heat = (math.sin(t * 1.2) + 1) / 2
        color = "#ff4a4a" if heat > 0.85 else ("#ff9f43" if heat > 0.6 else "#ff2a6d")
        c.create_text(W - 160, 268, anchor="sw", text="OVERHEAT" if heat > 0.85 else "heat", fill=color, font=(FONT, 9, "bold"), tags="dyn")
        c.create_rectangle(W - 160, 272, W - 60, 282, outline=color, tags="dyn")
        c.create_rectangle(W - 160, 272, W - 160 + 100 * heat, 282, fill=color, outline="", tags="dyn")

    def _art_meteors(self) -> None:
        c = self.canvas
        t = time.perf_counter()
        self._draw_thing(Thing("meteor", 130, 200, 0, 24, angle=t * 0.4, seed=5))
        c.create_text(130, 250, text="+15", fill="#ff9f43", font=(FONT, 12, "bold"), tags="dyn")
        self._arrow(185, 200, 250, 200)
        spread = 6 * math.sin(t * 2)
        for (fx, fy, s) in ((310, 160, 7), (360, 200, 3), (315, 245, 9)):
            self._draw_thing(Thing("meteor", fx + spread * 0.5, fy + spread * (fy - 200) / 40, 0, 12, angle=t * s * 0.2, seed=s))
        c.create_text(380, 270, text="+10 each", fill="#ff9f43", font=(FONT, 11, "bold"), tags="dyn")

    def _art_combo(self) -> None:
        c = self.canvas
        t = time.perf_counter()
        lit = int(t * 2) % 7  # stars light up one by one
        for i in range(5):
            x = 100 + i * 70
            self._draw_thing(Thing("star", x, 175, 0, 15 if i < lit else 11, angle=t if i < lit else 0))
            c.create_text(x, 210, text="+10", fill="#ffe066" if i < lit else "#4a5a9a", font=(FONT, 10), tags="dyn")
        done = lit >= 5
        c.create_text(W / 2, 258, text="combo ×2!" if done else "5 in a row…", fill="#ffe066" if done else "#9fb0ff",
                      font=(FONT, 18 if done else 13, "bold"), tags="dyn")

    def _art_powerups(self) -> None:
        c = self.canvas
        for x, kind, label, color in ((130, "heart", "extra life", "#ff7aa8"), (240, "shield", "shield", "#7cf7ff"), (350, "slow", "slow-mo", "#c49bff")):
            self._draw_thing(Thing(kind, x, 185, 0, 20))
            c.create_text(x, 235, text=label, fill=color, font=(FONT, 12, "bold"), tags="dyn")

    def _art_tips(self) -> None:
        t = time.perf_counter()
        self._draw_ship(200, 230, 0.4 * math.sin(t), 1, 6.0)
        self._draw_thing(Thing("meteor", 290, 160 + 10 * math.sin(t * 1.5), 0, 18, angle=t * 0.5, seed=9))
        self._draw_thing(Thing("star", 110, 150, 0, 13, angle=t))
        self.canvas.create_text(320, 250, text="shield up: ram it!", fill="#7cf7ff", font=(FONT, 11, "bold"), tags="dyn")

    def _draw_title(self) -> None:
        c = self.canvas
        t = time.perf_counter()
        for i in range(5):
            a = t * 0.8 + i * math.tau / 5
            c.create_polygon(star_points(W / 2 + 150 * math.cos(a), 200 + 40 * math.sin(a), 12, t * 2 + i), fill="#ffe066", outline="", tags="dyn")
        c.create_text(W / 2, 200, text="STAR SWEEP", fill="white", font=(FONT, 36, "bold"), tags="dyn")
        lines = [
            "Catch the falling stars. Dodge or blast the meteors:",
            "big ones break into fragments!",
            "",
            "W/S forward and back    A/D slide    mouse or Q/E turn",
            "Hold Space or the mouse button to fire",
            "Watch the heat: an overheated laser must cool down",
            "P pause    M sound",
            "",
            "♥ extra life    ⬡ shield    ◴ slow-mo",
        ]
        for i, line in enumerate(lines):
            c.create_text(W / 2, 278 + 22 * i, text=line, fill="#9fb0ff", font=(FONT, 11), tags="dyn")
        if int(t * 2) % 2 == 0:
            c.create_text(W / 2, 500, text="Press Space or click to start", fill="#ffe066", font=(FONT, 14, "bold"), tags="dyn")
        c.create_text(W / 2, 535, text="New here? Press H for How to Play", fill="#7cf7ff", font=(FONT, 11), tags="dyn")
        c.create_text(W / 2, 575, text=f"High score  {self.game.high_score}", fill="#5ad1ff", font=(FONT, 11), tags="dyn")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Star Sweep")
    ap.add_argument("--demo", action="store_true", help="watch the computer play")
    ap.add_argument("--smoke", type=int, metavar="FRAMES", help="test run: autopilot for N frames, then exit")
    ap.add_argument("--report", help="write a JSON summary here when the game exits")
    ap.add_argument("--seconds", type=float, help="close after this many seconds")
    args = ap.parse_args(argv)
    root = tk.Tk()
    App(root, demo=args.demo, frames=args.smoke, report=args.report, seconds=args.seconds)
    root.mainloop()


if __name__ == "__main__":
    main(sys.argv[1:])
