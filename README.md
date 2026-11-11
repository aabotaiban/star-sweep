# Star Sweep

A small arcade game for Windows. Fly your saucer anywhere, catch falling stars, and dodge or
blast meteors. Big meteors break into fragments when shot. The game speeds up every 20 seconds.

Made for [GitHub Game Off 2026](https://itch.io/jam/game-off-2026). Built with the help of an
AI assistant (Claude), which wrote the code, drew the artwork in code and synthesized the sounds.

**Play:** download the Windows build from the game's itch.io page, unzip it and double-click
`StarSweep.exe`. Nothing to install. Or build it yourself from this source (see below); the
finished game is then `dist\StarSweep.exe`.

**Learn:** the first time you start the game it opens the **How to Play** guide: 7 short pages
with pictures. Open it again any time with **H** on the title screen, the pause menu or after a game.

## Controls

| Key | Action |
| --- | --- |
| W / ↑ and S / ↓ | fly forward (where the nose points) and backward |
| A D / ← → | slide sideways |
| Mouse, or Q / E | turn: the ship faces the pointer, or rotates with Q/E |
| H | How to Play guide |
| Space or left mouse button (hold) | fire the laser the way the ship faces |
| Space, Enter or click | start / play again |
| P or Esc | pause |
| R | restart (when paused or after game over) |
| M | sound on/off |

## Scoring

- Star: 10 points × your combo multiplier.
- Every 5 stars in a row raises the multiplier, up to ×5. Missing a star or hitting a meteor resets it.
- Laser: a meteor is worth 15, a fragment 10. Meteors at least medium-sized split into 2 or 3
  fragments that fly apart and are still dangerous. Stars and power-ups are never hit.
- The laser heats up as you fire. Hold the trigger for about 3 seconds and it overheats,
  locking until it cools down.
- Power-ups: ♥ extra life (max 5), ⬡ shield for 6 s (meteors bounce off for +5), ◴ slow-mo for 5 s.
- Your best score is saved in `%APPDATA%\StarSweep\highscore.json`.

## For developers

Needs Python 3.12 (with tkinter). Using uv:

```
uv run --python 3.12 --no-project python game.py            # play from source
uv run --python 3.12 --no-project python game.py --demo     # watch the computer play
uv run --python 3.12 --no-project python -m unittest test_logic test_app
uv run --python 3.12 --no-project --with pyinstaller pyinstaller --noconfirm --onefile --windowed --name StarSweep --icon icon.ico --add-data "icon.png;." game.py
```

- `logic.py`: the game rules, no window code (tested by `test_logic.py`)
- `game.py`: the window, drawing, input and high score
- `guide.py`: the How to Play pages' text (edit here; the pictures are in `game.py`)
- `sounds.py`: sound effects, synthesized at startup
- `make_icon.py`: draws `icon.png` / `icon.ico`
