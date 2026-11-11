"""The in-game How to Play guide: one entry per page.

Each page has a title, a picture (drawn by game.py from the `art` name) and a few short lines.
Keep lines under about 50 characters so they fit the window.
"""

PAGES = [
    {
        "title": "Your Mission",
        "art": "mission",
        "lines": [
            "Fly your saucer through a falling sky.",
            "Catch the yellow stars for points.",
            "Meteors cost a life, and you start with 3.",
            "Every 20 seconds the sky gets faster.",
            "How long can you last?",
        ],
    },
    {
        "title": "Flying",
        "art": "flying",
        "lines": [
            "W or ↑   fly forward, where the nose points",
            "S or ↓   fly backward",
            "A D or ← →   slide sideways",
            "",
            "Move the mouse and the ship turns to face it.",
            "No mouse? Turn with Q and E.",
        ],
    },
    {
        "title": "Your Laser",
        "art": "laser",
        "lines": [
            "Hold Space or the left mouse button to fire.",
            "Bolts fly the way your nose points.",
            "They pass through stars and power-ups,",
            "so you never shoot your own rewards.",
            "",
            "Watch the heat bar! About 3 seconds of",
            "non-stop fire overheats the laser and it",
            "locks until it cools. Shoot in bursts.",
        ],
    },
    {
        "title": "Meteors",
        "art": "meteors",
        "lines": [
            "Blast a meteor:  +15 points.",
            "Big meteors break into 2 or 3 fragments.",
            "Fragments fly apart and are still dangerous!",
            "Each fragment is worth +10 and won't split again.",
            "",
            "Shoot big rocks early, while they are far away,",
            "so the pieces have room to miss you.",
        ],
    },
    {
        "title": "Stars & Combos",
        "art": "combo",
        "lines": [
            "Every star is worth 10 × your combo.",
            "Every 5 stars in a row raise the combo by one,",
            "up to ×5: that's 50 points a star!",
            "",
            "Letting a star fall past you, or getting hit,",
            "resets the combo to ×1.",
        ],
    },
    {
        "title": "Power-ups",
        "art": "powerups",
        "lines": [
            "♥  Extra life (up to 5)",
            "⬡  Shield for 6 seconds: meteors bounce off,",
            "     and each one you ram gives +5",
            "◴  Slow-mo for 5 seconds: the sky falls at half",
            "     speed, but your ship and laser don't",
            "",
            "Fly into a power-up to collect it.",
        ],
    },
    {
        "title": "Tips",
        "art": "tips",
        "lines": [
            "Stay low: you see trouble coming sooner.",
            "Turn to shoot meteors that drift toward you.",
            "With a shield up, ram meteors for points.",
            "A long flame means you're thrusting forward.",
            "P pauses the game.  M turns sound on and off.",
            "",
            "Ready? Press Space to start!",
        ],
    },
]
