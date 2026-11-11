"""Star Sweep game rules: pure Python, no window code, so it can be tested.

Angles: 0 points straight up, positive turns clockwise (screen coordinates, y down).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

W, H = 480, 640
SHIP_Y = H - 60  # where the ship starts
SHIP_R = 20.0  # the ship's hit circle
SHIP_SPEED = 380.0
Y_MIN = 110  # keeps the ship below the score display
MAX_LIVES = 5
SHIELD_TIME = 6.0
SLOW_TIME = 5.0
LEVEL_SECONDS = 20.0

TURN_SPEED = 9.0  # how fast the ship swings to face the aim, radians per second
KEY_TURN_SPEED = 3.5  # Q/E turning, radians per second
NOSE = 22.0  # distance from the ship's centre to its prow

LASER_SPEED = 760.0
LASER_LEN = 16.0
FIRE_COOLDOWN = 0.2  # seconds between shots
HEAT_PER_SHOT = 0.14  # 0..1; reaching 1 overheats the cannon (about 3 s of held fire)
COOL_RATE = 0.35  # heat lost per second
OVERHEAT_RESUME = 0.3  # an overheated cannon fires again once heat is below this

METEOR_SHOT_POINTS = 15
FRAGMENT_SHOT_POINTS = 10
SPLIT_MIN_R = 15.0  # meteors at least this big break apart when shot
FRAGMENT_SCALE = 0.55


def direction(angle: float) -> tuple[float, float]:
    return math.sin(angle), -math.cos(angle)


def ship_relative(forward: float, strafe: float, angle: float) -> tuple[float, float]:
    """Turn ship controls (forward/back, slide right/left) into screen x/y movement."""
    fx, fy = direction(angle)
    rx, ry = math.cos(angle), math.sin(angle)  # the ship's right-hand side
    return forward * fx + strafe * rx, forward * fy + strafe * ry


def bearing(fx: float, fy: float, tx: float, ty: float) -> float:
    """The angle from (fx, fy) toward (tx, ty)."""
    return math.atan2(tx - fx, -(ty - fy))


def angle_diff(a: float, b: float) -> float:
    """Signed shortest turn from a to b, in -pi..pi."""
    return (b - a + math.pi) % math.tau - math.pi


def seg_dist(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    """Distance from point p to the segment a-b."""
    vx, vy = bx - ax, by - ay
    L = vx * vx + vy * vy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / L))
    return math.hypot(px - (ax + t * vx), py - (ay + t * vy))


@dataclass
class Thing:
    kind: str  # star | meteor | heart | shield | slow
    x: float
    y: float
    vy: float
    r: float
    spin: float = 0.0
    angle: float = 0.0
    seed: int = 0
    vx: float = 0.0
    fragment: bool = False  # a piece of a meteor that was shot


@dataclass
class Laser:
    x: float  # the tip of the bolt
    y: float
    dx: float  # unit direction of travel
    dy: float


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    color: str


@dataclass
class Popup:
    x: float
    y: float
    text: str
    life: float = 0.9
    color: str = "#ffe066"


@dataclass
class Game:
    seed: int | None = None
    high_score: int = 0
    rng: random.Random = field(init=False)

    def __post_init__(self) -> None:
        self.rng = random.Random(self.seed)
        self.reset()

    def reset(self) -> None:
        self.ship_x = W / 2
        self.ship_y = float(SHIP_Y)
        self.aim = 0.0  # where the ship faces
        self.aim_target = 0.0  # where it is turning to
        self.lives = 3
        self.score = 0
        self.combo = 0
        self.best_combo = 0
        self.caught = 0
        self.time = 0.0
        self.things: list[Thing] = []
        self.particles: list[Particle] = []
        self.popups: list[Popup] = []
        self.spawn_timer = 0.6
        self.shield = 0.0
        self.slow = 0.0
        self.flash = 0.0
        self.over = False
        self.new_high = False
        self.lasers: list[Laser] = []
        self.fire_cooldown = 0.0
        self.heat = 0.0
        self.overheated = False
        self.meteors_shot = 0
        self.events: list[str] = []  # sounds for the window to play

    # --- derived values -------------------------------------------------
    @property
    def level(self) -> int:
        return 1 + int(self.time // LEVEL_SECONDS)

    @property
    def multiplier(self) -> int:
        return 1 + min(self.combo // 5, 4)

    @property
    def speed_scale(self) -> float:
        return 1.0 + 0.09 * (self.level - 1)

    def spawn_interval(self) -> float:
        return max(0.26, 0.85 - 0.055 * (self.level - 1))

    def nose(self) -> tuple[float, float]:
        dx, dy = direction(self.aim)
        return self.ship_x + dx * NOSE, self.ship_y + dy * NOSE

    # --- the laser ------------------------------------------------------
    def can_fire(self) -> bool:
        return not self.over and not self.overheated and self.fire_cooldown <= 0

    def fire(self) -> bool:
        """Shoot one bolt from the ship's prow, the way the ship faces, if the cannon is ready."""
        if not self.can_fire():
            return False
        dx, dy = direction(self.aim)
        x, y = self.nose()
        self.lasers.append(Laser(x + dx * LASER_LEN, y + dy * LASER_LEN, dx, dy))
        self.fire_cooldown = FIRE_COOLDOWN
        self.heat = min(1.0, self.heat + HEAT_PER_SHOT)
        if self.heat >= 1.0:
            self.overheated = True
            self.events.append("overheat")
        else:
            self.events.append("laser")
        return True

    # --- the step -------------------------------------------------------
    def step(
        self,
        dt: float,
        move: float = 0.0,
        move_y: float = 0.0,
        target_x: float | None = None,
        target_y: float | None = None,
        firing: bool = False,
        aim: float | None = None,
        turn: float = 0.0,
    ) -> None:
        """Advance the game by dt seconds.

        move, move_y: -1..1 from the keys. target_x/target_y: fly toward a point instead.
        aim: an angle to face (from the mouse); turn: -1..1 to rotate (Q/E keys).
        firing: whether the fire button is held.
        """
        self._update_effects(dt)
        if self.over:
            return

        before_level = self.level
        self.time += dt
        if self.level > before_level:
            self.events.append("level")
            self.popups.append(Popup(W / 2, H / 2 - 40, f"LEVEL {self.level}", 1.4, "#7cf7ff"))

        world_dt = dt * (0.5 if self.slow > 0 else 1.0)
        self.shield = max(0.0, self.shield - dt)
        self.slow = max(0.0, self.slow - dt)

        self._move_ship(dt, move, move_y, target_x, target_y)

        # Turning: swing toward the aim at a limited speed, so the turn is visible.
        if aim is not None:
            self.aim_target = aim
        self.aim_target += max(-1.0, min(1.0, turn)) * KEY_TURN_SPEED * dt
        gap = angle_diff(self.aim, self.aim_target)
        limit = TURN_SPEED * dt
        self.aim = (self.aim + max(-limit, min(limit, gap))) % math.tau

        # Laser cannon: cool down, fire, move bolts (lasers ignore slow-mo).
        self.fire_cooldown = max(0.0, self.fire_cooldown - dt)
        self.heat = max(0.0, self.heat - COOL_RATE * dt)
        if self.overheated and self.heat < OVERHEAT_RESUME:
            self.overheated = False
        if firing:
            self.fire()
        for b in self.lasers:
            b.x += b.dx * LASER_SPEED * dt
            b.y += b.dy * LASER_SPEED * dt

        # Spawning
        self.spawn_timer -= world_dt
        while self.spawn_timer <= 0:
            self.spawn()
            self.spawn_timer += self.spawn_interval() * self.rng.uniform(0.7, 1.3)

        # Falling things
        kept: list[Thing] = []
        for t in self.things:
            t.x += t.vx * world_dt
            t.y += t.vy * world_dt
            t.angle += t.spin * world_dt
            if self._hits_ship(t):
                self._catch(t)
                continue
            if t.y - t.r > H:
                if t.kind == "star" and self.combo > 0:
                    self.combo = 0
                    self.events.append("miss")
                continue
            if t.x + t.r < 0 or t.x - t.r > W:
                continue
            kept.append(t)
        self.things = kept
        self._laser_hits(dt)

    def _move_ship(self, dt: float, mx: float, my: float, tx: float | None, ty: float | None) -> None:
        if tx is not None or ty is not None:
            gx = (tx if tx is not None else self.ship_x) - self.ship_x
            gy = (ty if ty is not None else self.ship_y) - self.ship_y
            d = math.hypot(gx, gy)
            step = SHIP_SPEED * dt
            if d > step:
                gx, gy = gx / d * step, gy / d * step
            self.ship_x += gx
            self.ship_y += gy
        else:
            mx, my = max(-1.0, min(1.0, mx)), max(-1.0, min(1.0, my))
            n = math.hypot(mx, my)
            if n > 1:  # diagonals aren't faster
                mx, my = mx / n, my / n
            self.ship_x += mx * SHIP_SPEED * dt
            self.ship_y += my * SHIP_SPEED * dt
        self.ship_x = max(SHIP_R, min(W - SHIP_R, self.ship_x))
        self.ship_y = max(Y_MIN, min(H - SHIP_R - 6, self.ship_y))

    def _laser_hits(self, dt: float) -> None:
        live: list[Laser] = []
        travel = LASER_SPEED * dt
        for b in self.lasers:
            if b.x < -LASER_LEN or b.x > W + LASER_LEN or b.y < -LASER_LEN or b.y > H + LASER_LEN:
                continue
            # The stretch this bolt swept this step, so a fast bolt can't skip past a rock.
            tail_x = b.x - b.dx * (LASER_LEN + travel)
            tail_y = b.y - b.dy * (LASER_LEN + travel)
            target = next(
                (
                    t for t in self.things
                    if t.kind == "meteor" and seg_dist(t.x, t.y, tail_x, tail_y, b.x, b.y) <= t.r
                ),
                None,
            )
            if target is None:
                live.append(b)
                continue
            # Stars and power-ups are never hit: bolts pass through them.
            self._blast(target, b)
        self.lasers = live

    def _blast(self, t: Thing, bolt: Laser) -> None:
        self.things.remove(t)
        self.meteors_shot += 1
        pts = FRAGMENT_SHOT_POINTS if t.fragment else METEOR_SHOT_POINTS
        self.score += pts
        self.popups.append(Popup(t.x, t.y - 10, f"+{pts}", color="#ff9f43"))
        self._burst(t.x, t.y, "#ff9f43", 14)
        self._burst(t.x, t.y, "#a8785a", 8)
        if t.r >= SPLIT_MIN_R and not t.fragment:
            pieces = 3 if t.r >= 21 else 2
            # Pieces fly out sideways from the bolt's line, fanned across 180 degrees.
            base = math.atan2(bolt.dy, bolt.dx) + math.pi / 2
            for i in range(pieces):
                a = base + math.pi * (i / (pieces - 1)) + self.rng.uniform(-0.25, 0.25)
                speed = self.rng.uniform(90, 160)
                r = max(8.0, t.r * FRAGMENT_SCALE)
                self.things.append(Thing(
                    kind="meteor",
                    x=t.x + math.cos(a) * r,
                    y=t.y + math.sin(a) * r,
                    vx=math.cos(a) * speed,
                    vy=max(60.0, t.vy * 0.8 + math.sin(a) * speed * 0.5),  # still falling
                    r=r,
                    spin=self.rng.uniform(-5, 5),
                    seed=self.rng.randrange(1 << 30),
                    fragment=True,
                ))
            self.events.append("split")
        else:
            self.events.append("boom")

    def _update_effects(self, dt: float) -> None:
        # Runs even after game over or while paused, so effects always finish.
        self.flash = max(0.0, self.flash - dt)
        for p in self.particles:
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.vy += 300 * dt
            p.life -= dt
        self.particles = [p for p in self.particles if p.life > 0]
        for pop in self.popups:
            pop.y -= 40 * dt
            pop.life -= dt
        self.popups = [p for p in self.popups if p.life > 0]

    def spawn(self) -> Thing:
        rng = self.rng
        roll = rng.random()
        meteor_chance = min(0.25 + 0.045 * (self.level - 1), 0.55)
        if roll < 0.06:
            kinds = ["shield", "slow"] + (["heart"] if self.lives < MAX_LIVES else [])
            kind = rng.choice(kinds)
        elif roll < 0.06 + meteor_chance:
            kind = "meteor"
        else:
            kind = "star"
        r = rng.uniform(14, 24) if kind == "meteor" else 13.0
        vy = 150 * self.speed_scale * rng.uniform(0.85, 1.25) * (1.1 if kind == "meteor" else 1.0)
        t = Thing(
            kind=kind,
            x=rng.uniform(r + 8, W - r - 8),
            y=-r,
            vy=vy,
            r=r,
            spin=rng.uniform(-3, 3) if kind in ("meteor", "star") else 0.0,
            seed=rng.randrange(1 << 30),
        )
        self.things.append(t)
        return t

    def _hits_ship(self, t: Thing) -> bool:
        return math.hypot(t.x - self.ship_x, t.y - self.ship_y) <= SHIP_R + t.r * 0.8

    def _burst(self, x: float, y: float, color: str, n: int = 14) -> None:
        for _ in range(n):
            a = self.rng.uniform(0, math.tau)
            s = self.rng.uniform(60, 220)
            self.particles.append(Particle(x, y, math.cos(a) * s, math.sin(a) * s - 80, self.rng.uniform(0.35, 0.8), color))

    def _catch(self, t: Thing) -> None:
        if self.over:  # several hits in one instant: nothing counts after the last life
            return
        if t.kind == "star":
            pts = 10 * self.multiplier  # scored at the combo reached before this star
            self.combo += 1
            self.best_combo = max(self.best_combo, self.combo)
            self.caught += 1
            self.score += pts
            self.popups.append(Popup(t.x, t.y - 10, f"+{pts}"))
            self._burst(t.x, t.y, "#ffe066")
            self.events.append("star")
        elif t.kind == "meteor":
            if self.shield > 0:
                self.score += 5
                self.popups.append(Popup(t.x, t.y - 10, "+5", color="#7cf7ff"))
                self._burst(t.x, t.y, "#7cf7ff", 20)
                self.events.append("shieldhit")
                return
            self.lives -= 1
            self.combo = 0
            self.flash = 0.35
            self._burst(t.x, t.y, "#ff6b4a", 24)
            if self.lives <= 0:
                self.over = True
                if self.score > self.high_score:
                    self.high_score = self.score
                    self.new_high = True
                self.events.append("gameover")
            else:
                self.events.append("hit")
        else:
            if t.kind == "heart":
                self.lives = min(MAX_LIVES, self.lives + 1)
                label, color = "+1 LIFE", "#ff7aa8"
            elif t.kind == "shield":
                self.shield = SHIELD_TIME
                label, color = "SHIELD", "#7cf7ff"
            else:
                self.slow = SLOW_TIME
                label, color = "SLOW-MO", "#c49bff"
            self.popups.append(Popup(t.x, t.y - 10, label, 1.1, color))
            self._burst(t.x, t.y, color)
            self.events.append("power")


# --- the computer player, for demo mode and the smoke test ------------------

def _threat(game: Game) -> Thing | None:
    """The meteor most worth shooting: the closest one ahead of the ship."""
    meteors = [t for t in game.things if t.kind == "meteor" and t.y < game.ship_y - 30]
    if not meteors:
        return None
    return min(meteors, key=lambda t: math.hypot(t.x - game.ship_x, t.y - game.ship_y))


def autopilot_aim(game: Game) -> float:
    t = _threat(game)
    return 0.0 if t is None else bearing(game.ship_x, game.ship_y, t.x, t.y)


def autopilot_fire(game: Game) -> bool:
    """Shoot when the ship points at a meteor, keeping the cannon from overheating."""
    if game.heat > 0.75:
        return False
    dx, dy = direction(game.aim)
    nx, ny = game.nose()
    return any(
        t.kind == "meteor"
        and seg_dist(t.x, t.y, nx, ny, nx + dx * 600, ny + dy * 600) <= t.r
        for t in game.things
    )


def autopilot(game: Game) -> float:
    """Where to fly along the bottom row: under the next star, away from meteors. Returns x."""
    sy = game.ship_y
    danger = [t for t in game.things if t.kind == "meteor" and sy - 220 < t.y < sy + 10]
    goals = [t for t in game.things if t.kind != "meteor" and t.y < sy]
    target = game.ship_x
    if goals:
        target = max(goals, key=lambda t: t.y).x

    def blocked(x: float) -> bool:
        return any(abs(m.x - x) < m.r + SHIP_R + 10 for m in danger)

    if blocked(target):
        for off in range(20, W, 20):
            for cand in (target - off, target + off):
                if SHIP_R <= cand <= W - SHIP_R and not blocked(cand):
                    return cand
    return target
