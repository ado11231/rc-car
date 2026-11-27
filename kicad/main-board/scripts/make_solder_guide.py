# Makes the main board soldering guide for Ibrahim: docs/guides/main-board-soldering.pdf
# Everything comes from design.py, so the guide always matches the KiCad board.
#
#   uv run --with matplotlib python kicad/main-board/scripts/make_solder_guide.py
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import matplotlib
matplotlib.use("agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, FancyBboxPatch
from matplotlib.backends.backend_pdf import PdfPages
from design import PARTS, WIRES, ROWS, rc, check

errors, *_ = check()
if errors:
    sys.exit("design.py has errors:\n" + "\n".join(errors))

OUT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..",
                                    "docs", "guides", "main-board-soldering.pdf"))
plt.rcParams["font.family"] = "Arial"
W, H = 215.9, 279.4                 # letter, upright, mm
PT = 72 / 25.4
INK = "#111111"
P = 8.6                             # drawing mm per hole


def page():
    fig = plt.figure(figsize=(W / 25.4, H / 25.4))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W); ax.set_ylim(0, H); ax.set_aspect("equal"); ax.axis("off")
    return fig, ax


def T(ax, x, y, s, size=4.0, ha="center", va="center", weight="bold", z=8, color=INK, rotation=0):
    ax.text(x, y, s, fontsize=size * PT, ha=ha, va=va, weight=weight, color=color, zorder=z, rotation=rotation)


# ---- wire numbers: one per run, in build order ---------------------------
NAMES = {"VBAT": "BATTERY +", "GND": "GROUND", "+5V": "5 V", "+3V3": "3.3 V", "BATT_SENSE": "BATTERY SENSE",
         "SERVO_SIG": "SERVO SIGNAL", "IN1": "IN1", "IN2": "IN2", "IN3": "IN3", "IN4": "IN4",
         "OUT1": "OUT1", "OUT2": "OUT2", "OUT3": "OUT3", "OUT4": "OUT4"}
RUNS = []                            # (number, net, side, holes)
for net in ["GND", "VBAT", "+5V", "+3V3", "BATT_SENSE", "SERVO_SIG", "IN1", "IN2", "IN3", "IN4",
            "OUT1", "OUT2", "OUT3", "OUT4"]:
    for side, holes in WIRES[net]:
        RUNS.append((len(RUNS) + 1, net, side, holes))


def corners(holes):
    """Only the holes where the wire turns, plus both ends."""
    out = [holes[0]]
    for a, b, c in zip(holes, holes[1:], holes[2:]):
        (r1, c1), (r2, c2), (r3, c3) = rc(a), rc(b), rc(c)
        if (r2 - r1, c2 - c1) != (r3 - r2, c3 - c2):
            out.append(b)
    out.append(holes[-1])
    return out


# ---- board map --------------------------------------------------------
class Board:
    """Perf board drawing. bottom=True mirrors it left-right (board flipped over)."""
    def __init__(self, ax, x0, y0, bottom=False):
        self.ax, self.x0, self.y0, self.bottom = ax, x0, y0, bottom

    def xy(self, hole_or_rc):
        r, c = rc(hole_or_rc) if isinstance(hole_or_rc, str) else hole_or_rc
        cc = (18 - c) if self.bottom else (c - 1)
        return self.x0 + cc * P, self.y0 + r * P

    def frame(self):
        ax = self.ax
        (xa, ya), (xb, yb) = self.xy((0, 1)), self.xy((23, 18))
        l, r = min(xa, xb) - P * 0.9, max(xa, xb) + P * 0.9
        ax.add_patch(Rectangle((l, ya - P * 0.9), r - l, yb - ya + P * 1.8, fill=False, ec=INK, lw=0.6 * PT, zorder=1))
        for rr in range(24):
            for c in range(1, 19):
                x, y = self.xy((rr, c))
                ax.add_patch(Circle((x, y), 0.55, fc="white", ec="#9a9a9a", lw=0.25 * PT, zorder=2))
        for rr in range(24):
            for x in (l - 3.2, r + 3.2):
                T(ax, x, self.xy((rr, 1))[1], ROWS[rr], 3.0, weight="normal")
        for c in range(1, 19):
            x = self.xy((0, c))[0]
            T(ax, x, ya - P * 0.9 - 3.4, str(c), 3.0, weight="normal")
            T(ax, x, yb + P * 0.9 + 3.4, str(c), 3.0, weight="normal")
        T(ax, (l + r) / 2, yb + P * 0.9 + 9.5, "FRONT", 4.2)
        T(ax, (l + r) / 2, ya - P * 0.9 - 9.5, "BACK", 4.2)
        return l, r

    def box(self, c1, c2, r1, r2, fill="white", lw=0.9, z=4, dashed=False):
        """part body between column c1..c2 and row index r1..r2 (fractions allowed)"""
        (xa, ya), (xb, yb) = self.xy((r1, c1)), self.xy((r2, c2))
        self.ax.add_patch(Rectangle((min(xa, xb), min(ya, yb)), abs(xb - xa), abs(yb - ya), fc=fill, ec=INK,
                                    lw=lw * PT, zorder=z, ls=(0, (3, 2)) if dashed else "-"))

    def pin(self, hole, z=6, fill=INK, r=1.25):
        x, y = self.xy(hole)
        self.ax.add_patch(Circle((x, y), r, fc=fill, ec=INK, lw=0.6 * PT, zorder=z))

    def at(self, r, c):
        return self.xy((r, c))


def R(letter):
    return ROWS.index(letter)


def draw_parts(b, labels=True, solid=True):
    """Part bodies + pins. On the bottom view the bodies are dashed (they are on the other side)."""
    fill = "white" if solid else "none"     # bottom view: see the wires under the parts
    dash = not solid
    lw = 0.9 if solid else 0.5
    # ESP32 sockets and module outline
    b.box(10.4, 18.6, R("Q") - 0.55, R("W") + 0.55, fill, lw, dashed=dash)
    # driver
    b.box(10.4, 16.6, R("H") - 0.55, R("N") + 0.55, fill, lw, dashed=dash)
    # Mini360
    b.box(2.6, 7.4, R("F") - 0.55, R("L") + 0.55, fill, lw, dashed=dash)
    # terminals (openings toward the back edge)
    for c1, c2 in ((1, 3), (10, 12), (14, 16)):
        b.box(c1 - 0.85, c2 + 0.85, R("B") - 1.75, R("B") + 1.7, fill, lw, dashed=dash)
    # capacitor
    x, y = b.at(R("P"), 2)
    b.ax.add_patch(Circle((x, y), P * 1.45, fc=fill, ec=INK, lw=lw * PT, zorder=4, ls=(0, (3, 2)) if dash else "-"))
    # resistors
    for ref in ("R1", "R2"):                 # straight from design.py
        (r1, c1), (r2, c2) = [rc(h) for _, h, _ in PARTS[ref][2]]
        if r1 == r2:                         # lies along a row
            b.box(min(c1, c2) + 0.5, max(c1, c2) - 0.5, r1 - 0.4, r1 + 0.4, fill, lw, dashed=dash)
        else:                                # lies along a column
            b.box(c1 - 0.4, c1 + 0.4, min(r1, r2) + 0.5, max(r1, r2) - 0.5, fill, lw, dashed=dash)
    # servo header: body at column 2, pins out past column 1
    b.box(1.55, 2.45, R("T") - 0.5, R("V") + 0.5, fill, lw, dashed=dash)
    for rr in "TUV":
        (xa, ya), (xb, yb) = b.at(R(rr), 2), b.at(R(rr), -0.6)
        b.ax.plot([xa, xb], [ya, yb], color=INK, lw=1.4 * PT, solid_capstyle="butt", zorder=5)
    for ref, (_, _, pins) in PARTS.items():
        for name, hole, net in pins:
            b.pin(hole, fill=INK if net else "white")


def top_labels(b):
    ax = b.ax
    def lab(r, c, s, size=4.0, **k):
        x, y = b.at(r, c); T(ax, x, y, s, size, **k)
    lab(R("T") + 0.5, 12.6, "ESP32   SOCKETS", 3.4)      # left of the 47k
    for pin, hole, _ in PARTS["U1B"][2]:
        r, c = rc(hole); lab(r + 0.75, c, pin, 2.1)     # outside the row: the 10k lies just inside
    step = {"G9": -0.5, "G8": -0.2}                     # G9 would sit on the 47k leg at R15
    for pin, hole, _ in PARTS["U1A"][2]:
        r, c = rc(hole); lab(r + 0.75, c + step.get(pin, 0), pin, 2.1)
    lab(R("K"), 13.5, "DRIVER", 5.0); lab(R("K") - 1.15, 13.5, "SOCKETS", 3.2, weight="normal")
    for pin, hole, _ in PARTS["U2A"][2]:
        r, c = rc(hole); lab(r - 0.75, c, pin, 2.1)
    for pin, hole, _ in PARTS["U2B"][2]:
        r, c = rc(hole); lab(r + 0.75, c, pin, 2.1)
    lab(R("I"), 5, "MINI360", 4.6)
    for pin, hole, _ in PARTS["U3"][2]:
        r, c = rc(hole); lab(r + (0.75 if r == R("F") else -0.75), c, pin, 2.6)
    lab(R("P"), 2, "470µF", 3.4)
    x, y = b.at(R("P"), 3); T(ax, x + 1.4, y + 2.6, "+", 4.2)
    x, y = b.at(R("P"), 1); T(ax, x - 1.4, y + 2.6, "−", 4.2)
    for ref in ("R1", "R2"):
        (r1, c1), (r2, c2) = [rc(h) for _, h, _ in PARTS[ref][2]]
        if r1 == r2:
            lab(r1, (c1 + c2) / 2, PARTS[ref][1], 3.0)
        else:
            lab((r1 + r2) / 2, c1, PARTS[ref][1], 3.0, rotation=90)
    lab(R("U"), 9.75, "USB", 2.8)
    for c, s in ((2, "BATTERY"), (11, "LEFT MOTOR"), (15, "RIGHT MOTOR")):
        lab(R("B") + 0.85, c, s, 3.6)
    x, y = b.at(R("B"), 1); T(ax, x, y - 4.2, "−", 4.6)
    x, y = b.at(R("B"), 3); T(ax, x, y - 4.2, "+", 4.6)
    lab(R("W") + 0.95, 2, "SERVO", 3.6)
    for rr, s in (("T", "GND"), ("U", "5V"), ("V", "SIG")):
        lab(R(rr), 3.25, s, 2.6, ha="left")


def draw_wires(b, numbers=True):
    ax = b.ax
    for n, net, side, holes in RUNS:
        pts = [b.xy(h) for h in corners(holes)]
        xs, ys = zip(*pts)
        if side == "bottom":
            ax.plot(xs, ys, color=INK, lw=1.5 * PT, solid_capstyle="round", solid_joinstyle="round", zorder=3)
        else:
            ax.plot(xs, ys, color=INK, lw=1.1 * PT, ls=(0, (2.5, 1.6)), zorder=3)
        if numbers:
            # number on the longest straight piece, away from the ends
            best = max(zip(pts, pts[1:]), key=lambda s: abs(s[1][0] - s[0][0]) + abs(s[1][1] - s[0][1]))
            (xa, ya), (xb, yb) = best
            x, y = (xa + xb) / 2, (ya + yb) / 2
            # snap to the gap between two holes so the tag never hides a joint
            if abs(xb - xa) > abs(yb - ya):
                x = b.x0 + (round((x - b.x0) / P - 0.5) + 0.5) * P
            else:
                y = b.y0 + (round((y - b.y0) / P - 0.5) + 0.5) * P
            ax.add_patch(Circle((x, y), 2.3, fc="white", ec=INK, lw=0.7 * PT, zorder=9))
            T(ax, x, y - 0.05, str(n), 2.7, z=10)


pdf = PdfPages(OUT)

# 1. Top: where the parts go ---------------------------------------------------
fig, ax = page()
b = Board(ax, (W - 17 * P) / 2 + 2, 42)
l, r = b.frame()
T(ax, l, H - 16, "TOP", 7, ha="left")
for n, net, side, holes in RUNS:           # the one top wire, dashed
    if side == "top":
        xs, ys = zip(*[b.xy(h) for h in corners(holes)])
        ax.plot(xs, ys, color=INK, lw=1.1 * PT, ls=(0, (2.5, 1.6)), zorder=7)
draw_parts(b)
top_labels(b)
for n_, net_, side_, holes_ in RUNS:
    if side_ == "top":
        row = "M" if len(holes_) < 6 else "R"          # short hop / long 3.3 V wire
        x, y = b.at(R(row), 8.55)
        T(ax, x, y, "INSULATED\nWIRE", 2.4, ha="right")
pdf.savefig(fig); plt.close(fig)

# 2. Bottom: wires --------------------------------------------------------------
fig, ax = page()
b = Board(ax, (W - 17 * P) / 2 - 2, 42, bottom=True)
l, r = b.frame()
T(ax, l, H - 16, "BOTTOM", 7, ha="left")
T(ax, l + 40, H - 16, "flipped over", 3.6, ha="left", weight="normal")
draw_parts(b, solid=False)
draw_wires(b, numbers=False)
pdf.savefig(fig); plt.close(fig)

# 3. What we need -------------------------------------------------------------
fig, ax = page()
NEED = ["2 × 8-pin female header", "2 × 6-pin female header", "Mini360",
        "470µF capacitor", "47k resistor", "10k resistor", "3-pin right-angle header",
        "3 × screw terminal", "Bare wire, about 50 cm", "Insulated wire, about 8 cm"]
y = H - 24
for s_ in NEED:
    if s_:
        T(ax, 24, y, "•", 4.2, ha="left")
        T(ax, 30, y, s_, 4.2, ha="left", weight="normal")
    y -= 9
pdf.savefig(fig); plt.close(fig)

pdf.close()
print("wrote", OUT)
