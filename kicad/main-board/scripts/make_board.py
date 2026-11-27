"""Build main-board.kicad_pcb from design.py.

Run with KiCad's own Python:
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3 scripts/make_board.py

Drawing rules: the perf board itself carries no text. Row letters and
column numbers sit outside the board edge; every other label is printed
on the part it belongs to.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from design import PARTS, WIRES, ROWS, rc, check

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the KiCad project folder
FP = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints"
LIB = {
    "socket8": ("Connector_PinSocket_2.54mm", "PinSocket_1x08_P2.54mm_Vertical"),
    "socket6": ("Connector_PinSocket_2.54mm", "PinSocket_1x06_P2.54mm_Vertical"),
    "term2":   ("TerminalBlock_Phoenix", "TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal"),
    "header3": ("Connector_PinHeader_2.54mm", "PinHeader_1x03_P2.54mm_Horizontal"),
    "cap":     ("Capacitor_THT", "CP_Radial_D8.0mm_P5.00mm"),
    "res":     ("Resistor_THT", "R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal"),
}
P = 2.54
W, H = 50.0, 70.0
OX, OY = 100.0, 100.0
X0 = OX + (W - 17 * P) / 2          # column 1
Y0 = OY + (H - 23 * P) / 2          # row X (front) at the top of the drawing
F, B = pcbnew.F_SilkS, pcbnew.B_SilkS
LABEL = pcbnew.Cmts_User            # white text printed on parts (drawn above the bodies)
DIM = DARK = LABEL                  # every label is white
# KiCad paints User.1 on top of User.2 on top of User.3 ..., so parts that sit
# on top of other parts (resistor bodies, metal bits) get the lowest numbers.
(RES, METAL, PLASTIC, CAP, TERM, M360, DRV, ESP, CHIP) = (
    pcbnew.User_1, pcbnew.User_2, pcbnew.User_3, pcbnew.User_4, pcbnew.User_5,
    pcbnew.User_6, pcbnew.User_7, pcbnew.User_8, pcbnew.User_9)

def mm(v): return pcbnew.FromMM(v)
def V(x, y): return pcbnew.VECTOR2I(mm(x), mm(y))
def gx(c): return X0 + (c - 1) * P
def gy(r): return Y0 + (23 - r) * P
def xy(hole):
    r, c = rc(hole); return gx(c), gy(r)
def pt(hole): return V(*xy(hole))
def R(letter): return ROWS.index(letter)

errors, *_ = check()
if errors:
    sys.exit("design.py has errors:\n" + "\n".join(errors))

board = pcbnew.BOARD()
nets = {}
def net(name):
    if name not in nets:
        n = pcbnew.NETINFO_ITEM(board, name); board.Add(n); nets[name] = n
    return nets[name]

def shape(layer, kind, a, b, width=0.15, filled=False):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(kind); s.SetLayer(layer); s.SetWidth(mm(width))
    s.SetStart(a); s.SetEnd(b)
    if filled: s.SetFilled(True)
    board.Add(s); return s
COVER = []   # areas hidden under a part body: no empty holes drawn there
EDGE = pcbnew.Eco2_User             # thin outline drawn around each part body
def solid(layer, x1, y1, x2, y2):
    COVER.append(("rect", min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)))
    a, b = V(min(x1, x2), min(y1, y2)), V(max(x1, x2), max(y1, y2))
    if layer in (ESP, DRV, M360, TERM, RES, PLASTIC):
        shape(EDGE, pcbnew.SHAPE_T_RECT, a, b, 0.12)
    return shape(layer, pcbnew.SHAPE_T_RECT, a, b, 0.1, True)
def cells(layer, c1, c2, r1, r2):
    return solid(layer, gx(c1), gy(r1), gx(c2), gy(r2))
def disc(layer, x, y, rad):
    COVER.append(("disc", x, y, rad))
    if layer == CAP:
        shape(EDGE, pcbnew.SHAPE_T_CIRCLE, V(x, y), V(x + rad, y), 0.12)
    return shape(layer, pcbnew.SHAPE_T_CIRCLE, V(x, y), V(x + rad, y), 0.1, True)
def outline_bottom(c1, c2, r1, r2):
    shape(B, pcbnew.SHAPE_T_RECT, V(gx(c1), gy(r2)), V(gx(c2), gy(r1)), 0.2)

def text_on(t, x, y, layer=None, **k):
    return text(t, x, y, layer=LABEL if layer is None else layer, **k)

FONT = "Helvetica Neue"
def text(t, x, y, layer=F, size=1.0, bold=False, angle=0, align=0):
    o = pcbnew.PCB_TEXT(board)
    o.SetText(t); o.SetLayer(layer)
    o.SetPosition(V(x, y))
    o.SetTextSize(V(size, size))
    o.SetTextThickness(mm(size * 0.12))
    o.SetUnresolvedFontName(FONT); o.ResolveFont(None)
    o.SetBold(bold)
    if layer == B: o.SetMirrored(True)       # back-side text reads right when the board is flipped
    if angle: o.SetTextAngleDegrees(angle)
    if align < 0: o.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
    if align > 0: o.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_RIGHT)
    board.Add(o); return o

# ---- board outline, empty holes, grid labels outside the edge -----------
shape(pcbnew.Edge_Cuts, pcbnew.SHAPE_T_RECT, V(OX, OY), V(OX + W, OY + H), 0.15)
SERVO_ROWS = {"T", "U", "V"}         # servo pins stick out over the left edge there
for r in range(24):
    if ROWS[r] not in SERVO_ROWS:
        text(ROWS[r], OX - 1.6, gy(r), size=0.8)
    text(ROWS[r], OX + W + 1.6, gy(r), size=0.8)
for c in range(1, 19):
    text(str(c), gx(c), OY - 1.5, size=0.8)
    text(str(c), gx(c), OY + H + 1.5, size=0.8)
text("FRONT", OX + W / 2, OY - 3.6, size=0.9, bold=True)
text("BACK", OX + W / 2, OY + H + 3.6, size=0.9, bold=True)
# same grid labels on the back silk, so View > Flip Board View is readable too
for r in range(24):
    if ROWS[r] not in SERVO_ROWS:
        text(ROWS[r], OX - 1.6, gy(r), layer=B, size=0.8)
    text(ROWS[r], OX + W + 1.6, gy(r), layer=B, size=0.8)
for c in range(1, 19):
    text(str(c), gx(c), OY - 1.5, layer=B, size=0.8)
    text(str(c), gx(c), OY + H + 1.5, layer=B, size=0.8)
text("FRONT", OX + W / 2, OY - 3.6, layer=B, size=0.9, bold=True)
text("BACK", OX + W / 2, OY + H + 3.6, layer=B, size=0.9, bold=True)

# ---- parts --------------------------------------------------------------
def mini360(ref, pins):
    fp = pcbnew.FOOTPRINT(board)
    fp.SetFPID(pcbnew.LIB_ID("aliftmobile", "Mini360"))
    fp.SetReference(ref); fp.SetValue("Mini360")
    for name, hole, _ in pins:
        p = pcbnew.PAD(fp)
        p.SetShape(pcbnew.PAD_SHAPE_CIRCLE); p.SetAttribute(pcbnew.PAD_ATTRIB_PTH)
        p.SetSize(V(1.8, 1.8)); p.SetDrillSize(V(1.0, 1.0))
        p.SetLayerSet(p.PTHMask()); p.SetNumber(name)
        fp.Add(p); p.SetPosition(pt(hole))
    board.Add(fp); return fp

KEEP, FPS = [], []
for ref, (kind, label, pins) in PARTS.items():
    if kind == "mini360":
        fp = mini360(ref, pins)
    else:
        lib, name = LIB[kind]
        target = [xy(h) for _, h, _ in pins]
        fp = None
        for deg in (0, 90, 180, 270):
            cand = pcbnew.FootprintLoad(os.path.join(FP, lib + ".pretty"), name)
            cand.SetOrientationDegrees(deg)
            pads = sorted(cand.Pads(), key=lambda p: int(p.GetNumber()))
            p1 = pads[0].GetPosition()
            cand.SetPosition(cand.GetPosition() + pcbnew.VECTOR2I(mm(target[0][0]) - p1.x, mm(target[0][1]) - p1.y))
            if all(abs(pcbnew.ToMM(p.GetPosition().x) - tx) < 0.2 and abs(pcbnew.ToMM(p.GetPosition().y) - ty) < 0.2
                   for p, (tx, ty) in zip(pads, target)):
                fp = cand; break
        assert fp, f"no rotation fits {ref}"
        for p, (pin, hole, _) in zip(pads, pins):
            p.SetNumber(pin)
        fp.SetReference(ref); fp.SetValue(label)
        # the solid bodies below replace the library drawings; keep only the courtyard
        for item in list(fp.GraphicalItems()):
            if item.GetLayer() not in (pcbnew.F_CrtYd, pcbnew.B_CrtYd) or isinstance(item, pcbnew.PCB_TEXT):
                fp.Remove(item); KEEP.append(item)   # keep a reference so SWIG does not free it
        board.Add(fp)
    for p in fp.Pads():
        for pin, hole, n in pins:
            if p.GetNumber() == pin and n:
                p.SetNet(net(n))
    if kind in ("socket8", "socket6", "header3", "res", "cap", "mini360"):
        for p in fp.Pads():
            p.SetSize(V(1.8, 1.8)); p.SetDrillSize(V(0.9, 0.9))
            p.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
    fp.Reference().SetVisible(False)
    fp.Value().SetVisible(False)
    FPS.append(fp)

# ---- solid bodies, one User layer per material ---------------------------
BODY = {ESP: "ESP32 board", DRV: "Driver board", M360: "Mini360 board", TERM: "Screw terminals",
        CAP: "Capacitor", RES: "Resistors", METAL: "Metal parts", CHIP: "Chips", PLASTIC: "Plastic headers"}
ls = board.GetEnabledLayers()
for L in BODY: ls.AddLayer(L)
board.SetEnabledLayers(ls)
for L, name in BODY.items(): board.SetLayerName(L, name)

# Labels that would sit on a 47k leg (R15, U15) move toward the lower column;
# their neighbours move a little too so the names stay apart.
SIDESTEP = {"U1A.G9": -1.5, "U1A.G8": -0.6, "U1B.G3": -1.5, "U1B.G4": -0.6}

def pin_labels(ref, inward, size, gap=1.75):
    """Pin names on the module body. Used pins bright, unused pins grey."""
    for pin, hole, n in PARTS[ref][2]:
        x, y = xy(hole)
        sz = size * 0.8 if len(pin) > 3 else size
        text_on(pin, x + SIDESTEP.get(f"{ref}.{pin}", 0), y + inward * gap, size=sz)

# ESP32-C3 SuperMini (22.5 x 18 mm), USB-C toward column 11
cells(ESP, 10.07, 18.93, R("Q") - 0.54, R("W") + 0.54)
cells(METAL, 9.4, 10.9, R("S") + 0.15, R("U") - 0.15)
text_on("ESP32-C3", gx(17.0), gy(R("T")) + 0.4, size=1.0, bold=True)   # right of the 47k
text_on("USB-C", gx(10.25), gy(R("U")) + 0.2, size=0.5, angle=90)
pin_labels("U1A", -1, 0.55)
pin_labels("U1B", +1, 0.55, gap=1.75 + P)   # one row further in: the 10k lies right under this row
outline_bottom(10.07, 18.93, R("Q") - 0.54, R("W") + 0.54)

# HW-627 motor driver
cells(DRV, 10.2, 16.8, R("H") - 0.6, R("N") + 0.6)
text_on("DRV8833 MOTOR DRIVER", gx(13.5), gy(R("J")) - 0.4, size=0.75, bold=True)
text_on("HW-627", gx(13.5), gy(R("I")) - 0.2, size=0.6)
pin_labels("U2A", +1, 0.55)
pin_labels("U2B", -1, 0.55)
outline_bottom(10.2, 16.8, R("H") - 0.6, R("N") + 0.6)

# Mini360 with its adjust screw
cells(M360, 2.8, 7.2, R("F") - 0.6, R("L") + 0.6)
disc(METAL, gx(5), gy(R("K")) - 0.4, 0.9)
text_on("MINI360", gx(5), gy(R("I")) + 0.1, size=0.8, angle=90, bold=True)
text_on("BUCK  5.0 V OUT", gx(5.9), gy(R("I")) + 0.1, size=0.5, angle=90)
for lbl, hole, dy in [("IN+", "F7", -1), ("IN-", "F3", -1), ("OUT+", "L7", 1), ("OUT-", "L3", 1)]:
    x, y = xy(hole)
    text_on(lbl, x, y + dy * 1.75, size=0.55)
outline_bottom(2.8, 7.2, R("F") - 0.6, R("L") + 0.6)

# screw terminals: green block, screw heads, name and + / - on the block
for ref, name, signs in [("J1", "BATT", ("−", "+")), ("J2", "LEFT MOTOR", ("", "")), ("J3", "RIGHT MOTOR", ("", ""))]:
    (x1, y1), (x2, _) = xy(PARTS[ref][2][0][1]), xy(PARTS[ref][2][1][1])
    left, right, top, bottom = x1 - 2.72, x2 + 2.72, y1 - 5.38, y1 + 5.39
    solid(TERM, left, top, right, bottom)
    for x, s in zip((x1, x2), signs):
        disc(METAL, x, y1 - 2.6, 1.15)
        if s: text_on(s, x, bottom - 1.1, size=0.9, bold=True)
    text_on(name, (x1 + x2) / 2, bottom - 1.1, size=0.6, bold=True)
    shape(B, pcbnew.SHAPE_T_RECT, V(left, top), V(right, bottom), 0.2)

# servo header: plastic spacer, pins bent out past the left edge
sx = xy("T2")[0]
solid(PLASTIC, sx - 4.0, gy(R("V")) - 1.27, sx - 1.5, gy(R("T")) + 1.27)
for pin, hole, _ in PARTS["J4"][2]:
    x, y = xy(hole)
    solid(METAL, OX - 4.5, y - 0.32, sx - 4.0, y + 0.32)      # pin sticking out
    solid(METAL, sx - 1.5, y - 0.32, x - 0.9, y + 0.32)        # pin into the board
    text_on(pin, OX - 5.0, y, size=0.55, align=1)
text_on("SERVO", sx - 2.75, gy(R("U")), size=0.55, angle=90, bold=True)

# 470uF capacitor: can, minus stripe, value, + mark
(cxm, cy), (cxp, _) = xy("P1"), xy("P3")
cx = (cxm + cxp) / 2
disc(CAP, cx, cy, 4.0)
solid(METAL, cx - 3.6, cy - 1.6, cx - 3.0, cy + 1.6)
text_on("−", cxm, cy - 2.3, size=0.9, bold=True)
text_on("+", cxp, cy - 2.3, size=0.9, bold=True)
text_on("470 µF", cx, cy + 2.4, size=0.55)

# resistors: beige body with silver legs and the value printed on it
for ref in ("R1", "R2"):
    (a, b) = [xy(h) for _, h, _ in PARTS[ref][2]]
    val = PARTS[ref][1]
    if abs(a[0] - b[0]) < 0.1:
        lo, hi = min(a[1], b[1]), max(a[1], b[1])
        solid(METAL, a[0] - 0.25, lo, a[0] + 0.25, lo + 1.2); solid(METAL, a[0] - 0.25, hi - 1.2, a[0] + 0.25, hi)
        solid(RES, a[0] - 1.25, min(a[1], b[1]) + 1.2, a[0] + 1.25, max(a[1], b[1]) - 1.2)
        text_on(val, a[0], (a[1] + b[1]) / 2 + 0.6, size=0.55, angle=90, layer=DARK)
    else:
        lo, hi = min(a[0], b[0]), max(a[0], b[0])
        solid(METAL, lo, a[1] - 0.25, lo + 1.2, a[1] + 0.25); solid(METAL, hi - 1.2, a[1] - 0.25, hi, a[1] + 0.25)
        solid(RES, min(a[0], b[0]) + 1.2, a[1] - 1.25, max(a[0], b[0]) - 1.2, a[1] + 1.25)
        text_on(val, (a[0] + b[0]) / 2, a[1], size=0.55, layer=DARK)

# ---- empty perf board holes, except where a part covers them ----------
def covered(x, y):
    for k in COVER:
        if k[0] == "rect" and k[1] - 0.3 <= x <= k[3] + 0.3 and k[2] - 0.3 <= y <= k[4] + 0.3: return True
        if k[0] == "disc" and (x - k[1]) ** 2 + (y - k[2]) ** 2 <= (k[3] + 0.3) ** 2: return True
    return False
for r in range(24):
    for c in range(1, 19):
        x, y = gx(c), gy(r)
        if not covered(x, y):
            shape(pcbnew.Dwgs_User, pcbnew.SHAPE_T_CIRCLE, V(x, y), V(x + 0.45, y), 0.1)

# ---- wires --------------------------------------------------------------
pad_holes = {h for _, (_, _, pins) in PARTS.items() for _, h, _ in pins}
for n, runs in WIRES.items():
    for side, holes in runs:
        layer = pcbnew.B_Cu if side == "bottom" else pcbnew.F_Cu
        corners = [holes[0]]
        for i in range(1, len(holes) - 1):
            (r0, c0), (r1, c1), (r2, c2) = rc(holes[i - 1]), rc(holes[i]), rc(holes[i + 1])
            if (r1 - r0, c1 - c0) != (r2 - r1, c2 - c1):
                corners.append(holes[i])
        corners.append(holes[-1])
        for a, b in zip(corners, corners[1:]):
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(pt(a)); t.SetEnd(pt(b)); t.SetWidth(mm(0.6))
            t.SetLayer(layer); t.SetNet(net(n)); board.Add(t)
        if side == "top":
            for end in (holes[0], holes[-1]):
                if end in pad_holes: continue
                v = pcbnew.PCB_VIA(board)
                v.SetPosition(pt(end)); v.SetDrill(mm(0.6)); v.SetWidth(mm(1.2))
                v.SetNet(net(n)); board.Add(v)

# ---- check: no label may touch a pad, via, top wire or another label ----
def rect_of(item):
    bb = item.GetBoundingBox()
    return [pcbnew.ToMM(v) for v in (bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom())]
def seg_rect_dist(ax, ay, bx, by, r):
    best = 1e9
    for i in range(41):
        x = ax + (bx - ax) * i / 40; y = ay + (by - ay) * i / 40
        dx = max(r[0] - x, 0, x - r[2]); dy = max(r[1] - y, 0, y - r[3])
        best = min(best, (dx * dx + dy * dy) ** 0.5)
    return best
labels = [t for t in board.GetDrawings() if isinstance(t, pcbnew.PCB_TEXT) and t.GetLayer() in (LABEL, DIM, DARK)]
problems = []
for t in labels:
    r = rect_of(t)
    for fp in FPS:
        for p in fp.Pads():
            c = p.GetPosition(); rad = pcbnew.ToMM(p.GetSize().x) / 2
            if seg_rect_dist(pcbnew.ToMM(c.x), pcbnew.ToMM(c.y), pcbnew.ToMM(c.x), pcbnew.ToMM(c.y), r) < rad + 0.05:
                problems.append(f"'{t.GetText()}' touches pad {fp.GetReference()}.{p.GetNumber()}")
    for tr in board.GetTracks():
        if tr.GetLayer() != pcbnew.F_Cu and not isinstance(tr, pcbnew.PCB_VIA): continue
        a, b = tr.GetStart(), tr.GetEnd(); w = pcbnew.ToMM(tr.GetWidth(pcbnew.F_Cu) if isinstance(tr, pcbnew.PCB_VIA) else tr.GetWidth()) / 2
        if seg_rect_dist(pcbnew.ToMM(a.x), pcbnew.ToMM(a.y), pcbnew.ToMM(b.x), pcbnew.ToMM(b.y), r) < w + 0.05:
            problems.append(f"'{t.GetText()}' touches top wire/via {tr.GetNetname()}")
for i, t in enumerate(labels):
    for u in labels[i + 1:]:
        a, b = rect_of(t), rect_of(u)
        if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
            problems.append(f"'{t.GetText()}' overlaps '{u.GetText()}'")
print("label problems:", len(problems)); print("\n".join(problems))

ds = board.GetDesignSettings()
ds.m_TrackMinWidth = mm(0.25)
ds.SetCopperLayerCount(2)

out = os.path.join(HERE, "main-board.kicad_pcb")
pcbnew.SaveBoard(out, board)
pro = os.path.join(HERE, "main-board.kicad_pro")
if not os.path.exists(pro):
    json.dump({"meta": {"filename": "main-board.kicad_pro", "version": 3}}, open(pro, "w"), indent=2)
print("wrote", out)
