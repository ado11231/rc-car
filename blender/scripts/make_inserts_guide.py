# Makes the brass inserts guide for the solderer: docs/guides/brass-inserts.pdf
# Black and white, pictures + short bold labels, no lines from labels to parts.
#
#   1) Blender --background blender/rc_car.blend --python blender/scripts/render_inserts.py -- IMG_DIR
#   2) uv run --with matplotlib python blender/scripts/make_inserts_guide.py IMG_DIR
#
# Pages: 1 plate, 2 servo box, 3 beam. Insert holes ringed.
import os, sys, json
import matplotlib
matplotlib.use("agg")
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.patches import Polygon, Rectangle, FancyArrow, Circle
from matplotlib.backends.backend_pdf import PdfPages

IMG = sys.argv[1]
OUT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "docs", "guides", "brass-inserts.pdf"))
os.makedirs(os.path.dirname(OUT), exist_ok=True)
plt.rcParams["font.family"] = "Arial"
plt.rcParams["hatch.linewidth"] = 0.6
W, H = 279.4, 215.9            # letter, sideways, mm
PT = 72 / 25.4
INK = "#111111"


class Page:
    def __init__(self, num, title):
        self.fig = plt.figure(figsize=(W / 25.4, H / 25.4))
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set_xlim(0, W); self.ax.set_ylim(0, H); self.ax.set_aspect("equal"); self.ax.axis("off")
        if num:
            self.label(14, H - 20, f"{num}", 9, ha="left")
            self.label(30, H - 20, title, 9, ha="left")
        else:
            self.label(14, H - 24, title, 14, ha="left")

    def label(self, x, y, s, size=5.0, ha="center", va="baseline", weight="bold"):
        self.ax.text(x, y, s, fontsize=size * PT, ha=ha, va=va, weight=weight, color=INK)

    def small(self, x, y, s, size=3.6, ha="center"):
        self.label(x, y, s, size, ha, weight="normal")

    def image(self, name, cx, cy, h=None, w=None):
        im = mpimg.imread(os.path.join(IMG, name + ".png"))
        r = im.shape[1] / im.shape[0]
        if w is None: w = h * r
        if h is None: h = w / r
        self.ax.imshow(im, extent=(cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2), interpolation="antialiased", zorder=2)
        self.ext = {name: (cx - w / 2, cy - h / 2, w, h)}
        self.ext_all = getattr(self, "ext_all", {}); self.ext_all.update(self.ext)
        return w, h

    def hole(self, name, i):
        """page position of insert hole i in picture `name`"""
        x0, y0, w, h = self.ext_all[name]
        u, v = json.load(open(os.path.join(IMG, name + ".json")))[i]
        return x0 + u * w, y0 + v * h

    def rings(self, name, idx, r=5.0):
        """insert spot: black hole (from the render) inside a thick ring"""
        for i in idx:
            x, y = self.hole(name, i)
            self.ax.add_patch(Circle((x, y), r, fill=False, ec="white", lw=3.6 * PT, zorder=6))
            self.ax.add_patch(Circle((x, y), r, fill=False, ec=INK, lw=1.8 * PT, zorder=7))

    def poly(self, pts, fill="white", lw=0.5, hatch=None, z=3):
        self.ax.add_patch(Polygon(pts, closed=True, fc=fill, ec=INK, lw=lw * PT, hatch=hatch, zorder=z))

    def line(self, pts, lw=0.5, z=4):
        xs, ys = zip(*pts)
        self.ax.plot(xs, ys, color=INK, lw=lw * PT, solid_capstyle="round", zorder=z)

    def arrow(self, x, y, dx, dy):
        self.ax.add_patch(FancyArrow(x, y, dx, dy, width=1.2, head_width=5, head_length=5, length_includes_head=True,
                                     fc=INK, ec=INK, zorder=6))

    def save(self, pdf):
        pdf.savefig(self.fig); plt.close(self.fig)


# Small side-cut drawings (all sizes in page mm)
HW, IW, IH = 16.0, 20.0, 15.0        # hole width, insert width, insert height


def part_cut(p, cx, top, w=74, h=30):
    """the printed part cut in half, with the insert hole in the middle (hatched plastic)"""
    l, r = cx - w / 2, cx + w / 2
    p.poly([(l, top - h), (cx - HW / 2, top - h), (cx - HW / 2, top), (l, top)], hatch="////")
    p.poly([(cx + HW / 2, top - h), (r, top - h), (r, top), (cx + HW / 2, top)], hatch="////")
    p.poly([(cx - HW / 2, top - h), (cx + HW / 2, top - h), (cx + HW / 2, top - h + 0.01), (cx - HW / 2, top - h + 0.01)])


def insert(p, cx, bottom, tilt=0.0):
    """brass insert seen from the side: knurled sides, hole down the middle (dashed)"""
    import math
    a = math.radians(tilt)
    def T(x, y):
        x, y = x - cx, y - bottom
        return (cx + x * math.cos(a) - y * math.sin(a), bottom + x * math.sin(a) + y * math.cos(a))
    zig = 6
    left = [T(cx - IW / 2 + (1.4 if k % 2 else 0), bottom + IH * k / zig) for k in range(zig + 1)]
    right = [T(cx + IW / 2 - (1.4 if k % 2 else 0), bottom + IH * k / zig) for k in range(zig, -1, -1)]
    p.poly(left + right, fill="white", lw=0.6, z=5)
    for k in range(1, zig):
        y = bottom + IH * k / zig
        p.line([T(cx - IW / 2 + (1.4 if k % 2 else 0), y), T(cx + IW / 2 - (1.4 if k % 2 else 0), y)], lw=0.3, z=5)
    p.ax.plot(*zip(T(cx - 3, bottom), T(cx - 3, bottom + IH)), color=INK, lw=0.35 * PT, ls=(0, (2, 1.5)), zorder=6)
    p.ax.plot(*zip(T(cx + 3, bottom), T(cx + 3, bottom + IH)), color=INK, lw=0.35 * PT, ls=(0, (2, 1.5)), zorder=6)


def iron(p, cx, tip_y, length=62):
    """soldering iron straight up: pointed tip, metal shaft, fat handle"""
    p.poly([(cx, tip_y), (cx - 3, tip_y + 6), (cx + 3, tip_y + 6)], fill="white", z=7)
    p.poly([(cx - 3, tip_y + 6), (cx + 3, tip_y + 6), (cx + 3, tip_y + 30), (cx - 3, tip_y + 30)], fill="white", z=7)
    p.poly([(cx - 6, tip_y + 30), (cx + 6, tip_y + 30), (cx + 6, tip_y + length), (cx - 6, tip_y + length)], fill=INK, z=7)


def cross(p, cx, cy, s=9):
    p.line([(cx - s, cy - s), (cx + s, cy + s)], lw=1.6, z=9)
    p.line([(cx - s, cy + s), (cx + s, cy - s)], lw=1.6, z=9)


pdf = PdfPages(OUT)

# 1. Chassis plate: straight down on the top, then flipped over (front still to the right)
p = Page(1, "PLATE   x6   3 mm")
p.image("plate-top", 152, 142, w=212); p.rings("plate-top", [0, 1], 3.6)
p.label(14, 170, "TOP", 6, ha="left"); p.label(14, 161, "x2", 5, ha="left")
(x0, y0), (x1, y1) = p.hole("plate-top", 0), p.hole("plate-top", 1)
p.label(x0 - 11, (y0 + y1) / 2 - 1.3, "TRAY", 3.8, ha="right")
p.image("plate-bottom", 152, 52, w=212); p.rings("plate-bottom", [0, 1, 2, 3], 3.6)
p.label(14, 80, "BOTTOM", 6, ha="left"); p.label(14, 71, "x4", 5, ha="left")
(x0, y0), (x1, y1) = p.hole("plate-bottom", 0), p.hole("plate-bottom", 1)
p.label(max(x0, x1) + 10, (y0 + y1) / 2 - 1.3, "BUMPER", 3.8, ha="left")
(x0, y0), (x1, y1) = p.hole("plate-bottom", 2), p.hole("plate-bottom", 3)
p.label(min(x0, x1) - 10, (y0 + y1) / 2 - 1.3, "TOW HOOK", 3.8, ha="right")
p.label(265, 100, "FRONT", 4.2, ha="right")
p.save(pdf)

# 2. Servo box: straight on the bottom and the top
p = Page(2, "SERVO BOX   x6   6 mm")
p.image("box-bottom", 75, 108, h=120); p.rings("box-bottom", [0, 1, 2, 3], 6.5); p.label(75, 36, "BOTTOM   x4", 6)
p.image("box-top", 205, 108, h=120); p.rings("box-top", [0, 1], 6.5); p.label(205, 36, "TOP   x2", 6)
p.save(pdf)

# 3. Beam: from the front, plus one end face straight on
p = Page(3, "BEAM   x2   8 mm")
p.image("beam-front", 112, 118, w=165)
for i, s_ in ((0, -1), (1, 1)):
    x, y = p.hole("beam-front", i)
    p.arrow(x + s_ * 22, y, -s_ * 16, 0)
p.label(112, 70, "FRONT VIEW", 4.0)
p.image("beam-end", 225, 118, h=80); p.rings("beam-end", [0], 7)
p.label(225, 70, "END FACE", 4.0)
p.label(140, 40, "ONE IN EACH END   x2", 6)
p.save(pdf)

pdf.close()
print("wrote", OUT)
