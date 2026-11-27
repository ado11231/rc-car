# Makes the assembly guide: docs/guides/assembly.pdf
# Black and white, pictures + short bold labels, no lines from labels to parts.
# New parts in each step are drawn thick and pulled out along the way they go in (dashed line).
#
#   1) Blender --background blender/rc_car.blend --python blender/scripts/render_assembly.py -- IMG_DIR
#   2) uv run --with matplotlib python blender/scripts/make_assembly_guide.py IMG_DIR
#
# Print at 100% (actual size): the screws on the hardware page and in the corner of each step are 1:1.
import os, sys, json, math
import matplotlib
matplotlib.use("agg")
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import numpy as np
from matplotlib.patches import Polygon, Rectangle, Circle, RegularPolygon, FancyArrow
from matplotlib.backends.backend_pdf import PdfPages

IMG = sys.argv[1]
OUT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "docs", "guides", "assembly.pdf"))
os.makedirs(os.path.dirname(OUT), exist_ok=True)
plt.rcParams["font.family"] = "Arial"
W, H = 279.4, 215.9            # letter, sideways, mm
PT = 72 / 25.4
INK = "#111111"


RES = 0.5                      # occupancy grid, mm per cell


class Page:
    """One page. Everything drawn is marked on an occupancy grid; tags (part labels) are placed last,
    at the free spot nearest to where they were asked for, so they never sit on a drawing or another label."""

    def __init__(self, num, title, sub=None):
        self.fig = plt.figure(figsize=(W / 25.4, H / 25.4))
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set_xlim(0, W); self.ax.set_ylim(0, H); self.ax.set_aspect("equal"); self.ax.axis("off")
        self.rend = self.fig.canvas.get_renderer()
        self.occ = np.zeros((int(H / RES) + 1, int(W / RES) + 1), bool)
        self.hard = np.zeros_like(self.occ)
        self.info = {}
        self.todo = []
        if num is None:
            self.label(14, H - 24, title, 14, ha="left")
        else:
            self.label(14, H - 20, str(num), 9, ha="left")
            self.label(30, H - 20, title, 9, ha="left")
        if sub:
            self.small(30 if num is not None else 14, H - 28, sub, 4.0, ha="left")

    # -- occupancy
    def mark(self, x0, y0, x1, y1):
        c0, c1 = max(int(x0 / RES), 0), min(int(x1 / RES) + 1, self.occ.shape[1])
        r0, r1 = max(int(y0 / RES), 0), min(int(y1 / RES) + 1, self.occ.shape[0])
        self.occ[r0:r1, c0:c1] = True
        self.hard[r0:r1, c0:c1] = True

    def free(self, x0, y0, x1, y1, grid=None):
        if x0 < 6 or x1 > W - 6 or y0 < 6 or y1 > H - 30:
            return False
        g = self.occ if grid is None else grid
        return not g[int(y0 / RES):int(y1 / RES) + 1, int(x0 / RES):int(x1 / RES) + 1].any()

    def bbox(self, t):
        bb = t.get_window_extent(self.rend).transformed(self.ax.transData.inverted())
        return bb.x0, bb.y0, bb.x1, bb.y1

    # -- drawing
    def label(self, x, y, s, size=4.6, ha="center", va="baseline", weight="bold"):
        t = self.ax.text(x, y, s, fontsize=size * PT, ha=ha, va=va, weight=weight, color=INK, zorder=20)
        self.mark(*self.bbox(t))
        return t

    def small(self, x, y, s, size=3.8, ha="center"):
        return self.label(x, y, s, size, ha, weight="normal")

    def image(self, name, cx, cy, w=None, h=None):
        """picture cropped to its drawing, as big as fits in a w x h box centred on (cx, cy)"""
        im = mpimg.imread(os.path.join(IMG, name + ".png"))
        PH, PW = im.shape[:2]
        a = im[:, :, 3] > 0.02
        ys, xs = a.any(axis=1).nonzero()[0], a.any(axis=0).nonzero()[0]
        r0, r1, c0, c1 = ys[0], ys[-1] + 1, xs[0], xs[-1] + 1
        im, a = im[r0:r1, c0:c1], a[r0:r1, c0:c1]
        ch, cw = im.shape[:2]
        k = min(w / cw if w else 1e9, h / ch if h else 1e9)
        w, h = cw * k, ch * k
        x0, y0 = cx - w / 2, cy - h / 2
        self.ax.imshow(im, extent=(x0, x0 + w, y0, y0 + h), interpolation="antialiased", zorder=2)
        # mark the drawing (not its empty corners) on the grid, grown by 1.5 mm
        g0, g1 = int(x0 / RES), int((x0 + w) / RES)
        q0, q1 = int(y0 / RES), int((y0 + h) / RES)
        for r in range(max(q0, 0), min(q1 + 1, self.occ.shape[0])):
            py = int((y0 + h - (r + 0.5) * RES) / k)
            if not 0 <= py < ch: continue
            cols = np.arange(max(g0, 0), min(g1 + 1, self.occ.shape[1]))
            px = ((cols + 0.5) * RES - x0) / k
            ok = (px >= 0) & (px < cw)
            self.occ[r, cols[ok]] |= a[py, px[ok].astype(int)]
        grow = int(1.5 / RES)
        o = self.occ.copy()
        for d in range(1, grow + 1):
            o[d:, :] |= self.occ[:-d, :]; o[:-d, :] |= self.occ[d:, :]
            o[:, d:] |= self.occ[:, :-d]; o[:, :-d] |= self.occ[:, d:]
        self.occ = o
        info = json.load(open(os.path.join(IMG, name + ".json")))
        def P(uv):
            px, py = uv[0] * PW - c0, (1 - uv[1]) * PH - r0      # pixels in the cropped picture, from the top left
            return (x0 + px * k, y0 + h - py * k)
        self.info[name] = {"anchors": {k_: P(v) for k_, v in info["anchors"].items()},
                           "paths": [(P(a_), P(b_)) for a_, b_ in info["paths"]]}
        return w, h

    def tag(self, name, key, dx=0, dy=0, text=None, size=4.6, ha="center", fixed=False):
        """label near a part, no line to it. Asked-for spot = anchor + (dx, dy); moved to the nearest free spot."""
        x, y = self.info[name]["anchors"][key]
        self.todo.append((x, y, dx, dy, text or key.strip(), size, ha, fixed))

    def place(self):
        def search(cx, cy, x, y, tw, th, grid, rmax):
            pad = 1.0
            for r in np.arange(0, rmax, 1.0):
                n = 1 if r == 0 else int(8 + 1.5 * r)
                cands = [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]
                cands = [c for c in cands if self.free(c[0] - tw / 2 - pad, c[1] - th / 2 - pad, c[0] + tw / 2 + pad, c[1] + th / 2 + pad, grid)]
                if cands:
                    return min(cands, key=lambda c: (c[0] - x) ** 2 + (c[1] - y) ** 2)
            return None
        for x, y, dx, dy, s, size, ha, fixed in self.todo:
            t = self.ax.text(0, 0, s, fontsize=size * PT, ha="center", va="center", weight="bold", color=INK, zorder=20)
            bx0, by0, bx1, by1 = self.bbox(t)
            tw, th = bx1 - bx0, by1 - by0
            cx = x + dx + (tw / 2 if ha == "left" else -tw / 2 if ha == "right" else 0)
            cy = y + dy
            best, boxed = (cx, cy), fixed
            if not fixed:
                found = search(cx, cy, x, y, tw, th, None, 24)           # clear white space close by
                if found is None:                                       # else: on the old (thin) drawing, on a white card
                    found = search(cx, cy, x, y, tw, th, self.hard, 30); boxed = True
                if found: best = found
                else: print("  no spot for", repr(s))
            t.set_position(best)
            if boxed:
                t.set_bbox(dict(boxstyle="square,pad=0.15", fc="white", ec="none"))
            self.mark(best[0] - tw / 2 - 0.5, best[1] - th / 2 - 0.5, best[0] + tw / 2 + 0.5, best[1] + th / 2 + 0.5)

    def paths(self, name):
        for (x0, y0), (x1, y1) in self.info[name]["paths"]:
            self.ax.plot([x0, x1], [y0, y1], color=INK, lw=0.35 * PT, ls=(0, (2.2, 1.6)), zorder=3)
            n = int(math.hypot(x1 - x0, y1 - y0) / RES) + 1
            for i in range(n + 1):
                px, py = x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n
                self.mark(px - 0.8, py - 0.8, px + 0.8, py + 0.8)

    def poly(self, pts, fill="white", lw=0.4, z=5):
        self.ax.add_patch(Polygon(pts, closed=True, fc=fill, ec=INK, lw=lw * PT, zorder=z))
        xs, ys = zip(*pts); self.mark(min(xs), min(ys), max(xs), max(ys))

    def line(self, pts, lw=0.3, z=6):
        xs, ys = zip(*pts)
        self.ax.plot(xs, ys, color=INK, lw=lw * PT, solid_capstyle="round", zorder=z)

    def save(self, pdf):
        self.place()
        pdf.savefig(self.fig); plt.close(self.fig)


# ---------------------------------------------------------------- actual-size hardware (page mm = real mm)
def screw(p, x, y, d, L, head_d, head_h):
    """cap screw lying down, head on the left, (x, y) = middle of the head's left side"""
    p.poly([(x, y - head_d / 2), (x + head_h, y - head_d / 2), (x + head_h, y + head_d / 2), (x, y + head_d / 2)])
    p.poly([(x + head_h, y - d / 2), (x + head_h + L, y - d / 2), (x + head_h + L, y + d / 2), (x + head_h, y + d / 2)])
    pitch = 0.5 if d < 2.5 else 0.6
    k = x + head_h + pitch
    while k < x + head_h + L - 0.2:
        p.line([(k, y - d / 2), (k + pitch * 0.6, y + d / 2)], lw=0.15)
        k += pitch
    return head_h + L

def nut(p, x, y, af):
    p.ax.add_patch(RegularPolygon((x, y), 6, radius=af / math.sqrt(3), orientation=0, fc="white", ec=INK, lw=0.4 * PT, zorder=5))
    p.ax.add_patch(Circle((x, y), af * 0.3, fc="white", ec=INK, lw=0.3 * PT, zorder=6))

def washer(p, x, y, od=7.0, id_=3.2):
    p.ax.add_patch(Circle((x, y), od / 2, fc="white", ec=INK, lw=0.4 * PT, zorder=5))
    p.ax.add_patch(Circle((x, y), id_ / 2, fc="white", ec=INK, lw=0.3 * PT, zorder=6))

def insert(p, x, y, L, od=4.6):
    """heat-set insert lying down, knurled"""
    p.poly([(x, y - od / 2), (x + L, y - od / 2), (x + L, y + od / 2), (x, y + od / 2)])
    k = x + 0.7
    while k < x + L - 0.3:
        p.line([(k, y - od / 2), (k + 0.5, y + od / 2)], lw=0.15); p.line([(k + 0.5, y - od / 2), (k, y + od / 2)], lw=0.15)
        k += 1.0

HW = {   # name: (draw function, count)
    "M3 x 8":  (lambda p, x, y: screw(p, x, y, 3, 8, 5.5, 3), 10),
    "M3 x 6":  (lambda p, x, y: screw(p, x, y, 3, 6, 5.5, 3), 2),
    "M3 x 30": (lambda p, x, y: screw(p, x, y, 3, 30, 5.5, 3), 2),
    "M3 WASHER": (lambda p, x, y: washer(p, x + 3.5, y), 4),
    "M2 x 8":  (lambda p, x, y: screw(p, x, y, 2, 8, 3.8, 2), 6),
    "M2 x 6":  (lambda p, x, y: screw(p, x, y, 2, 6, 3.8, 2), 4),
    "M2 NUT":  (lambda p, x, y: nut(p, x + 2.3, y, 4.0), 4),
}

def kit(p, items):
    """the hardware for this step, actual size, top right corner"""
    x, y = W - 92, H - 18
    p.small(x, y + 4, "ACTUAL SIZE", 3.0, ha="left")
    for name, n in items:
        y -= 9
        HW[name][0](p, x, y)
        p.label(x + 44, y - 1.4, f"{name}   x{n}", 4.2, ha="left")


def frame(p, cx, cy, w, h):
    """thin box round a close-up, so the cut edges look on purpose"""
    p.ax.add_patch(Rectangle((cx - w / 2, cy - h / 2), w, h, fill=False, ec=INK, lw=0.4 * PT, zorder=3))


pdf = PdfPages(OUT)

# picture area: under the title and the hardware corner
BX, BY, BW, BH = W / 2, 94, 252, 160

# ---------------------------------------------------------------- cover
p = Page(None, "ASSEMBLY")
p.image("cover", W / 2, 100, 250, 160)
p.save(pdf)

# ---------------------------------------------------------------- 1 motors
p = Page(1, "MOTORS")
kit(p, [("M2 x 8", 4), ("M2 NUT", 4)])
p.image("motors", BX, BY, BW, BH); p.paths("motors")
p.tag("motors", "MOTOR + BRACKET x2", -24, 2, text="MOTOR + BRACKET   x2", ha="right")
p.tag("motors", "M2 NUT x4", 10, 4, text="M2 NUT", ha="left")
p.tag("motors", "M2 x 8 x4", 12, -4, text="M2 x 8   FROM THE TOP", ha="left")
p.tag("motors", "WIRES UP THROUGH SLOT", 14, -6, text="WIRES UP THROUGH THE SLOT", ha="left")
p.tag("motors", "FRONT", 0, -12)
p.save(pdf)

# ---------------------------------------------------------------- 2 servo in
p = Page(2, "SERVO")
iw, ih = p.image("servo-in", BX, BY, BW, BH); p.paths("servo-in"); frame(p, BX, BY, iw, ih)
p.tag("servo-in", "SERVO", -30, -6, ha="right")
p.tag("servo-in", "WIRE", 10, 4, text="WIRE THROUGH THE HOLE FIRST", ha="left")
p.tag("servo-in", "SHAFT", -12, -4, text="SHAFT DOWN", ha="right")
p.tag("servo-in", "SCREWS", 8, 4, text="ITS 2 SCREWS", ha="left")
p.tag("servo-in", "FRONT", 0, -10)
p.save(pdf)

# ---------------------------------------------------------------- 3 center the servo (before the arm)
p = Page(3, "CENTER THE SERVO")
ax = p.ax
def rect(x, y, w, h, fill="white", lw=0.5, z=3, r=0):
    from matplotlib.patches import FancyBboxPatch
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}", fc=fill, ec=INK, lw=lw * PT, zorder=z))
    p.mark(x - 1.5, y - 1.5, x + w + 1.5, y + h + 1.5)
def wire(pts, lw=1.4):
    xs, ys = zip(*pts); ax.plot(xs, ys, color=INK, lw=lw * PT, solid_capstyle="round", zorder=4)
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        p.mark(min(x0, x1) - 1, min(y0, y1) - 1, max(x0, x1) + 1, max(y0, y1) + 1)
def num(x, y, n):
    ax.add_patch(Circle((x, y), 4.2, fc=INK, ec=INK, zorder=6))
    ax.text(x, y - 0.2, str(n), fontsize=5.2 * PT, ha="center", va="center", weight="bold", color="white", zorder=7)
    p.mark(x - 5, y - 5, x + 5, y + 5)
# breadboard with the ESP32, rails on the right (+ inside, - outside)
bx, by, bw, bh = 34, 36, 78, 132
rect(bx, by, bw, bh, lw=0.6)
PX, MX = bx + bw - 12, bx + bw - 6
for x in (PX, MX):
    ax.plot([x, x], [by + 4, by + bh - 4], color=INK, lw=0.6 * PT, ls=(0, (1, 1.5)), zorder=3)
p.label(PX, by + bh + 3, "+", 6); p.label(MX, by + bh + 3, "−", 6)
ex0, ex1, ey0, ey1 = bx + 12, bx + 44, by + bh - 60, by + bh - 12
rect(ex0, ey0, ex1 - ex0, ey1 - ey0, lw=1.4, z=5)
p.label((ex0 + ex1) / 2, (ey0 + ey1) / 2, "ESP32", 4.6)
rect((ex0 + ex1) / 2 - 5, ey1 - 2, 10, 6, lw=1.0, z=6)
wire([((ex0 + ex1) / 2, ey1 + 4), ((ex0 + ex1) / 2, by + bh + 22)], lw=2.2)
p.label((ex0 + ex1) / 2 + 4, by + bh + 16, "USB", 4.6, ha="left")
num((ex0 + ex1) / 2 - 11, by + bh + 16, 1)
J18 = (ex1 + 8, ey0 + 3)
# servo and its 3 wires, no crossings except over the rails
sx, sy = 152, 86
rect(sx, sy, 34, 18, lw=1.4, z=5)
rect(sx - 6, sy + 12, 46, 3, lw=1.0, z=4)
ax.add_patch(Circle((sx + 9, sy + 9), 4, fc="white", ec=INK, lw=1.2 * PT, zorder=6))
p.label(sx + 24, sy + 7.5, "SERVO", 4.0)
for y, end_x, end_y, name in ((sy + 16, J18[0], J18[1], "ORANGE"), (sy + 9, PX, sy + 9, "RED"), (sy + 2, MX, sy + 2, "BROWN")):
    pts = [(sx, y), (end_x + 6 if name == "ORANGE" else end_x, y)]
    if name == "ORANGE":
        pts += [(end_x + 6, end_y), (end_x, end_y)]
    wire(pts, lw=1.3)
    ax.add_patch(Circle(pts[-1], 1.3, fc=INK, ec=INK, zorder=6))
    p.label((MX + sx) / 2 + 2, y + 1.6, name, 3.4)
p.label(J18[0], J18[1] + 3.5, "j18", 3.8)
# phone
fx, fy = 206, 62
rect(fx, fy, 44, 86, lw=1.4, r=5)
p.label(fx + 22, fy + 74, "rc-car", 4.0)
p.label(fx + 22, fy + 67, "192.168.4.1", 3.6, weight="normal")
ax.add_patch(Circle((fx + 22, fy + 34), 12, fc="white", ec=INK, lw=0.8 * PT, zorder=6))
ax.add_patch(Circle((fx + 22, fy + 34), 4, fc=INK, ec=INK, zorder=7))
p.label(fx + 22, fy - 9, "STEER, THEN LET GO", 4.2)
num(fx + 22, fy + 98, 2)
# result
num(sx + 17, sy - 14, 3)
p.label(sx + 17, sy - 26, "SERVO CENTERED", 4.6)
p.label(sx + 17, sy - 34, "KEEP USB IN  →  STEP 4", 4.2)
p.save(pdf)

# ---------------------------------------------------------------- 4 arm (car upside down)
p = Page(4, "SERVO ARM")
iw, ih = p.image("arm", 92, BY, 160, BH); p.paths("arm"); frame(p, 92, BY, iw, ih)
p.tag("arm", "ARM", -18, 0, text="SERVO ARM", ha="right")
p.tag("arm", "ARM SCREW", 8, 2, ha="left")
p.tag("arm", "FRONT", 0, -10)
iw, ih = p.image("arm-under", 222, 96, 84, 110)
p.label(222, 96 + ih / 2 + 5, "FRONT  ↑", 4.2)
p.label(222, 96 - ih / 2 - 9, "STRAIGHT ACROSS", 4.6)
p.save(pdf)

# ---------------------------------------------------------------- 5 beam (car upside down)
p = Page(5, "BEAM")
kit(p, [("M2 x 8", 2)])
iw, ih = p.image("beam-on", BX, BY, BW, BH); p.paths("beam-on"); frame(p, BX, BY, iw, ih)
p.tag("beam-on", "BEAM", -16, 0, ha="right")
p.tag("beam-on", "M2 x 8", 10, 4, ha="left")
p.tag("beam-on", "FRONT", 0, -10)
p.save(pdf)

# ---------------------------------------------------------------- 4 wheels
p = Page(6, "WHEELS")
kit(p, [("M3 x 30", 2), ("M3 WASHER", 4)])
p.image("wheels", 100, 124, 180, 92); p.paths("wheels")
p.tag("wheels", "PUSH ON (D SHAFT)", 0, -24, text="PUSH ON")
p.image("wheel-stack", 168, 44, 200, 62); p.paths("wheel-stack")
p.label(30, 74, "FRONT, CLOSE UP", 4.0, ha="left")
for k_, dy in (("M3 x 30", -9), ("WASHER", 9), ("WHEEL", -20), ("WASHER ", 9)):
    p.tag("wheel-stack", k_, 0, dy, size=4.2)
p.tag("wheel-stack", "INSERT", 6, -10, text="BEAM", size=4.2)
p.save(pdf)

# ---------------------------------------------------------------- 5 servo box
p = Page(7, "SERVO BOX")
kit(p, [("M3 x 8", 4)])
iw, ih = p.image("box-side", BX - 18, 120, 222, 84); p.paths("box-side")
p.label(BX - 18 + iw / 2 + 4, 120 - ih * 0.1, "FRONT  →", 4.2, ha="left")
p.tag("box-side", "SERVO BOX", 0, 12)
p.tag("box-side", "M3 x 8 x4", -10, 0, text="M3 x 8   x4   FROM UNDER", ha="right")
p.image("box-iso", BX, 44, 120, 62)
p.save(pdf)

# ---------------------------------------------------------------- 6 bumper
p = Page(8, "BUMPER")
kit(p, [("M3 x 8", 4)])
iw, ih = p.image("bumper-side", BX - 18, 120, 222, 84); p.paths("bumper-side")
p.label(BX - 18 + iw / 2 + 4, 120 - ih * 0.1, "FRONT  →", 4.2, ha="left")
p.tag("bumper-side", "BUMPER", 18, 10, ha="left")
p.tag("bumper-side", "M3 x 8 x2 TOP", -8, 0, text="M3 x 8   x2   TOP", ha="right")
p.tag("bumper-side", "M3 x 8 x2 UNDER", -8, 0, text="M3 x 8   x2   UNDER", ha="right")
p.image("bumper-iso", BX, 44, 120, 62)
p.save(pdf)

# ---------------------------------------------------------------- 7 tow hook
p = Page(9, "TOW HOOK")
kit(p, [("M3 x 8", 2)])
p.image("hook", BX, BY, BW, BH); p.paths("hook")
p.tag("hook", "TOW HOOK", -22, -4, ha="right")
p.tag("hook", "M3 x 8 x2", 10, 4, text="M3 x 8", ha="left")
p.tag("hook", "BACK", 0, -14)
p.save(pdf)

# ---------------------------------------------------------------- 8 switch
p = Page(10, "SWITCH")
p.image("switch", BX, BY + 6, BW, BH + 10); p.paths("switch")
p.tag("switch", "SWITCH", 16, 6, ha="left")
p.tag("switch", "FRONT", 0, -12)
p.save(pdf)

# ---------------------------------------------------------------- 9 main board
p = Page(11, "MAIN BOARD")
kit(p, [("M2 x 6", 4)])
p.image("board", BX, BY, BW, BH); p.paths("board")
p.tag("board", "MAIN BOARD", -46, -10, ha="right")
(sx, sy) = max((a_ for a_, b_ in p.info["board"]["paths"]), key=lambda q: q[0])
p.label(sx + 5, sy, "M2 x 6", 4.6, ha="left", va="center")
p.tag("board", "USB", 26, -10, text="USB TO THE RIGHT", ha="left")
p.tag("board", "TERMINALS TO THE BACK", -12, 12, text="TERMINALS TO THE BACK", ha="right")
p.tag("board", "FRONT", 0, -12)
p.save(pdf)

# ---------------------------------------------------------------- 10 wires (top view, front up)
p = Page(12, "WIRES")
X0, Y = W - 96, H - 16
for a_, b_ in (("LEFT MOTOR", "B"), ("RIGHT MOTOR", "A"), ("BATTERY BLACK", "-"), ("SWITCH WIRE", "+"),
               ("SERVO PLUG", "BROWN BACK")):
    p.label(X0, Y, a_, 4.2, ha="left"); p.label(X0 + 42, Y, "→   " + b_, 4.2, ha="left")
    Y -= 8
iw, ih = p.image("wires-close", 118, 92, 200, 158)
p.label(118, 92 + ih / 2 + 4, "FRONT", 4.6)
p.tag("wires-close", "-", 0, 0, size=8, fixed=True); p.tag("wires-close", "+", 0, 0, size=8, fixed=True)
p.tag("wires-close", "MOTOR B", 0, 0, text="B", size=8, fixed=True)
p.tag("wires-close", "MOTOR A", 0, 0, text="A", size=8, fixed=True)
p.tag("wires-close", "SERVO", 0, 0, size=4.2, fixed=True)
p.tag("wires-close", "BATTERY", 0, 14, size=4.6)
p.tag("wires-close", "LEFT MOTOR", -14, 0, ha="right", size=4.6)
p.tag("wires-close", "RIGHT MOTOR", 14, 0, ha="left", size=4.6)
p.tag("wires-close", "SWITCH", -14, 0, ha="right", size=4.6)
p.save(pdf)

# ---------------------------------------------------------------- 11 tray, antenna, battery
p = Page(13, "TRAY + ANTENNA + BATTERY")
kit(p, [("M3 x 6", 2)])
p.image("tray", BX, BY, BW, BH); p.paths("tray")
p.tag("tray", "BATTERY TRAY", -24, -4, ha="right")
p.tag("tray", "M3 x 6 x2", -16, -10, text="M3 x 6", ha="right")
p.tag("tray", "ANTENNA", 6, 4, text="ANTENNA   PUSH IN", ha="left")
p.tag("tray", "BATTERY (LAST)", 30, 6, text="BATTERY   LAST", ha="left")
p.tag("tray", "BACK", 0, -14)
p.save(pdf)

# ---------------------------------------------------------------- done: reference views
p = Page(None, "DONE")
p.image("ref-top", 50, 128, 70, 110); p.small(50, 66, "TOP", 4.0)
p.image("ref-under", 124, 128, 70, 110); p.small(124, 66, "BOTTOM", 4.0)
p.image("ref-back", 216, 128, 100, 100); p.small(216, 66, "BACK LEFT", 4.0)
p.image("ref-side", 140, 34, 180, 44); p.small(140, 8, "RIGHT SIDE", 4.0)
p.save(pdf)

pdf.close()
print("wrote", OUT)
