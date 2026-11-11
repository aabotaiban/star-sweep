import math
import unittest

from logic import (
    FIRE_COOLDOWN, FRAGMENT_SHOT_POINTS, H, METEOR_SHOT_POINTS, SHIP_R, SHIP_SPEED, SHIP_Y, W, Y_MIN,
    Game, Laser, Thing, autopilot, autopilot_aim, autopilot_fire, bearing, direction,
)

FAR = W - 2 * SHIP_R  # an x far from the ship's starting point


def drop(game: Game, kind: str) -> None:
    """Place a thing right on top of the ship so the next step catches it."""
    game.things.append(Thing(kind, game.ship_x, game.ship_y, 0.0, 13.0))


def run(game: Game, seconds: float, **kw) -> None:
    for _ in range(int(seconds * 60)):
        game.step(1 / 60, **kw)


class Rules(unittest.TestCase):
    def setUp(self) -> None:
        self.g = Game(seed=1)
        self.g.spawn_timer = 999  # no random spawns unless a test wants them

    def test_star_scores_and_builds_combo(self):
        for _ in range(5):
            drop(self.g, "star")
            self.g.step(0.01)
        self.assertEqual(self.g.score, 50)
        self.assertEqual(self.g.combo, 5)
        self.assertEqual(self.g.multiplier, 2)
        drop(self.g, "star")
        self.g.step(0.01)
        self.assertEqual(self.g.score, 70)  # the 6th star is worth 20

    def test_multiplier_caps_at_5(self):
        self.g.combo = 100
        self.assertEqual(self.g.multiplier, 5)

    def test_meteor_costs_a_life_and_the_combo(self):
        self.g.combo = 7
        drop(self.g, "meteor")
        self.g.step(0.01)
        self.assertEqual(self.g.lives, 2)
        self.assertEqual(self.g.combo, 0)
        self.assertIn("hit", self.g.events)

    def test_meteor_hits_from_any_side(self):
        self.g.ship_y = 300
        for dx, dy in ((0, -25), (25, 0), (0, 25), (-25, 0)):
            self.g.things.append(Thing("meteor", self.g.ship_x + dx, self.g.ship_y + dy, 0.0, 12))
        self.g.step(0.01)
        self.assertEqual(self.g.lives, 0)
        self.assertTrue(self.g.over)

    def test_shield_blocks_meteors(self):
        drop(self.g, "shield")
        self.g.step(0.01)
        self.assertGreater(self.g.shield, 0)
        drop(self.g, "meteor")
        self.g.step(0.01)
        self.assertEqual(self.g.lives, 3)
        self.assertEqual(self.g.score, 5)

    def test_shield_wears_off(self):
        self.g.shield = 0.5
        self.g.step(0.6)
        self.assertEqual(self.g.shield, 0)

    def test_heart_adds_a_life_up_to_five(self):
        self.g.lives = 5
        drop(self.g, "heart")
        self.g.step(0.01)
        self.assertEqual(self.g.lives, 5)
        self.g.lives = 2
        drop(self.g, "heart")
        self.g.step(0.01)
        self.assertEqual(self.g.lives, 3)

    def test_slow_mo_halves_falling_speed(self):
        self.g.things.append(Thing("star", FAR, 100, 100.0, 13))
        self.g.ship_x = SHIP_R
        self.g.slow = 3
        self.g.step(1.0)
        self.assertAlmostEqual(self.g.things[0].y, 150)

    def test_game_over_records_high_score(self):
        self.g.high_score = 10
        self.g.score = 40
        self.g.lives = 1
        drop(self.g, "meteor")
        self.g.step(0.01)
        self.assertTrue(self.g.over)
        self.assertEqual(self.g.high_score, 40)
        self.assertTrue(self.g.new_high)
        before = self.g.time
        self.g.step(1.0)  # nothing moves once it's over
        self.assertEqual(self.g.time, before)

    def test_hit_flash_fades_after_game_over(self):
        self.g.lives = 1
        drop(self.g, "meteor")
        self.g.step(0.01)
        self.assertGreater(self.g.flash, 0)
        self.g.step(1.0)
        self.assertEqual(self.g.flash, 0)

    def test_missed_star_breaks_the_combo(self):
        self.g.combo = 3
        self.g.things.append(Thing("star", FAR, H + 50, 10.0, 13))
        self.g.ship_x = SHIP_R
        self.g.step(0.01)
        self.assertEqual(self.g.combo, 0)
        self.assertEqual(self.g.things, [])

    def test_levels_speed_up_and_spawn_faster(self):
        start_interval = self.g.spawn_interval()
        self.g.time = 41
        self.assertEqual(self.g.level, 3)
        self.assertLess(self.g.spawn_interval(), start_interval)
        self.assertGreater(self.g.speed_scale, 1)

    def test_spawned_things_start_on_screen_horizontally(self):
        g = Game(seed=3)
        for _ in range(500):
            t = g.spawn()
            self.assertGreaterEqual(t.x - t.r, 0)
            self.assertLessEqual(t.x + t.r, W)

    def test_same_seed_same_game(self):
        a, b = Game(seed=42), Game(seed=42)
        for _ in range(600):
            a.step(1 / 60, move=0.3, firing=True, aim=0.4)
            b.step(1 / 60, move=0.3, firing=True, aim=0.4)
        self.assertEqual((a.score, a.lives, len(a.things)), (b.score, b.lives, len(b.things)))


class Flying(unittest.TestCase):
    def setUp(self) -> None:
        self.g = Game(seed=1)
        self.g.spawn_timer = 999

    def test_flies_in_all_four_directions(self):
        x, y = self.g.ship_x, self.g.ship_y
        self.g.step(0.1, move_y=-1)
        self.assertAlmostEqual(self.g.ship_y, y - SHIP_SPEED * 0.1)
        self.g.step(0.1, move=1)
        self.assertAlmostEqual(self.g.ship_x, x + SHIP_SPEED * 0.1)

    def test_diagonal_is_not_faster(self):
        x, y = self.g.ship_x, self.g.ship_y
        self.g.step(0.1, move=1, move_y=-1)
        self.assertAlmostEqual(math.hypot(self.g.ship_x - x, self.g.ship_y - y), SHIP_SPEED * 0.1)

    def test_ship_stays_on_screen_and_below_the_score(self):
        self.g.step(5.0, move=-1, move_y=-1)
        self.assertEqual((self.g.ship_x, self.g.ship_y), (SHIP_R, Y_MIN))
        self.g.step(5.0, move=1, move_y=1)
        self.assertEqual(self.g.ship_x, W - SHIP_R)
        self.assertLessEqual(self.g.ship_y + SHIP_R, H)

    def test_ship_turns_to_face_the_aim_gradually(self):
        self.g.step(0.01, aim=math.pi / 2)  # point right
        self.assertGreater(self.g.aim, 0)
        self.assertLess(self.g.aim, math.pi / 2)  # not there yet: turning takes time
        run(self.g, 0.5)
        self.assertAlmostEqual(self.g.aim, math.pi / 2, places=5)

    def test_turns_the_short_way_round(self):
        self.g.step(0.01, aim=-0.5)  # a little left of up
        self.assertGreater(self.g.aim, math.pi)  # wrapped, i.e. turned left, not all the way right

    def test_q_and_e_keys_rotate(self):
        run(self.g, 0.5, turn=1.0)
        self.assertGreater(self.g.aim, 1.0)

    def test_forward_follows_the_nose(self):
        from logic import ship_relative
        mx, my = ship_relative(1, 0, 0.0)  # facing up
        self.assertAlmostEqual((mx, my), (0, -1))
        mx, my = ship_relative(1, 0, math.pi / 2)  # facing right
        self.assertAlmostEqual(mx, 1)
        self.assertAlmostEqual(my, 0)
        mx, my = ship_relative(-1, 0, math.pi / 2)  # back while facing right
        self.assertAlmostEqual(mx, -1)
        mx, my = ship_relative(0, 1, math.pi / 2)  # slide right while facing right = down
        self.assertAlmostEqual(mx, 0)
        self.assertAlmostEqual(my, 1)

    def test_flying_forward_at_an_angle_moves_the_ship_that_way(self):
        from logic import ship_relative
        self.g.ship_y = 300
        self.g.aim = self.g.aim_target = math.pi / 4  # up and to the right
        x, y = self.g.ship_x, self.g.ship_y
        mx, my = ship_relative(1, 0, self.g.aim)
        self.g.step(0.1, move=mx, move_y=my)
        self.assertGreater(self.g.ship_x, x)
        self.assertLess(self.g.ship_y, y)
        self.assertAlmostEqual(math.hypot(self.g.ship_x - x, self.g.ship_y - y), SHIP_SPEED * 0.1)

    def test_bearing_and_direction_agree(self):
        for tx, ty in ((300, 100), (50, 600), (240, 10)):
            a = bearing(200, 300, tx, ty)
            dx, dy = direction(a)
            d = math.hypot(tx - 200, ty - 300)
            self.assertAlmostEqual(dx, (tx - 200) / d)
            self.assertAlmostEqual(dy, (ty - 300) / d)


class Lasers(unittest.TestCase):
    def setUp(self) -> None:
        self.g = Game(seed=1)
        self.g.spawn_timer = 999

    def shoot_once(self, **kw) -> None:
        self.g.step(0.01, firing=True, **kw)
        run(self.g, 1.0, **kw)

    def test_laser_destroys_a_small_meteor_and_scores(self):
        self.g.things.append(Thing("meteor", self.g.ship_x, 200, 0.0, 12))
        self.shoot_once()
        self.assertEqual(self.g.things, [])
        self.assertEqual(self.g.meteors_shot, 1)
        self.assertEqual(self.g.score, METEOR_SHOT_POINTS)
        self.assertEqual(self.g.lasers, [])

    def test_laser_fires_the_way_the_ship_faces(self):
        self.g.ship_y = 300
        self.g.aim = self.g.aim_target = math.pi / 2  # facing right
        self.g.things.append(Thing("meteor", W - 30, 300, 0.0, 12))
        self.g.things.append(Thing("meteor", self.g.ship_x, 120, 0.0, 12))  # straight up: not hit
        self.shoot_once(aim=math.pi / 2)
        self.assertEqual(self.g.meteors_shot, 1)
        self.assertEqual(self.g.things[0].y, 120)

    def test_laser_passes_through_stars_and_power_ups(self):
        for i, kind in enumerate(("star", "shield")):
            self.g.things.append(Thing(kind, self.g.ship_x, 150 + 100 * i, 0.0, 13))
        self.shoot_once()
        self.assertEqual(len(self.g.things), 2)
        self.assertEqual(self.g.score, 0)

    def test_laser_misses_a_meteor_off_to_the_side(self):
        self.g.things.append(Thing("meteor", self.g.ship_x + 60, 200, 0.0, 18))
        self.shoot_once()
        self.assertEqual(self.g.meteors_shot, 0)

    def test_fast_bolt_cannot_tunnel_through_a_small_meteor(self):
        self.g.things.append(Thing("meteor", self.g.ship_x, 300, 0.0, 10))
        self.g.lasers.append(Laser(self.g.ship_x, 300 + 10 + 5, 0.0, -1.0))
        self.g.step(1 / 30)
        self.assertEqual(self.g.meteors_shot, 1)

    def test_fire_rate_is_limited(self):
        shots = 0
        for _ in range(60):
            before = len(self.g.lasers)
            self.g.step(1 / 60, firing=True)
            shots += len(self.g.lasers) > before
        self.assertLessEqual(shots, int(1 / FIRE_COOLDOWN) + 1)
        self.assertGreaterEqual(shots, int(1 / FIRE_COOLDOWN) - 1)

    def test_overheat_locks_then_recovers(self):
        for _ in range(60 * 4):
            self.g.step(1 / 60, firing=True)
            if self.g.overheated:
                break
        self.assertTrue(self.g.overheated)
        self.assertFalse(self.g.fire())
        run(self.g, 3)
        self.assertFalse(self.g.overheated)
        self.assertTrue(self.g.fire())

    def test_no_firing_after_game_over(self):
        self.g.over = True
        self.assertFalse(self.g.fire())

    def test_lasers_leave_the_screen_in_any_direction(self):
        self.g.ship_y = 300
        for a in (0, math.pi / 2, math.pi, -math.pi / 2):
            self.g.aim = self.g.aim_target = a
            self.g.fire_cooldown = 0
            self.g.fire()
        run(self.g, 2)
        self.assertEqual(self.g.lasers, [])


class Fragments(unittest.TestCase):
    def setUp(self) -> None:
        self.g = Game(seed=1)
        self.g.spawn_timer = 999

    def hit(self, r: float) -> None:
        self.g.things.append(Thing("meteor", self.g.ship_x, 200, 0.0, r))
        self.g.lasers.append(Laser(self.g.ship_x, 200 + r, 0.0, -1.0))
        self.g.step(0.001)

    def test_big_meteor_breaks_into_three_fragments(self):
        self.hit(22)
        pieces = self.g.things
        self.assertEqual(len(pieces), 3)
        self.assertTrue(all(p.kind == "meteor" and p.fragment and p.r < 22 for p in pieces))
        self.assertIn("split", self.g.events)
        self.assertEqual(self.g.score, METEOR_SHOT_POINTS)

    def test_medium_meteor_breaks_into_two(self):
        self.hit(17)
        self.assertEqual(len(self.g.things), 2)

    def test_small_meteor_just_explodes(self):
        self.hit(13)
        self.assertEqual(self.g.things, [])
        self.assertIn("boom", self.g.events)

    def test_fragments_fly_apart_and_keep_falling(self):
        self.hit(22)
        xs = sorted(p.vx for p in self.g.things)
        self.assertLess(xs[0], 0)
        self.assertGreater(xs[-1], 0)
        self.assertTrue(all(p.vy > 0 for p in self.g.things))

    def test_fragments_do_not_split_again_and_score_less(self):
        self.hit(22)
        piece = self.g.things[0]
        self.g.things = [piece]
        self.g.lasers.append(Laser(piece.x, piece.y + piece.r, 0.0, -1.0))
        self.g.step(0.001)
        self.assertEqual(self.g.things, [])
        self.assertEqual(self.g.score, METEOR_SHOT_POINTS + FRAGMENT_SHOT_POINTS)

    def test_fragments_are_dangerous(self):
        self.hit(22)
        piece = self.g.things[0]
        piece.x, piece.y, piece.vx, piece.vy = self.g.ship_x, self.g.ship_y, 0, 0
        self.g.step(0.01)
        self.assertEqual(self.g.lives, 2)

    def test_fragments_leaving_the_sides_are_removed(self):
        self.g.things.append(Thing("meteor", W + 30, 300, 0.0, 10, vx=100, fragment=True))
        self.g.step(0.01)
        self.assertEqual(self.g.things, [])


class Autopilot(unittest.TestCase):
    def test_autopilot_aims_at_and_shoots_a_meteor(self):
        g = Game(seed=1)
        g.spawn_timer = 999
        g.things = [Thing("meteor", g.ship_x + 120, 250, 0.0, 14)]
        for _ in range(60):
            g.step(1 / 60, aim=autopilot_aim(g), firing=autopilot_fire(g))
        self.assertGreaterEqual(g.meteors_shot, 1)

    def test_autopilot_plays_reasonably(self):
        g = Game(seed=5)
        for _ in range(60 * 60):
            if g.over:
                break
            g.step(1 / 60, target_x=autopilot(g), target_y=SHIP_Y, aim=autopilot_aim(g), firing=autopilot_fire(g))
        self.assertGreater(g.caught, 20)
        self.assertGreater(g.meteors_shot, 5)


if __name__ == "__main__":
    unittest.main()
