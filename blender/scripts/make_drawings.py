# Makes the black-and-white drawing PDFs for the 7 printed parts, one page per part.
#
#   uv run --with matplotlib python blender/scripts/make_drawings.py              all 7, plus all-parts.pdf
#   uv run --with matplotlib python blender/scripts/make_drawings.py plate beam   only these
#   (names: plate beam tray bumper box antenna hook)
#
# Writes docs/drawings/NN-name.pdf and docs/drawings/all-parts.pdf.
# The picture on each page is docs/renders/NN-name.png (made with render_part.py).
# Every page is checked when it is saved: it prints how many labels touch other labels, lines or pictures.
# Keep that at 0.
import os, sys, math
import matplotlib
import matplotlib.text
matplotlib.use("agg")
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.patches import Circle, Polygon, Rectangle
from matplotlib.backends.backend_pdf import PdfPages

DOCS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "docs")
OUT = os.path.join(DOCS, "drawings")          # the PDFs
RENDERS = os.path.join(DOCS, "renders")       # the part pictures
FOLDERS = {"01": "01-chassis-plate", "02": "02-steering-beam", "03": "03-battery-tray", "04": "04-front-bumper",
           "05": "05-servo-box", "06": "06-antenna", "07": "07-tow-hook"}
W, H = 279.4, 215.9                 # letter paper sideways, in mm
PT = 72 / 25.4                      # points per mm
INK, THIN, FAINT = "#111111", "#555555", "#b5b5b5"
HID = (0, (2.2, 1.4))               # dash pattern for edges you can't see


class Sheet:
    """one page. Everything is placed in mm from the bottom left corner of the page."""

    def __init__(self, num, title, sub):
        self.num = num
        self.fig = plt.figure(figsize=(W / 25.4, H / 25.4))
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set_xlim(0, W); self.ax.set_ylim(0, H); self.ax.set_aspect("equal"); self.ax.axis("off")
        self.text(12, H - 16, f"{num}  {title}", 6.5, weight="bold")
        self.text(12, H - 23, sub, 3.0)

    # Basic shapes
    def text(self, x, y, s, size=2.6, ha="left", va="baseline", rot=0, color=INK, weight="normal"):
        self.ax.text(x, y, s, fontsize=size * PT, ha=ha, va=va, rotation=rot, color=color, weight=weight)

    def line(self, pts, lw=0.25, color=INK, ls="-"):
        xs, ys = zip(*pts)
        ln, = self.ax.plot(xs, ys, lw=lw * PT, color=color, ls=ls, solid_capstyle="butt")
        ln.dim_id = getattr(self, "_in_dim", 0)       # lines that belong to a dimension may touch its arrows
        return ln

    def poly(self, pts, lw=0.45):
        self.ax.add_patch(Polygon(pts, closed=True, fill=False, lw=lw * PT, ec=INK))

    def rect(self, x, y, w, h, lw=0.45, fill=None):
        self.ax.add_patch(Rectangle((x, y), w, h, fill=fill is not None, fc=fill or "none", lw=lw * PT, ec=INK))

    def circle(self, x, y, d, lw=0.35):
        self.ax.add_patch(Circle((x, y), d / 2, fill=False, lw=lw * PT, ec=INK))

    def cross(self, x, y, s=1.2):
        """small + mark"""
        self.line([(x - s, y), (x + s, y)], 0.12, THIN); self.line([(x, y - s), (x, y + s)], 0.12, THIN)

    def arrow(self, p, q):
        an = self.ax.annotate("", xy=q, xytext=p, arrowprops=dict(arrowstyle="-|>", lw=0.25 * PT, color=INK,
                                                                  mutation_scale=4.5, shrinkA=0, shrinkB=0))
        an.dim_id = getattr(self, "_dim", 0)
        an.ends = (tuple(p), tuple(q))

    def origin(self, x, y, right=False):
        """black dot with "0,0": the corner the hole list measures from"""
        self.ax.add_patch(Circle((x, y), 1.3, color=INK, zorder=5))
        if right:
            self.text(x + 2.2, y - 4.2, "0,0", 2.4, ha="left", weight="bold")
        else:
            self.text(x - 2, y - 4.2, "0,0", 2.4, ha="right", weight="bold")

    def hole(self, x, y, d, insert=False):
        """hole with centre lines through it. Insert holes get a thin ring around them."""
        self.circle(x, y, d)
        if insert:
            self.circle(x, y, d + 1.8, 0.15)
        e = d / 2 + (2.6 if insert else 1.8)
        for p, q in (((x - e, y), (x + e, y)), ((x, y - e), (x, y + e))):
            self.ax.plot(*zip(p, q), lw=0.13 * PT, color=THIN, dashes=(6, 1.5, 1, 1.5))

    # Sizes
    def dim_h(self, x0, x1, y, yref0, yref1, label=None):
        """side-to-side size from x0 to x1. The arrow line is at height y, with lines down (or up) to yref0 and yref1."""
        self._dim = getattr(self, "_dim", 0) + 1
        self._in_dim = self._dim
        for x, yr in ((x0, yref0), (x1, yref1)):
            self.line([(x, yr + (1 if y > yr else -1)), (x, y + (1.5 if y > yr else -1.5))], 0.15, THIN)
        self.arrow(((x0 + x1) / 2, y), (x0, y)); self.arrow(((x0 + x1) / 2, y), (x1, y))
        label = label or fmt(x1 - x0)
        if len(label) * 1.75 + 1.2 > abs(x1 - x0):          # number doesn't fit between the arrows: put it beside them
            self.text(max(x0, x1) + 1.6, y - 1.0, label, 2.8, ha="left")
        else:
            self.text((x0 + x1) / 2, y + 1.0, label, 2.8, ha="center")
        self._in_dim = 0

    def dim_v(self, y0, y1, x, xref0, xref1, label=None):
        """up-and-down size from y0 to y1, arrow line at x"""
        self._dim = getattr(self, "_dim", 0) + 1
        self._in_dim = self._dim
        for y, xr in ((y0, xref0), (y1, xref1)):
            self.line([(xr + (1 if x > xr else -1), y), (x + (1.5 if x > xr else -1.5), y)], 0.15, THIN)
        self.arrow((x, (y0 + y1) / 2), (x, y0)); self.arrow((x, (y0 + y1) / 2), (x, y1))
        self.text(x + (1.2 if x > xref0 else -1.2), (y0 + y1) / 2, label or fmt(y1 - y0), 2.8,
                  ha="left" if x > xref0 else "right", va="center", rot=0)
        self._in_dim = 0

    def callout(self, tx, ty, px, py, label, ha="left"):
        """text at (tx, ty) with a thin line to the point (px, py)"""
        self.line([(px, py), (tx - (1 if ha == "left" else -1), ty + 0.8)], 0.15, THIN)
        self.ax.add_patch(Circle((px, py), 0.35, color=INK))
        self.text(tx, ty, label, 2.6, ha=ha)

    def view_label(self, x, y, label):
        self.text(x, y, label, 2.8, weight="bold")

    def picture(self, path, x, y, w, caption=None):
        img = mpimg.imread(path)
        h = w * img.shape[0] / img.shape[1]
        self.ax.imshow(img, extent=(x, x + w, y, y + h), zorder=1)
        if caption:
            self.text(x + w / 2, y - 3, caption, 2.6, ha="center", color=THIN)

    # Layout check
    def check(self):
        """list labels that touch other labels, lines or pictures, and lines that cross a size arrow"""
        r = self.fig.canvas.get_renderer()
        inv = self.ax.transData.inverted()
        texts = []
        for t in self.ax.texts:
            if not t.get_text().strip():
                continue
            bb = t.get_window_extent(r)
            (x0, y0), (x1, y1) = inv.transform([(bb.x0, bb.y0), (bb.x1, bb.y1)])
            texts.append((t.get_text(), (x0 + 0.3, y0 + 0.3, x1 - 0.3, y1 - 0.3)))
        segs = []
        for ln in self.ax.lines:
            xy = ln.get_xydata()
            segs += [(xy[i], xy[i + 1]) for i in range(len(xy) - 1)]
        for pa in self.ax.patches:
            v = inv.transform(pa.get_verts()) if len(pa.get_verts()) else []
            if len(v) > 300:
                v = v[::4]
            segs += [(v[i], v[i + 1]) for i in range(len(v) - 1)]
        for an in [c for c in self.ax.get_children() if isinstance(c, matplotlib.text.Annotation)]:
            v = inv.transform(an.arrow_patch.get_path().vertices) if an.arrow_patch else []
            segs += [(v[i], v[i + 1]) for i in range(len(v) - 1)]
        boxes = [tuple(im.get_extent()) for im in self.ax.images]          # x0, x1, y0, y1
        out = []
        anns = [c for c in self.ax.get_children() if isinstance(c, matplotlib.text.Annotation) and hasattr(c, "ends")]
        for i, a in enumerate(anns):
            for b in anns[i + 1:]:
                if a.dim_id != b.dim_id and segs_cross(a.ends, b.ends):
                    out.append(f"dimension arrows cross near ({a.ends[1][0]:.0f},{a.ends[1][1]:.0f})")
        for (bx0, bx1, by0, by1) in boxes:
            for (p0, p1) in segs:
                if seg_hits_box(p0, p1, (bx0, by0, bx1, by1)):
                    out.append(f"a drawing line runs into a picture near ({p0[0]:.0f},{p0[1]:.0f})")
                    break
        for a in anns:
            for ln in self.ax.lines:
                if getattr(ln, "dim_id", 0) == a.dim_id and a.dim_id:
                    continue
                xy = ln.get_xydata()
                for i in range(len(xy) - 1):
                    if segs_cross(a.ends, (tuple(xy[i]), tuple(xy[i + 1]))):
                        out.append(f"a line crosses the dimension arrow near ({a.ends[1][0]:.0f},{a.ends[1][1]:.0f})")
                        break
        for i, (ta, a) in enumerate(texts):
            if a[0] < 0 or a[2] > W or a[1] < 0 or a[3] > H:
                out.append(f"'{ta}' runs off the page")
            for tb, b in texts[i + 1:]:
                if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
                    out.append(f"'{ta}'  overlaps text  '{tb}'")
            for (p0, p1) in segs:
                if seg_hits_box(p0, p1, a):
                    out.append(f"'{ta}'  is crossed by a line near ({p0[0]:.0f},{p0[1]:.0f})-({p1[0]:.0f},{p1[1]:.0f})")
                    break
            for (bx0, bx1, by0, by1) in boxes:
                if a[0] < bx1 and bx0 < a[2] and a[1] < by1 and by0 < a[3]:
                    out.append(f"'{ta}'  sits on a picture")
        return out


def seg_hits_box(p0, p1, b):
    """does the line p0-p1 pass through the box b = (x0, y0, x1, y1)?"""
    x0, y0 = p0; dx, dy = p1[0] - x0, p1[1] - y0
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x0 - b[0]), (dx, b[2] - x0), (-dy, y0 - b[1]), (dy, b[3] - y0)):
        if abs(p) < 1e-12:
            if q < 0:
                return False
        else:
            t = q / p
            if p < 0:
                t0 = max(t0, t)
            else:
                t1 = min(t1, t)
            if t0 > t1:
                return False
    return True


def segs_cross(s1, s2):
    """do two lines cross? (touching at the ends does not count)"""
    (a, b), (c, d) = s1, s2
    def orient(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    o1, o2, o3, o4 = orient(a, b, c), orient(a, b, d), orient(c, d, a), orient(c, d, b)
    return o1 * o2 < -1e-6 and o3 * o4 < -1e-6


def fmt(v):
    """number without extra zeros: 4.0 -> "4", 2.50 -> "2.5" """
    return f"{v:.2f}".rstrip("0").rstrip(".")


# helpers shared by the 7 parts
def rrect(u0, u1, v0, v1, r, n=8):
    """outline of a rectangle with round corners"""
    pts = []
    for cu, cv, a0 in ((u1 - r, v0 + r, -90), (u1 - r, v1 - r, 0), (u0 + r, v1 - r, 90), (u0 + r, v0 + r, 180)):
        pts += [(cu + r * math.cos(math.radians(a0 + 90 * i / n)), cv + r * math.sin(math.radians(a0 + 90 * i / n))) for i in range(n + 1)]
    return pts


def outline(s, pts, lw=0.45, ls="-", color=INK):
    """closed outline through pts"""
    s.line(list(pts) + [pts[0]], lw, color, ls)


def tag(s, x, y, t, dx=1.6, dy=1.2):
    """bold hole number next to a hole"""
    s.text(x + dx, y + dy, t, 2.4, weight="bold")


def hole_table(s, x, y, rows, per=9, cw=(6, 14, 14, 24), head=("#", "from back", "from right", "size"), size=2.4):
    """table with `per` rows in each column block. The first 3 columns are centred, the rest start at the left."""
    rh = size * 1.75
    for c in range((len(rows) + per - 1) // per):
        part = rows[c * per:(c + 1) * per]
        xs = [x + c * (sum(cw) + 5) + sum(cw[:i]) for i in range(len(cw) + 1)]
        for i, t in enumerate(head):
            s.text(xs[i] + (cw[i] / 2 if i < 3 else 1), y, t, size - 0.1, ha="center" if i < 3 else "left", weight="bold")
        s.line([(xs[0], y - 1.6), (xs[-1], y - 1.6)], 0.2, INK)
        for r, row in enumerate(part):
            yy = y - 1.6 - rh * (r + 1) + 1.2
            for i, t in enumerate(row):
                t = fmt(t) if isinstance(t, (int, float)) else t
                s.text(xs[i] + (cw[i] / 2 if i < 3 else 1), yy, t, size, ha="center" if i < 3 else "left", weight="bold" if i == 0 else "normal")
            s.line([(xs[0], yy - 1.3), (xs[-1], yy - 1.3)], 0.08, FAINT)
    return y - 1.6 - rh * min(per, len(rows))


def pic(s, num, x, y, w, caption):
    """the part's picture (docs/renders/NN-name.png)"""
    s.picture(os.path.join(RENDERS, FOLDERS[num] + ".png"), x, y, w)


# 01 Chassis plate
PLATE_FEATS = ([(u, v, "ins") for u, v in ((6, 30), (7, 14), (7, 46), (13, 30), (169, 24), (169, 36))]
               + [(u, v, "3.4") for u, v in ((130, 20), (130, 40), (169, 17), (169, 43))]
               + [(u, v, "2.2") for u, v in ((17.3, 4.5), (17.3, 55.5), (36.7, 4.5), (36.7, 55.5))]
               + [(147, 21.25, "1.6"), (147, 48.9, "1.6"), (57, 57.5, "3.2"), (64, 57.5, "3.2"), (119, 49, "6")]
               + [(u, v, "post") for u, v in ((43.8, 7.8), (43.8, 52.2), (108.2, 7.8), (108.2, 52.2))])
PLATE_CUTS = [("A", 38, 30, 3, 8), ("B", 61, 68, 15, 10), ("C", 147, 35.2, 12.8, 23.4)]
HOLE_D = {"ins": 4.0, "3.4": 3.4, "2.2": 2.2, "1.6": 1.6, "3.2": 3.2, "6": 6.0, "post": 1.6}


def plate_items():
    """everything on the plate in order from the back: (tag, u, v, kind or cut)"""
    items = sorted([(u, v, kd) for u, v, kd in PLATE_FEATS] + [(c[1], c[2], c) for c in PLATE_CUTS], key=lambda f: (f[0], f[1]))
    out, n = [], 0
    for u, v, kd in items:
        if isinstance(kd, tuple):
            out.append((kd[0], u, v, kd))
        else:
            n += 1
            out.append((str(n), u, v, kd))
    return out


def plate():
    s = Sheet("01", "Chassis plate", "Print 1   |   4 thick, wing 2 thick   |   Insert holes: brass insert melted in after printing")
    k, ox, oy = 0.9, 26.0, 98.0
    P = lambda u, v: (ox + k * u, oy + k * v)
    s.view_label(ox, 180, "TOP VIEW")
    out = [(0, 0), (111, 0), (111, 6), (175, 6), (175, 54), (111, 54), (111, 60), (71, 60), (71, 76), (51, 76), (51, 60), (0, 60)]
    s.poly([P(*q) for q in out])
    s.line([P(51, 60), P(71, 60)], 0.2, THIN, HID)
    nudge = {"1": (-4.4, 2.4), "14": (-6.6, -5.6), "21": (-7.4, 1.1), "22": (-7.4, 1.1), "11": (1.9, -3.6), "12": (1.9, -3.6), "18": (1.1, -3.6)}
    for t, u, v, kd in plate_items():
        x, y = P(u, v)
        if isinstance(kd, tuple):
            _, _, _, w, h = kd
            s.rect(x - k * w / 2, y - k * h / 2, k * w, k * h, 0.35)
            if w > 10:
                s.text(x, y - 1.0, t, 2.6, ha="center", weight="bold")
            else:
                tag(s, x + k * w / 2, y + k * h / 2 - 2.4, t, 0.8, 0)
            continue
        d = HOLE_D[kd]
        if kd == "post":
            s.circle(x, y, 5 * k, 0.35)
        s.hole(x, y, d * k, insert=kd == "ins")
        r = (5 if kd == "post" else d + (1.8 if kd == "ins" else 0)) * k / 2
        dx, dy = nudge.get(t, (r + 0.3, 1.1))
        tag(s, x, y, t, dx, dy)
    s.origin(*P(0, 0), right=True)
    s.text(*P(20, 63), "WING", 2.4, weight="bold")
    s.arrow(P(30, 64), P(49, 68))

    x0, y0 = P(0, 0)
    s.dim_h(P(0, 0)[0], P(51, 0)[0], 174, P(0, 60)[1], P(51, 76)[1], "51")
    s.dim_h(P(51, 0)[0], P(71, 0)[0], 174, P(51, 76)[1], P(71, 76)[1], "20")
    s.dim_v(P(0, 60)[1], P(0, 76)[1], P(71, 0)[0] + 6, P(71, 0)[0], P(71, 0)[0], "sticks out 16")
    s.dim_h(x0, P(111, 0)[0], oy - 8, y0, y0, "111")
    s.dim_h(P(111, 0)[0], P(175, 0)[0], oy - 8, y0, P(175, 6)[1], "64")
    s.dim_h(x0, P(175, 0)[0], oy - 15, y0, P(175, 6)[1], "175 long")
    s.dim_v(y0, P(0, 60)[1], x0 - 7, x0, x0, "60 wide")
    s.dim_v(P(0, 6)[1], P(0, 54)[1], P(175, 0)[0] + 7, P(175, 0)[0], P(175, 0)[0], "48 wide")
    s.dim_v(y0, P(0, 6)[1], P(140, 0)[0], P(111, 0)[0], P(140, 0)[0], "6")
    s.text(*P(132, 66), "FRONT", 2.6, weight="bold")
    s.arrow(P(146, 67), P(160, 67))

    # post detail
    k3, cx, by = 2.0, 240.0, 78.0
    s.view_label(204, 112, "POST DETAIL  (9, 10, 13, 14)")
    s.rect(cx - 20, by, 40, 4 * k3)
    s.rect(cx - 2.5 * k3, by + 4 * k3, 5 * k3, 6 * k3, 0.45)
    s.rect(cx - 0.8 * k3, by + 5 * k3, 1.6 * k3, 5 * k3, 0.3)
    s.dim_v(by, by + 4 * k3, cx - 24, cx - 20, cx - 20, "plate 4")
    s.dim_v(by + 4 * k3, by + 10 * k3, cx + 9, cx + 5, cx + 5, "post 6 tall")
    s.dim_v(by + 5 * k3, by + 10 * k3, cx - 9, cx - 1.6, cx - 5, "hole 5 deep")
    s.dim_h(cx - 5, cx + 5, by + 10 * k3 + 4, by + 10 * k3, by + 10 * k3, "Ø5 post")
    s.text(cx - 5, by + 10 * k3 + 9, "Ø1.6 centre hole", 2.3)

    rows = []
    for tg, u, v, kd in plate_items():
        if isinstance(kd, tuple):
            rows.append((tg, u, v, f"{fmt(kd[3])} x {fmt(kd[4])} cutout, through"))
        elif kd == "post":
            rows.append((tg, u, v, "Ø5 post 6 tall, Ø1.6 hole 5 deep"))
        else:
            rows.append((tg, u, v, ("Ø4.0 insert hole" if kd == "ins" else "Ø" + fmt(HOLE_D[kd]) + " hole") + ", through"))
    s.rect(6, 6, 270, 70, 0.6)
    s.text(10, 69.5, "HOLE LIST", 4.2, weight="bold")
    s.text(48, 69.8, "from the back and right edges to the centre", 2.5)
    hole_table(s, 10, 62, rows, per=9, cw=(6, 16, 17, 45), size=2.75)
    pic(s, "01", 214, 120, 60, "")
    return s


# 02 Steering beam
def beam():
    s = Sheet("02", "Steering beam", "Print 1, flat on its bottom   |   Edges rounded 0.6   |   All holes centred")
    k = 2.0
    ox, oy = 34.0, 132.0
    F = lambda u, h: (ox + k * u, oy + k * h)
    s.view_label(ox, 172, "FRONT VIEW")
    s.poly([F(0, 0), F(72, 0), F(72, 12.8), F(62, 12.8), F(62, 5.45), F(10, 5.45), F(10, 12.8), F(0, 12.8)])
    for u0, u1 in ((0, 10), (62, 72)):
        for h in (7, 11):
            s.line([F(u0, h), F(u1, h)], 0.18, THIN, HID)
        s.line([F(u0 - 1.5, 9), F(u1 + 1.5, 9)], 0.13, THIN, (0, (6, 1.5, 1, 1.5)))
    for u, r in ((26, 1.2), (46, 1.2), (36, 2.5)):
        for e in (-r, r):
            s.line([F(u + e, 0), F(u + e, 5.45)], 0.18, THIN, HID)
    s.dim_h(F(0, 0)[0], F(72, 0)[0], oy - 8, oy, oy, "72 long")
    s.dim_h(F(0, 0)[0], F(10, 0)[0], F(0, 12.8)[1] + 6, F(0, 12.8)[1], F(10, 12.8)[1], "10")
    s.dim_h(F(62, 0)[0], F(72, 0)[0], F(0, 12.8)[1] + 6, F(62, 12.8)[1], F(72, 12.8)[1], "10")
    s.dim_v(oy, F(0, 12.8)[1], F(72, 0)[0] + 7, F(72, 0)[0], F(72, 0)[0], "12.8 tall")
    s.dim_v(oy, F(0, 9)[1], ox - 6, ox, ox, "9")
    s.dim_v(oy, F(0, 5.45)[1], F(18, 0)[0], F(18, 0)[0], F(18, 0)[0], "5.45 tall")

    ty = 88.0
    T = lambda u, v: (ox + k * u, ty + k * v)
    s.view_label(ox, ty + 30, "TOP VIEW")
    s.rect(*T(0, 0), k * 72, k * 10)
    s.line([T(10, 0), T(10, 10)], 0.2, INK); s.line([T(62, 0), T(62, 10)], 0.2, INK)
    for u, d in ((26, 2.4), (46, 2.4), (36, 5.0)):
        s.hole(*T(u, 5), d * k)
    s.dim_h(T(0, 0)[0], T(26, 0)[0], ty - 7, ty, T(26, 5)[1], "26")
    s.dim_h(T(26, 0)[0], T(36, 0)[0], ty - 7, T(26, 5)[1], T(36, 5)[1], "10")
    s.dim_h(T(36, 0)[0], T(46, 0)[0], ty - 7, T(36, 5)[1], T(46, 5)[1], "10")
    s.dim_v(ty, T(0, 10)[1], T(72, 0)[0] + 7, T(72, 0)[0], T(72, 0)[0], "10 wide")
    s.callout(T(50, 0)[0], ty + 24, T(46, 5)[0] + 1.6, T(46, 5)[1] + 1.6, "2 holes Ø2.4, through")
    s.callout(T(22, 0)[0], ty + 24, T(36, 5)[0] - 3.4, T(36, 5)[1] + 3.4, "Ø5, through", ha="right")

    ex, ey = 230.0, 132.0
    E = lambda v, h: (ex + k * v, ey + k * h)
    s.view_label(ex - 10, 172, "END VIEW")
    s.rect(ex, ey, k * 10, k * 12.8)
    s.hole(*E(5, 9), 4.0 * k)
    s.dim_h(ex, E(10, 0)[0], ey - 7, ey, ey, "10")
    s.dim_v(ey, E(0, 9)[1], E(10, 0)[0] + 7, E(5, 9)[0], E(10, 0)[0], "9")
    s.callout(ex - 5, ey + 17, E(5, 9)[0] - 4.0, E(5, 9)[1], "Ø4.0, through", ha="right")

    pic(s, "02", 150, 6, 112, "The part")
    return s


# 03 Battery tray
TRAY_ROWS = [("1", 6.4, 14, "Ø3.4 hole, through, Ø6 step 3 deep"),
             ("2", 6.4, 46, "Ø3.4 hole, through, Ø6 step 3 deep"),
             ("3", 16.7, 4.5, "Ø4.8 pocket in the bottom, 2.3 deep"),
             ("4", 16.7, 55.5, "Ø4.8 pocket in the bottom, 2.3 deep"),
             ("W", 16.9, 30, "15 x 24 window, r4 corners, through"),
             ("post", -2, 52, "Ø7 post 11 tall, Ø3.2 hole 8 deep")]


def tray():
    s = Sheet("03", "Battery tray", "Print 1, floor down   |   Corners r3, inside r1   |   Walls 2 (front 1.95)   |   Top edge 0.6 chamfer")
    k, ox, oy = 1.6, 44.0, 62.0
    P = lambda u, v: (ox + k * u, oy + k * v)
    L, Wd = 34.35, 60.0
    s.view_label(18, 178, "TOP VIEW")
    outline(s, [P(*q) for q in rrect(0, L, 0, Wd, 3)])
    outline(s, [P(*q) for q in rrect(2, L - 1.95, 2, Wd - 2, 1)], 0.3)
    s.circle(*P(-2, 52), 7 * k, 0.45)
    s.hole(*P(-2, 52), 3.2 * k)
    outline(s, [P(*q) for q in rrect(9.4, 24.4, 18, 42, 4)], 0.35)
    s.text(*P(16.9, 29), "W", 2.6, ha="center", weight="bold")
    for n, (u, v) in enumerate(((6.4, 14), (6.4, 46)), 1):
        s.hole(*P(u, v), 3.4 * k); s.circle(*P(u, v), 6 * k, 0.3)
        tag(s, *P(u, v), str(n), 5.2, 1.4)
    for n, (u, v) in enumerate(((16.7, 4.5), (16.7, 55.5)), 3):
        s.circle(*P(u, v), 4.8 * k, 0.25); s.ax.patches[-1].set_linestyle(HID)
        tag(s, *P(u, v), str(n), 4.4, 1.6)
    s.origin(*P(0, 0), right=True)
    x0, y0 = P(0, 0); x1, y1 = P(L, Wd)
    s.dim_h(x0, x1, y1 + 8, y1, y1, "34.35 long")
    s.dim_v(y0, y1, x1 + 8, x1, x1, "60 wide")
    s.dim_h(P(-2, 0)[0], x0, y1 + 8, P(-2, 52)[1] + 7, y1, "2")
    s.dim_v(P(0, 52)[1], y1, P(-2, 0)[0] - 10, P(-2, 52)[0] - 7, x0, "8")
    s.callout(30, 134, P(-2, 52)[0] - 4.0, P(-2, 52)[1] - 4.0, "post Ø7", ha="right")
    s.text(*P(L + 5, -9), "FRONT", 2.6, weight="bold")
    s.arrow(P(L + 15, -8.2), P(L + 24, -8.2))

    sx, sy = 140.0, 150.0
    Q = lambda u, h: (sx + k * u, sy + k * h)
    s.view_label(sx - 11, 178, "SIDE VIEW (right side)")
    s.rect(*Q(0, 0), k * L, k * 11)
    s.rect(*Q(-5.5, 0), k * 7, k * 11, 0.35)
    s.line([Q(2, 5), Q(L - 1.95, 5)], 0.2, THIN, HID)
    s.dim_v(sy, Q(0, 5)[1], Q(L, 0)[0] + 7, Q(L, 0)[0], Q(L, 0)[0], "floor 5")
    s.dim_v(sy, Q(0, 11)[1], Q(L, 0)[0] + 24, Q(L, 0)[0], Q(L, 0)[0], "11 tall")

    s.view_label(130, 137, "HOLE LIST")
    s.text(130, 132.5, "from the back and right edges to the centre", 2.5)
    hole_table(s, 130, 126, [(r[0], r[1], r[2], r[3]) for r in TRAY_ROWS], cw=(10, 18, 18, 90), size=2.75)
    pic(s, "03", 150, 6, 112, "The part")
    return s


# 04 Front bumper
BUMP_PROF = [(7, 0), (0, 7), (0, 26.5), (9, 35.5), (12, 35.5), (12, 32.5), (10.24, 32.5), (3, 25.26), (3, 8.24), (11.24, 0)]


def bumper():
    s = Sheet("04", "Front bumper", "Print 1, front face down   |   Wall 3 thick   |   Edges rounded 0.9   |   Front corners chamfer 5 x 5")
    k, ox, oy = 2.0, 92.0, 98.0                  # 0,0 = front bottom corner of the profile; "in" runs to the left
    F = lambda d, h: (ox - k * d, oy + k * h)
    s.view_label(18, 181.5, "SIDE SHAPE (right side)")
    s.poly([F(*q) for q in BUMP_PROF], 0.55)
    off = {1: (-1, -4.2), 2: (1.4, -1), 3: (1.4, 0), 4: (0, 2), 5: (0.6, -3.4), 6: (-5.6, -3.4), 7: (-1.6, -4.4),
           8: (1.4, -1.2), 9: (1.4, 0), 10: (-2.0, -4.2)}
    for i, q in enumerate(BUMP_PROF, 1):
        x, y = F(*q)
        s.ax.add_patch(Circle((x, y), 0.45, color=INK, zorder=5))
        s.text(x + off[i][0], y + off[i][1], f"P{i}", 2.3, weight="bold")
    s.rect(*F(30, 16.5), k * 27, k * 4, 0.35)
    s.rect(*F(16, 32.5), k * 4, k * 3, 0.35)
    s.rect(*F(22, 35.5), k * 8.5, k * 3, 0.35)
    s.origin(*F(0, 0), right=True)
    s.dim_v(oy, F(0, 38.5)[1], ox + 9, F(22, 38.5)[0], ox, "38.5 tall")
    s.dim_h(F(30, 0)[0], ox, oy - 9, F(30, 16.5)[1], oy, "30 deep")
    s.text(*F(29, 22), "tongue", 2.3)
    s.text(*F(23.5, 36.4), "tab", 2.3, ha="right")

    s.view_label(14, 80, "SIDE SHAPE POINTS")
    s.text(14, 75.5, "in = from the front face,  up = from the bottom", 2.5)
    hole_table(s, 14, 70, [(f"P{i}", d, h, "") for i, (d, h) in enumerate(BUMP_PROF, 1)], per=5, cw=(9, 14, 14, 2),
               head=("pt", "in", "up", ""), size=2.7)

    k2, tx, ty = 1.5, 262.0, 126.0
    T = lambda d, y: (tx - k2 * d, ty + k2 * y)
    s.view_label(206, 178, "TOP VIEW")
    s.poly([T(12, -32), T(5, -32), T(0, -27), T(0, 27), T(5, 32), T(12, 32)])
    s.poly([T(12, 24), T(16, 24), T(16, -24), T(12, -24)], 0.35)
    s.poly([T(16, 10), T(30, 10), T(30, -10), T(16, -10)], 0.35)
    for sg in (1, -1):
        outline(s, [T(-q[0], q[1]) for q in rrect(-22, -13.5, sg * 17.5 - 3, sg * 17.5 + 3, 1.5)], 0.35)
        s.hole(*T(19, sg * 17.5), 3.4 * k2)
        s.hole(*T(22, sg * 6), 3.4 * k2)
    s.dim_v(T(0, -32)[1], T(0, 32)[1], tx + 8, tx, tx, "64")
    s.dim_h(T(5, 0)[0], tx, T(0, 32)[1] + 6, T(5, 32)[1], T(0, 27)[1], "5")
    s.dim_h(T(19, 0)[0], T(5, 0)[0], T(0, 32)[1] + 6, T(19, 17.5)[1], T(5, 32)[1], "14")
    s.dim_h(T(30, 0)[0], T(22, 0)[0], T(0, -32)[1] - 7, T(30, -10)[1], T(22, -6)[1], "8")
    s.dim_h(T(22, 0)[0], tx, T(0, -32)[1] - 7, T(22, -6)[1], T(0, -27)[1], "22")
    s.dim_v(T(0, -17.5)[1], T(0, 17.5)[1], T(30, 0)[0] - 11, T(19, 0)[0], T(19, 0)[0], "35")
    s.dim_v(T(0, -6)[1], T(0, 6)[1], T(30, 0)[0] - 4, T(22, 0)[0], T(22, 0)[0], "12")
    s.text(*T(7, -3), "FRONT", 2.4, weight="bold", rot=90)
    s.text(232, 66, "4 holes Ø3.4, through", 2.4, ha="center")

    s.text(*T(23, -1.2), "20 wide", 2.3, ha="center")
    s.view_label(14, 39, "ADDED PIECES  (out = from the centre line)")
    hole_table(s, 14, 33, [
        ("tongue", "3 to 30", "16.5 to 20.5", "20 wide, centred"),
        ("top lip", "12 to 16", "32.5 to 35.5", "48 wide, centred"),
        ("2 tabs", "13.5 to 22", "35.5 to 38.5", "6 wide, centred 17.5 out, corners r1.5"),
        ("2 middle braces", "triangle (12, 20.5) (3, 20.5) (3, 28.5)", "", "3 wide, from 5.5 to 8.5 out"),
        ("2 end braces", "(16, 32.5) (10.24, 32.5) (3, 25.26) (3, 18.5)", "", "3 wide, from 19.5 to 22.5 out")],
        cw=(28, 76, 26, 62), head=("piece", "in", "up", "width"), size=2.6)
    pic(s, "04", 114, 96, 80, "The part (from behind)")
    return s


# 05 Servo box
BOX_ROWS = [("1", 4, 14, "Ø7 post, Ø4.0 hole", "post up to the top inside, hole 6 up from the bottom"),
            ("2", 4, 34, "Ø7 post, Ø4.0 hole", "post up to the top inside, hole 6 up from the bottom"),
            ("3", 43, 11, "Ø7 post, Ø4.0 hole", "post up to the top inside, hole 6 up from the bottom"),
            ("4", 43, 37, "Ø7 post, Ø4.0 hole", "post up to the top inside, hole 6 up from the bottom"),
            ("5", 46, 6.5, "Ø6 post, Ø4.0 hole", "post hangs from the top, hole 8 down from the top"),
            ("6", 46, 41.5, "Ø6 post, Ø4.0 hole", "post hangs from the top, hole 8 down from the top"),
            ("S", 21, 29.2, "13.4 x 24 servo hole", "all the way through the top")]


def servo_box():
    s = Sheet("05", "Servo box", "Print 1, top face down   |   Open bottom   |   Corners r3, inside r1   |   Walls 2, top 2   |   Top edge 1 chamfer")
    k, ox, oy = 1.7, 34.0, 88.0
    P = lambda u, v: (ox + k * u, oy + k * v)
    L, Wd = 49.0, 48.0
    s.view_label(18, 182, "TOP VIEW")
    outline(s, [P(*q) for q in rrect(0, L, 0, Wd, 3)])
    outline(s, [P(*q) for q in rrect(1, L - 1, 1, Wd - 1, 2)], 0.2)
    outline(s, [P(*q) for q in rrect(2, L - 2, 2, Wd - 2, 1)], 0.2, HID, THIN)
    s.rect(*P(14.3, 17.2), k * 13.4, k * 24, 0.45)
    s.text(*P(21, 28.4), "S", 2.6, ha="center", weight="bold")
    for n, (u, v) in enumerate(((4, 14), (4, 34), (43, 11), (43, 37)), 1):
        s.circle(*P(u, v), 7 * k, 0.25); s.ax.patches[-1].set_linestyle(HID)
        s.circle(*P(u, v), 4 * k, 0.25); s.ax.patches[-1].set_linestyle(HID)
        tag(s, *P(u, v), str(n), 6.4 if u < 20 else -9.4, -1.0)
    for n, (u, v) in enumerate(((46, 6.5), (46, 41.5)), 5):
        s.circle(*P(u, v), 6 * k, 0.25); s.ax.patches[-1].set_linestyle(HID)
        s.hole(*P(u, v), 4 * k)
        tag(s, *P(u, v), str(n), -8.2, -1.0)
    s.origin(*P(0, 0), right=True)
    x0, y0 = P(0, 0); x1, y1 = P(L, Wd)
    s.dim_h(x0, x1, y1 + 8, y1, y1, "49 long")
    s.dim_v(y0, y1, x1 + 8, x1, x1, "48 wide")
    s.dim_h(P(14.3, 0)[0], P(27.7, 0)[0], y0 - 7, P(14.3, 17.2)[1], P(27.7, 17.2)[1], "13.4")
    s.dim_h(x0, P(14.3, 0)[0], y0 - 7, y0, P(14.3, 17.2)[1], "14.3")
    s.dim_v(P(0, 17.2)[1], P(0, 41.2)[1], x0 - 8, x0, P(14.3, 0)[0], "24")
    s.dim_v(y0, P(0, 17.2)[1], x0 - 8, x0, P(14.3, 0)[0], "17.2")
    s.text(*P(L + 1, -9), "FRONT", 2.6, weight="bold")

    sx, sy = 34.0, 22.0
    Q = lambda u, h: (sx + k * u, sy + k * h)
    s.view_label(sx, sy + 32, "SIDE VIEW (right side)")
    s.poly([Q(0, 0), Q(L, 0), Q(L, 10), Q(L - 1, 11), Q(1, 11), Q(0, 10)])
    s.line([Q(2, 0), Q(2, 9), Q(L - 2, 9), Q(L - 2, 0)], 0.2, THIN, HID)
    s.dim_v(sy, Q(0, 11)[1], Q(L, 0)[0] + 7, Q(L, 0)[0], Q(L, 0)[0], "11 tall")
    s.dim_v(Q(0, 9)[1], Q(0, 11)[1], sx - 6, Q(2, 0)[0], sx, "top 2 thick")

    s.view_label(140, 179, "HOLE LIST")
    s.text(140, 174.5, "from the back and right edges to the centre", 2.5)
    hole_table(s, 140, 168, [
        ("1", 4, 14, "Ø7 full-height post, Ø4.0 hole 6 deep from bottom"),
        ("2", 4, 34, "Ø7 full-height post, Ø4.0 hole 6 deep from bottom"),
        ("3", 43, 11, "Ø7 full-height post, Ø4.0 hole 6 deep from bottom"),
        ("4", 43, 37, "Ø7 full-height post, Ø4.0 hole 6 deep from bottom"),
        ("5", 46, 6.5, "Ø6 post 3 long under the top, Ø4.0 hole 8 deep"),
        ("6", 46, 41.5, "Ø6 post 3 long under the top, Ø4.0 hole 8 deep"),
        ("S", 21, 29.2, "13.4 x 24 servo hole, through the top")], cw=(7, 18, 18, 92), size=2.75)
    pic(s, "05", 152, 8, 112, "The part (from below)")
    return s


# 06 Antenna
def antenna():
    s = Sheet("06", "Antenna", "Print 1, lying on its side")
    k, ox, oy = 3.0, 34.0, 150.0
    A = lambda u, r: (ox + k * u, oy + k * r)
    s.view_label(ox, 178, "SIDE VIEW")
    s.rect(*A(0, -1.45), k * 7.8, k * 2.9)
    s.rect(*A(7.8, -2.6), k * 2, k * 5.2)
    s.poly([A(9.8, -1.6), A(53.4, -1.1), A(53.4, 1.1), A(9.8, 1.6)])
    s.circle(*A(55.8, 0), 5 * k, 0.45)
    s.line([A(-2, 0), A(60.5, 0)], 0.13, THIN, (0, (6, 1.5, 1, 1.5)))
    s.dim_h(A(0, 0)[0], A(7.8, 0)[0], oy - 14, A(0, -1.45)[1], A(7.8, -2.6)[1], "7.8")
    s.dim_h(A(7.8, 0)[0], A(9.8, 0)[0], oy - 14, A(7.8, -2.6)[1], A(9.8, -2.6)[1], "2")
    s.dim_h(A(9.8, 0)[0], A(55.8, 0)[0], oy - 14, A(9.8, -2.6)[1], A(55.8, 0)[1], "46 to ball centre")
    s.dim_h(A(0, 0)[0], A(58.3, 0)[0], oy - 22, A(0, -1.45)[1], A(58.3, 0)[1], "58.3 long")
    s.callout(A(4, 0)[0] + 2, oy + 16, A(4, 1.45)[0], A(4, 1.45)[1], "peg Ø2.9")
    s.callout(A(9, 0)[0] + 9, oy + 22, A(8.8, 2.6)[0], A(8.8, 2.6)[1], "collar Ø5.2")
    s.callout(A(20, 0)[0], oy + 16, A(14, 1.55)[0], A(14, 1.55)[1], "mast Ø3.2, tapers to Ø2.2 at the top")
    s.callout(A(50, 0)[0], oy + 16, A(55.8, 1.8)[0], A(55.8, 1.8)[1], "ball Ø5", ha="right")
    pic(s, "06", 40, 4, 120, "The part")
    return s


# 07 Tow hook
def hook():
    s = Sheet("07", "Tow hook", "Print 1, on its flat bottom   |   Edges rounded 0.8")
    k, ox, oy = 3.0, 132.0, 122.0
    S_ = lambda b, h: (ox - k * b, oy + k * h)
    s.view_label(18, 178, "SIDE VIEW (right side)")
    pts = [(0, 0), (20.5, 0)]
    pts += [(20.5 + 7 * math.sin(math.radians(a)), 7 - 7 * math.cos(math.radians(a))) for a in range(10, 91, 10)]
    pts += [(27.5, 11.5), (23.5, 11.5)]
    pts += [(20.5 + 3 * math.sin(math.radians(a)), 7 - 3 * math.cos(math.radians(a))) for a in range(90, -1, -10)]
    pts += [(0, 4)]
    s.poly([S_(*q) for q in pts])
    s.circle(*S_(25.5, 11.5), 5.6 * k, 0.45)
    s.cross(*S_(20.5, 7), 2.0)
    s.origin(*S_(0, 0), right=True)
    for b in (4.5, 11.5):
        for e in (-1.7, 1.7):
            s.line([S_(b + e, 0), S_(b + e, 4)], 0.18, THIN, HID)
    s.line([S_(15.5, 0), S_(15.5, 4)], 0.2, THIN)
    s.dim_h(S_(20.5, 0)[0], ox, oy - 17, S_(20.5, 7)[1], oy, "20.5")
    s.dim_h(S_(15.5, 0)[0], ox, oy - 9, oy, oy, "pad 15.5")
    s.dim_h(S_(28.3, 0)[0], ox, oy - 25, S_(28.3, 11.5)[1], oy, "28.3 long")
    s.dim_v(oy, S_(0, 4)[1], ox + 7, ox, ox, "4 thick")
    s.dim_v(oy, S_(0, 7)[1], ox + 24, S_(20.5, 7)[0], ox, "7")
    s.dim_v(oy, S_(0, 11.5)[1], S_(28.3, 0)[0] - 8, S_(25.5, 11.5)[0], S_(28.3, 0)[0], "11.5")
    s.dim_h(S_(27.5, 0)[0], S_(23.5, 0)[0], S_(0, 14.3)[1] + 8, S_(27.5, 11.5)[1], S_(23.5, 11.5)[1], "4")
    s.callout(S_(10, 0)[0], oy + 34, S_(23.5, 7)[0] + 0.5, S_(23.5, 7)[1], "bend R3 inside, R7 outside")
    s.callout(S_(28.3, 0)[0] - 4, oy + 42, S_(25.5, 11.5)[0] - 6.0, S_(25.5, 11.5)[1] + 5.0, "knob Ø5.6, 9 long", ha="right")

    ty = 52.0
    T = lambda b, y: (ox - k * b, ty + k * y)
    s.view_label(18, 82, "TOP VIEW")
    outline(s, [T(-q[0], q[1]) for q in rrect(-15.5, 0, -7, 7, 3)])
    s.poly([T(15.5, -4.5), T(28.3, -4.5), T(28.3, 4.5), T(15.5, 4.5)])
    s.line([T(22.7, -4.5), T(22.7, 4.5)], 0.25)
    for b in (4.5, 11.5):
        s.hole(*T(b, 0), 3.4 * k)
    s.dim_v(T(0, -7)[1], T(0, 7)[1], ox + 8, ox, ox, "pad 14 wide")
    s.dim_v(T(0, -4.5)[1], T(0, 4.5)[1], T(28.3, 0)[0] - 8, T(28.3, 0)[0], T(28.3, 0)[0], "hook 9 wide")
    s.dim_h(T(4.5, 0)[0], ox, ty - 26, T(4.5, 0)[1], ty - 21, "4.5")
    s.dim_h(T(11.5, 0)[0], T(4.5, 0)[0], ty - 26, T(11.5, 0)[1], T(4.5, 0)[1], "7")
    s.callout(ox + 14, ty + 26, T(4.5, 0)[0] + 3.6, T(4.5, 0)[1] + 3.6, "2 holes Ø3.4, through, centred")
    s.text(ox + 4, ty - 32, "FRONT", 2.6, weight="bold")
    s.arrow((ox + 18, ty - 31), (ox + 30, ty - 31))

    pic(s, "07", 186, 12, 88, "The part")
    return s


SHEETS = {"plate": plate, "beam": beam, "tray": tray, "bumper": bumper, "box": servo_box, "antenna": antenna, "hook": hook}


def save(s, pdf=None):
    """write the page to its own PDF (and to the all-parts PDF when one is open)"""
    probs = s.check()
    path = os.path.join(OUT, FOLDERS[s.num] + ".pdf")
    s.fig.savefig(path)
    if pdf:
        pdf.savefig(s.fig)
    plt.close(s.fig)
    print(f"wrote {FOLDERS[s.num]}.pdf ({len(probs)} collisions)")
    for q in probs:
        print("   ", q)


if __name__ == "__main__":
    names = sys.argv[1:]
    if names:
        for n in names:
            save(SHEETS[n]())
    else:
        with PdfPages(os.path.join(OUT, "all-parts.pdf")) as pdf:
            for make in SHEETS.values():
                save(make(), pdf)
        print("wrote all-parts.pdf")
