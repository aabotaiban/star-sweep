"""Window tests: the How to Play guide draws and navigates. Needs a desktop session."""

import tkinter as tk
import unittest

import game
from guide import PAGES


class Guide(unittest.TestCase):
    def setUp(self) -> None:
        self._save = game.save_high_score
        game.save_high_score = lambda score: None  # tests never touch the real high score
        self.root = tk.Tk()
        self.app = game.App(self.root)
        self.app.sounds.muted = True

    def tearDown(self) -> None:
        game.save_high_score = self._save
        self.root.destroy()

    def test_every_page_draws(self):
        self.app.open_guide()
        for i in range(len(PAGES)):
            self.app.page = i
            self.app.draw()  # raises if a page's picture is broken
            texts = [self.app.canvas.itemcget(item, "text") for item in self.app.canvas.find_withtag("dyn")
                     if self.app.canvas.type(item) == "text"]
            self.assertIn(PAGES[i]["title"], texts)
            self.assertIn(PAGES[i]["lines"][0], texts)

    def test_pages_turn_both_ways_and_stop_at_the_ends(self):
        self.app.state = "title"
        self.app.on_key(None, "h")
        self.assertEqual(self.app.state, "guide")
        self.app.on_key(None, "left")
        self.assertEqual(self.app.page, 0)
        for _ in range(len(PAGES) + 3):
            self.app.on_key(None, "right")
        self.assertEqual(self.app.page, len(PAGES) - 1)
        self.app.on_key(None, "left")
        self.assertEqual(self.app.page, len(PAGES) - 2)

    def test_space_on_the_last_page_starts_a_game(self):
        self.app.state = "title"
        self.app.open_guide()
        for _ in range(len(PAGES) - 1):
            self.app.on_key(None, "space")
        self.assertEqual(self.app.state, "guide")
        self.app.on_key(None, "space")
        self.assertEqual(self.app.state, "playing")
        self.assertNotIn("space", self.app.keys)  # the start press doesn't fire the laser

    def test_escape_goes_back_where_you_came_from(self):
        self.app.state = "title"
        self.app.open_guide()
        self.app.on_key(None, "escape")
        self.assertEqual(self.app.state, "title")
        self.app.state = "paused"
        self.app.on_key(None, "h")
        self.assertEqual(self.app.state, "guide")
        self.app.on_key(None, "escape")
        self.assertEqual(self.app.state, "paused")

    def test_guide_from_pause_returns_to_the_paused_game(self):
        self.app.state = "paused"
        self.app.open_guide()
        self.app.page = len(PAGES) - 1
        self.app.on_key(None, "space")
        self.assertEqual(self.app.state, "paused")

    def test_every_screen_draws(self):
        for state in ("title", "playing", "paused", "over"):
            self.app.state = state
            self.app.draw()


if __name__ == "__main__":
    unittest.main()
