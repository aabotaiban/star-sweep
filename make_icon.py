"""Draws the Star Sweep icon (a yellow star on a night-blue tile) as icon.png and icon.ico."""

import math
import struct
import tkinter as tk

SIZE = 64


def inside(px: float, py: float, poly: list[tuple[float, float]]) -> bool:
    hit = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > py) != (yj > py) and px < (xj - xi) * (py - yi) / (yj - yi) + xi:
            hit = not hit
        j = i
    return hit


def main() -> None:
    root = tk.Tk()
    root.withdraw()
    img = tk.PhotoImage(width=SIZE, height=SIZE)
    c = SIZE / 2
    star = []
    for i in range(10):
        r = 27 if i % 2 == 0 else 12
        a = i * math.pi / 5 - math.pi / 2
        star.append((c + r * math.cos(a), c + 2 + r * math.sin(a)))
    rows = []
    for y in range(SIZE):
        row = []
        for x in range(SIZE):
            # Rounded tile corners stay transparent-looking dark.
            corner = min(x, SIZE - 1 - x) < 8 and min(y, SIZE - 1 - y) < 8 and math.hypot(
                min(x, SIZE - 1 - x) - 8, min(y, SIZE - 1 - y) - 8) > 8
            if corner:
                row.append("#000000")
            elif inside(x + 0.5, y + 0.5, star):
                row.append("#ffe066")
            else:
                row.append("#0b1026")
        rows.append("{" + " ".join(row) + "}")
    img.put(" ".join(rows))
    for x in range(SIZE):  # make the cut corners truly transparent
        for y in range(SIZE):
            if img.get(x, y) == (0, 0, 0):
                img.transparency_set(x, y, True)
    img.write("icon.png", format="png")
    root.destroy()

    png = open("icon.png", "rb").read()
    # An .ico file can hold a PNG directly: one header, one directory entry.
    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack("<BBBBHHII", SIZE, SIZE, 0, 0, 1, 32, len(png), 6 + 16)
    with open("icon.ico", "wb") as f:
        f.write(header + entry + png)
    print("wrote icon.png and icon.ico")


if __name__ == "__main__":
    main()
