# Builds the 3D model of the RC car (every part, screw and wire) and saves it as blender/rc_car.blend.
#
#   Build:  Blender --background --factory-startup --python blender/scripts/build_model.py
#   Check:  Blender --background --factory-startup --python blender/scripts/build_model.py -- --check
#
# The check looks for parts that run into each other (wheels straight, full left and full right),
# wires that lie in each other, and wire ends that are not on their part.
#
# Units are mm. X points forward, Y points left, Z points up.
# The car is built with the plate at z 14 to 18, then everything is lifted by LIFT at the end so the
# tires sit on the ground (z 0). So while building, the ground is at z = -LIFT.
import bpy, bmesh, math, os, sys
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "rc_car.blend"))   # blender/rc_car.blend

# Main sizes
R = 21.5                         # wheel radius (RecDec N20 wheel, 43 across, 19 wide)
TW = 19.0                        # tire width
LIFT = 12.5                      # how far the whole car is lifted at the end
AZ = R - LIFT                    # axle height while building (9, under the plate)
XF, XR = 56.0, -64.0             # front axle (steers) and rear axle (driven), 120 apart
PZ0, PZ = 14.0, 18.0             # plate bottom and top
LIPO = (55.0, 30.0, 16.0)        # battery size
PB0, PB1, PBY = -50.0, 20.0, 25.0   # perf board: back edge x, front edge x, half width
PBZ0 = PZ + 6.0                  # perf board bottom (it sits on 4 posts printed on the plate)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.unit_settings.system = "METRIC"; sc.unit_settings.scale_length = 0.001; sc.unit_settings.length_unit = "MILLIMETERS"

# Colors
def mat(name, rgb, metal=0.0, rough=0.5):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rough
    m.diffuse_color = (*rgb, 1)
    return m

M = dict(
    # printed parts
    plate=mat("Plate charcoal", (0.06, 0.065, 0.075), 0, 0.45),
    plow=mat("Gunmetal grey", (0.20, 0.21, 0.23), 0.15, 0.38),        # bumper, steering beam, tow hook
    tray=mat("Tray gunmetal", (0.20, 0.21, 0.23), 0.15, 0.38),
    sbox=mat("Satin black", (0.022, 0.022, 0.025), 0, 0.32),
    stripe=mat("Stripe black", (0.008, 0.008, 0.01), 0, 0.65),        # tape on the bumper
    # bought parts
    term=mat("Terminal green", (0.05, 0.45, 0.2), 0, 0.5),
    hub=mat("Hub white", (0.8, 0.8, 0.78)),
    lipo=mat("Battery wrap black", (0.025, 0.025, 0.03), 0, 0.35),
    lipo_end=mat("Battery end teal", (0.18, 0.28, 0.28), 0, 0.5),
    label=mat("Label orange", (0.95, 0.45, 0.04), 0, 0.4),
    plugw=mat("Plug white", (0.92, 0.92, 0.88)),
    pad=mat("Pad copper", (0.85, 0.7, 0.45), 0.9, 0.3),
    tin=mat("Tinned wire", (0.75, 0.75, 0.78), 0.9, 0.3),
    tire=mat("Tire rubber", (0.015, 0.015, 0.015), 0, 0.9),
    steel=mat("Steel", (0.6, 0.6, 0.62), 0.9, 0.3),
    brass=mat("Motor brass", (0.75, 0.6, 0.3), 0.8, 0.35),
    pcb=mat("PCB green", (0.05, 0.25, 0.12)),
    pcbb=mat("PCB blue", (0.05, 0.1, 0.45)),
    white=mat("Print white", (0.85, 0.83, 0.78)),
    blk=mat("Plastic black", (0.02, 0.02, 0.02)),
    servo=mat("Servo blue", (0.1, 0.15, 0.5)),
    # wires
    red=mat("Wire red", (0.8, 0.05, 0.05)), black=mat("Wire black", (0.01, 0.01, 0.01)),
    orange=mat("Wire orange", (0.9, 0.4, 0.05)), brown=mat("Wire brown", (0.35, 0.18, 0.06)),
    white_w=mat("Wire white", (0.9, 0.9, 0.9)),
)
M.update(res=mat("Resistor tan", (0.78, 0.66, 0.45)), c3=mat("ESP32-C3 board blue", (0.05, 0.12, 0.4)))

# Collections (folders in the Blender outliner)
def coll(name):
    c = bpy.data.collections.new(name)
    sc.collection.children.link(c)
    return c

C_PRINT, C_BUY, C_HW, C_WIRE, C_HELP = coll("Printed"), coll("Bought"), coll("Screws and nuts"), coll("Wires"), coll("Helpers")
CUR = [C_PRINT]          # new objects go into this collection

# Shape helpers
def mesh_obj(name, bm, m):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me)
    CUR[0].objects.link(o)
    me.materials.append(m)
    return o

def box(name, x0, x1, y0, y1, z0, z1, m):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1)
    bmesh.ops.scale(bm, vec=(x1 - x0, y1 - y0, z1 - z0), verts=bm.verts)
    bmesh.ops.translate(bm, vec=((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), verts=bm.verts)
    return mesh_obj(name, bm, m)

def cyl(name, c, r, d, axis="z", m=None, n=32, r2=None):
    """cylinder centred at c, radius r, length d along axis. r2 makes it taper to that radius at the + end."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=n, radius1=r, radius2=r if r2 is None else r2, depth=d)
    rot = {"x": Matrix.Rotation(math.pi / 2, 4, "Y"), "y": Matrix.Rotation(-math.pi / 2, 4, "X"), "z": Matrix()}[axis]
    bmesh.ops.transform(bm, matrix=Matrix.Translation(c) @ rot, verts=bm.verts)
    return mesh_obj(name, bm, m)

def ball(c, r, m):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=r)
    bmesh.ops.translate(bm, vec=c, verts=bm.verts)
    return mesh_obj("ball", bm, m)

def bake(o):
    """move the object's position into its points, so the object itself sits at 0,0,0"""
    o.data.transform(o.matrix_world); o.matrix_world = Matrix()

def cyl2(name, p0, p1, r, m, n=24):
    """cylinder from point p0 to point p1"""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    o = cyl(name, (0, 0, 0), r, d.length, "z", m, n)
    o.matrix_world = Matrix.Translation((p0 + p1) / 2) @ d.to_track_quat("Z", "Y").to_matrix().to_4x4()
    bake(o)
    return o

def prism(name, pts, z0, z1, m):
    """flat outline pts (x, y), pulled up from z0 to z1"""
    bm = bmesh.new()
    vb = [bm.verts.new((x, y, z0)) for x, y in pts]
    vt = [bm.verts.new((x, y, z1)) for x, y in pts]
    bm.faces.new(vb[::-1]); bm.faces.new(vt)
    n = len(pts)
    for i in range(n):
        bm.faces.new((vb[i], vb[(i + 1) % n], vt[(i + 1) % n], vt[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_obj(name, bm, m)

def xz_prism(name, pts, y0, y1, m):
    """outline pts drawn as (x, z) from the side, pulled sideways from y0 to y1"""
    o = prism(name, pts, y0, y1, m)
    o.data.transform(Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1))))   # swap y and z
    o.data.flip_normals()
    return o

def rrect(x0, x1, y0, y1, r, n=6):
    """outline of a rectangle with round corners of radius r"""
    pts = []
    for cx, cy, a0 in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
        pts += [(cx + r * math.cos(math.radians(a0 + 90 * i / n)), cy + r * math.sin(math.radians(a0 + 90 * i / n))) for i in range(n + 1)]
    return pts

def rbox(name, x0, x1, y0, y1, z0, z1, r, m, top_in=0.0):
    """box with round upright corners. top_in > 0 cuts the top edge at 45 degrees by that much."""
    bm = bmesh.new()
    vb = [bm.verts.new((x, y, z0)) for x, y in rrect(x0, x1, y0, y1, r)]
    zc = z1 - top_in
    vm = [bm.verts.new((x, y, zc)) for x, y in rrect(x0, x1, y0, y1, r)] if top_in else vb
    vt = [bm.verts.new((x, y, z1)) for x, y in rrect(x0 + top_in, x1 - top_in, y0 + top_in, y1 - top_in, r - top_in)]
    bm.faces.new(vb[::-1]); bm.faces.new(vt)
    n = len(vb)
    for lo, hi in ((vb, vm), (vm, vt)) if top_in else ((vb, vt),):
        for i in range(n):
            bm.faces.new((lo[i], lo[(i + 1) % n], hi[(i + 1) % n], hi[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_obj(name, bm, m)

def soften(o, w=0.7):
    """round over every sharp edge by w"""
    b = o.modifiers.new("bevel", "BEVEL"); b.width = w; b.segments = 2; b.limit_method = "ANGLE"
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.modifier_apply(modifier=b.name)
    return o

def boolean(target, tool, op="DIFFERENCE"):
    b = target.modifiers.new("b", "BOOLEAN"); b.operation = op; b.object = tool; b.solver = "EXACT"
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.modifier_apply(modifier=b.name)
    bpy.data.objects.remove(tool)
    assert len(target.data.polygons) > 0, target.name
    return target

def cut(target, *tools):
    """cut the tools out of target (the tools are deleted)"""
    for t in tools:
        boolean(target, t)
    return target

def add(target, *tools):
    """join the tools onto target (the tools are deleted)"""
    for t in tools:
        boolean(target, t, "UNION")
    return target

def hole(c, r, d, axis="z"):
    """a round tool for cut(): radius r, length d"""
    return cyl("h", c, r, d, axis, M["blk"], 24)

def ins_hole(c, depth, down=True):
    """4.0 hole for an M3 heat-set insert, starting at c and going down (or up)"""
    z = c[2] - depth / 2 if down else c[2] + depth / 2
    return hole((c[0], c[1], z), 2.0, depth)

# Screw helpers
def hexnut(name, c, axis="z", h=2.4, af=5.5):
    o = cyl(name, c, af / math.sqrt(3), h, axis, M["steel"], 6)
    return cut(o, hole(c, 1.6, h + 2, axis))

def screw(name, top, length, down=(0, 0, -1)):
    """M3 screw. top = the point just under the head, the screw runs along `down`."""
    top, dv = Vector(top), Vector(down).normalized()
    s = cyl2(name, top, top + dv * length, 1.45, M["steel"], 16)
    add(s, cyl2(name + " head", top - dv * 3.0, top + dv * 0.01, 2.75, M["steel"], 16))
    return s

def m2screw(name, top, length, down=(0, 0, -1)):
    """M2 screw (motor brackets, servo arm, perf board)"""
    top, dv = Vector(top), Vector(down).normalized()
    s = cyl2(name, top, top + dv * length, 0.95, M["steel"], 12)
    add(s, cyl2(name + " head", top - dv * 1.6, top + dv * 0.01, 1.9, M["steel"], 12))
    return s

def washer(name, c, axis="z"):
    o = cyl(name, c, 3.5, 0.5, axis, M["steel"], 24)
    return cut(o, hole(c, 1.65, 3, axis))

# Wire helpers
WIRES = []      # every wire: (object, [(end point, name of the part it ends on), ...]), used by the check

def relax(pts, n=8):
    """turn every sharp corner into a smooth bend. The first and last pieces stay straight
    for a bit, so the wire leaves its plug straight."""
    P = [Vector(p) for p in pts]
    if len(P) < 3:
        return pts
    out = [P[0]]
    for i in range(1, len(P) - 1):
        a = P[i] + (P[i - 1] - P[i]) * (0.5 if i > 1 else 0.35)
        b = P[i] + (P[i + 1] - P[i]) * (0.5 if i < len(P) - 2 else 0.35)
        for k in range(n + 1):
            s = k / n
            out.append(a * (1 - s) ** 2 + P[i] * 2 * s * (1 - s) + b * s * s)
    out.append(P[-1])
    return [tuple(p) for p in out]

def wire(name, pts, m, r=0.75, ends=(), smooth=True):
    """a wire through the points pts, radius r. ends = the part names the first and last point sit on."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"; cu.bevel_depth = r; cu.bevel_resolution = 3; cu.use_fill_caps = True
    ends_at = (pts[0], pts[-1])
    pts = relax(pts) if smooth else pts
    sp = cu.splines.new("POLY"); sp.points.add(len(pts) - 1)
    for p, q in zip(sp.points, pts):
        p.co = (*q, 1)
    o = bpy.data.objects.new(name, cu)
    C_WIRE.objects.link(o)
    cu.materials.append(m)
    WIRES.append((o, list(zip(ends_at, ends))))
    return o

# Printed parts
CUR[0] = C_PRINT

# Where the M3 screws go (x, y)
UNDER = {       # screws going up through a 3.4 hole in the plate into the part on top
    "servo box": [(39, -10), (39, 10), (78, -13), (78, 13)],
}
INTO_PLATE = {  # screws going up through a part under the plate into inserts in the plate
    "bumper": [(78, -6), (78, 6)],
    "tow hook": [(-85, 0), (-78, 0)],
}
BRK_SCREWS = [(XR + dx, s * 25.5) for dx in (-9.7, 9.7) for s in (1, -1)]   # M2, metal motor brackets under the plate
LEAD_X = -53.0                   # the motor wires come up through a slot in the plate here
TRAY_SCREWS = [(-84, -16), (-84, 16)]     # M3 x 6 down through the battery tray floor into plate inserts

# servo (MG90S) sits upside down in a hole in the plate: its tabs rest on the plate, the shaft points down,
# and the servo arm is under the plate
SX, SY0 = XF, -6.2               # shaft x is the front axle; the body runs from y -6.2 to 16.6
SV_L, SV_W, SV_H = 22.8, 12.2, 22.7
TAB_Z = PZ + 0.05                # tabs rest on the plate top
SV_FACE = TAB_Z - 6.8            # the face the shaft comes out of, under the plate
HORN_Z0 = 5.5                    # servo arm bottom; the steering beam is screwed on under it
STEER_MAX = math.radians(22)

# on/off switch: snaps into a thin wing on the left side of the plate, just in front of the left rear wheel.
# The rocker is on top and the body hangs under the wing. Its two wires go through two small holes next to it.
SWX, SWY = -30.0, 38.0           # switch centre
SW_HOLES = [(-34.0, 27.5), (-27.0, 27.5)]   # wire from the battery plug / wire to the board

# Chassis plate
PLATE_X0 = -91.0                 # back edge, just behind the battery tray
plate = prism("Chassis plate", [(PLATE_X0, -30), (20, -30), (20, -24), (84, -24), (84, 24), (20, 24), (20, 30), (SWX + 10, 30), (SWX + 10, 46),
                               (SWX - 10, 46), (SWX - 10, 30), (PLATE_X0, 30)], PZ0, PZ, M["plate"])
for x, y in BRK_SCREWS:
    cut(plate, hole((x, y, (PZ0 + PZ) / 2), 1.1, 6))
for x, y in TRAY_SCREWS:
    cut(plate, hole((x, y, (PZ0 + PZ) / 2), 2.0, 6))
WIRE_HOLE = (28.0, 19.0)         # spare Ø6 wire hole through the plate, just in front of the board (hole 15 on the drawing)
cut(plate, hole((*WIRE_HOLE, (PZ0 + PZ) / 2), 3.0, 6))
cut(plate, box("lead slot", LEAD_X - 1.5, LEAD_X + 1.5, -4, 4, PZ0 - 1, PZ + 1, M["plate"]),
    box("servo cutout", SX - 6.4, SX + 6.4, SY0 - 0.3, SY0 + SV_L + 0.3, PZ0 - 1, PZ + 1, M["plate"]))
for y in (-8.75, 18.9):
    cut(plate, hole((SX, y, (PZ0 + PZ) / 2), 0.8, 6))                 # small holes for the servo's own tab screws
for k, pts in list(UNDER.items()) + list(INTO_PLATE.items()):
    for x, y in pts:   # 3.4 for screws going up into other parts, 4.0 for inserts in the plate
        cut(plate, hole((x, y, (PZ0 + PZ) / 2), 2.0 if k in INTO_PLATE else 1.7, 6))
# four posts for the perf board, M2 x 6 screws down into 1.6 holes
PB_HOLES = [(x, s * (PBY - 2.8)) for x in (PB0 + 2.8, PB1 - 2.8) for s in (1, -1)]
for x, y in PB_HOLES:
    add(plate, cyl("post", (x, y, (PZ - 0.1 + PBZ0) / 2), 2.5, PBZ0 - PZ + 0.1, "z", M["plate"]))
    cut(plate, hole((x, y, PBZ0 - 2.5), 0.8, 5.1))
cut(plate, box("wing pocket", SWX - 10.1, SWX + 10.1, 30.05, 46.1, PZ0 - 1, PZ - 2, M["plate"]))   # wing is 2 thick so the switch clips grip
cut(plate, box("switch", SWX - 7.5, SWX + 7.5, SWY - 5, SWY + 5, PZ0 - 1, PZ + 1, M["plate"]))       # switch hole 15 x 10
for x, y in SW_HOLES:
    cut(plate, hole((x, y, (PZ0 + PZ) / 2), 1.6, 6))

# Battery tray: sits on the plate right over the rear motors
TR0, TR1, TW_ = -90.4, -56.05, 30.0               # tray back x, front x, half width
BATX = (-88.2, -58.2)                             # battery x range (it lies across the car)
BZ0 = PZ + 5                                      # battery bottom = top of the 5 thick floor
tray = rbox("Battery tray", TR0, TR1, -TW_, TW_, PZ, BZ0, 3, M["tray"])
lipw = rbox("lip", TR0, TR1, -TW_, TW_, BZ0 - 0.01, BZ0 + 6, 3, M["tray"], top_in=0.6)    # 6 tall wall all round the battery
cut(lipw, rbox("in", TR0 + 2, TR1 - 1.95, -TW_ + 2, TW_ - 2, BZ0 - 1, BZ0 + 7, 1, M["tray"]))
add(tray, lipw)
for x, y in TRAY_SCREWS:                         # two screws down through the floor, heads sunk into it
    cut(tray, hole((x, y, PZ + 2.5), 1.7, 6), hole((x, y, BZ0 - 1.5), 3.0, 3.1))
for x, y in BRK_SCREWS:                          # pockets under the floor for the motor bracket screw heads
    if TR0 < x + 2.4 and x - 2.4 < TR1:
        cut(tray, hole((x, y, PZ + 1.1), 2.4, 2.4))
cut(tray, rbox("floor window", -81, -66, -12, 12, PZ - 1, BZ0 + 1, 4, M["tray"]))
ANT = (TR0 - 2.0, 22.0)                           # antenna post: round post on the back left corner, 3.2 hole from the top
add(tray, cyl("antenna boss", (*ANT, (PZ + BZ0 + 6) / 2), 3.5, BZ0 + 6 - PZ, "z", M["tray"], 32))
cut(tray, hole((*ANT, BZ0 + 6 - 4), 1.6, 8.2))

# Antenna: just for looks. Peg into the post, collar, thin mast, ball on top.
AZ0 = BZ0 + 6
ant = cyl("Antenna", (*ANT, AZ0 - 3.9), 1.45, 7.8, "z", M["blk"], 24)
add(ant, cyl("collar", (*ANT, AZ0 + 1.0), 2.6, 2.0, "z", M["blk"], 24),
    cyl("mast", (*ANT, AZ0 + 24.5), 1.6, 45, "z", M["blk"], 24, r2=1.1),
    ball((*ANT, AZ0 + 48), 2.5, M["blk"]))

# Front bumper: upright face with 45 degree edges top and bottom, on a tongue under the plate
FX = 100.0                       # front face (16 in front of the plate)
DT = 29.0                        # top edge (the servo box top is at the same height)
CH = 2.12                        # makes the 45 degree walls 3 thick, like the rest
FT = DT - 9                      # top of the flat face, where the top 45 degree edge starts
prof = [(FX - 7, -6.5), (FX, 0.5), (FX, FT), (FX - 9, DT), (FX - 12, DT), (FX - 12, DT - 3), (FX - 2 * CH - 6, DT - 3),
        (FX - 3, FT - CH + 0.88), (FX - 3, 1.74), (FX - 11.24, -6.5)]
bump = xz_prism("Front bumper", prof, -32, 32, M["plow"])
add(bump, box("tongue", 70, FX - 2.9, -10, 10, 10, PZ0, M["plow"]))           # under the plate, 2 M3 screws up into inserts
for y in (-7, 7):                                                              # two braces from the tongue up the back of the face
    add(bump, xz_prism("brace", [(88, PZ0 - 0.1), (FX - 2.95, PZ0 - 0.1), (FX - 2.95, FT + 2)], y - 1.5, y + 1.5, M["plow"]))
add(bump, box("lip to box", 84.05, FX - 11.5, -24, 24, DT - 3, DT, M["plow"]))   # top lip reaches back to touch the servo box
BUMP_TABS = [(81.0, -17.5), (81.0, 17.5)]      # two tabs sit on the servo box top, M3 x 8 down into inserts
for x, y in BUMP_TABS:
    add(bump, rbox("tab", 78.0, 86.5, y - 3, y + 3, DT - 0.05, DT + 3, 1.5, M["plow"]))
for s_ in (1, -1):                              # two more braces near the ends tie the top edge to the face
    y0, y1 = sorted((s_ * 19.5, s_ * 22.5))
    add(bump, xz_prism("end brace", [(84.1, DT - 2.95), (FX - 2 * CH - 6, DT - 2.95), (FX - 2.95, FT - CH + 0.88), (FX - 2.95, 12)],
                       y0, y1, M["plow"]))
for x, y in INTO_PLATE["bumper"]:
    cut(bump, hole((x, y, 12), 1.7, 6))
for s_ in (1, -1):                                                             # 45 degree cuts on the two outer front corners
    cut(bump, prism("corner", [(FX - 5, s_ * 32.1), (FX + 0.1, s_ * 32.1), (FX + 0.1, s_ * 26.9)], -8, DT + 1, M["plow"]))
soften(bump, 0.9)
for x, y in BUMP_TABS:
    cut(bump, hole((x, y, DT + 1.5), 1.7, 4))

def skin(name, pts, t, y0, y1, m):
    """a layer t thick laid over the outside of a side outline (like tape)"""
    P = [Vector((x, 0, z)) for x, z in pts]
    Q = []
    for i, p in enumerate(P):
        ns = []
        for a, b in ((P[i - 1], p) if i else (None, None), (p, P[i + 1]) if i < len(P) - 1 else (None, None)):
            if a is not None:
                d = (b - a).normalized(); ns.append(Vector((d.z, 0, -d.x)))
        n = sum(ns, Vector()); n.normalize()
        Q.append(p + n * (t / max(n.dot(ns[0]), 0.5)))
    return xz_prism(name, [(v.x, v.z) for v in P + Q[::-1]], y0, y1, m)

# two stripes of black tape over the bumper face, top edge and lip
CUR[0] = C_BUY
for s_ in (1, -1):
    y0, y1 = sorted((s_ * 5.5, s_ * 10.5))
    skin(f"Bumper stripe {'LR'[s_ < 0]}", [(FX - 7, -6.5), (FX, 0.5), (FX, FT), (FX - 9, DT), (84.05, DT)], 0.2, y0, y1, M["stripe"])
CUR[0] = C_PRINT

# tow hook: round J hook under the back of the plate, opening faces forward, knob on the tip so a
# strap can't slide off. Wide pad under the plate with 2 M3 screws up into plate inserts.
HC = PLATE_X0 - 3.0              # x of the bend centre
hk = [(-88, 10), (HC, 10)]
hk += [(HC + 7 * math.cos(a), 17 + 7 * math.sin(a)) for a in [math.radians(-90 - 10 * k) for k in range(1, 10)]]   # outside of the bend
hk += [(HC - 7, 21.5), (HC - 3, 21.5)]
hk += [(HC + 3 * math.cos(a), 17 + 3 * math.sin(a)) for a in [math.radians(180 + 10 * k) for k in range(0, 10)]]   # inside of the bend
hk += [(-88, 14)]
hook = xz_prism("Tow hook", hk, -4.5, 4.5, M["plow"])
add(hook, rbox("pad", -89, -73.5, -7, 7, 10, PZ0, 3, M["plow"]),
    cyl("knob", (HC - 5, 0, 21.5), 2.8, 9, "y", M["plow"], 32))
soften(hook, 0.8)
for x, y in INTO_PLATE["tow hook"]:
    cut(hook, hole((x, y, 12), 1.7, 6))

# servo box: black cover over the front of the plate. Top is level with the bumper top and the servo
# pokes out of it. Open bottom. 4 M3 screws up through the plate into inserts in posts inside.
SB0, SB1, SBY = 35.0, 84.0, 24.0
sbox = rbox("Servo box", SB0, SB1, -SBY, SBY, PZ, DT, 3, M["sbox"], top_in=1.0)
cut(sbox, rbox("in", SB0 + 2, SB1 - 2, -SBY + 2, SBY - 2, PZ - 1, DT - 2, 1, M["sbox"]))
for x, y in UNDER["servo box"]:
    add(sbox, cyl("boss", (x, y, (PZ + DT - 1.9) / 2), 3.5, DT - 1.9 - PZ, "z", M["sbox"]))
    cut(sbox, ins_hole((x, y, PZ - 0.1), 6.1, down=False))
for x, y in BUMP_TABS:
    add(sbox, cyl("bumper boss", (x, y, DT - 5), 3.0, 6.1, "z", M["sbox"]))
    cut(sbox, ins_hole((x, y, DT + 0.1), 8.1))
cut(sbox, box("servo hole", SX - SV_W / 2 - 0.6, SX + SV_W / 2 + 0.6, SY0 - 0.6, SY0 + SV_L + 0.6, DT - 3, DT + 1, M["sbox"]))

def wheel(name, x, yc, s, bore):
    """push-on wheel centred at (x, yc, axle height): rubber tire with tread and a plastic hub. Returns [tire, hub]."""
    CUR[0] = C_BUY
    t = cyl(name + " tire", (x, yc, AZ), R - 1.0, TW, "y", M["tire"], 48)
    cut(t, hole((x, yc, AZ), 16.0, TW + 2, "y"))
    bm = bmesh.new(); bm.from_mesh(t.data)
    for i in range(16):                          # 2 rows of 16 tread blocks
        for k, off in enumerate((-4.5, 4.5)):
            ang = 2 * math.pi * i / 16 + (math.pi / 16 if k else 0)
            g = bmesh.ops.create_cube(bm, size=1)["verts"]
            bmesh.ops.scale(bm, vec=(3.2, 7, 2), verts=g)
            bmesh.ops.rotate(bm, verts=g, cent=(0, 0, 0), matrix=Matrix.Rotation(-ang + math.pi / 2, 3, "Y"))
            bmesh.ops.translate(bm, verts=g, vec=(x + (R - 1.0) * math.cos(ang), yc + off, AZ + (R - 1.0) * math.sin(ang)))
    bm.to_mesh(t.data); bm.free()
    hub = cyl(name + " hub", (x, yc, AZ), 15.8, TW - 2, "y", M["hub"])
    cut(hub, hole((x, yc + s * (TW / 2 - 1), AZ), 12, 4, "y"), hole((x, yc, AZ), bore, TW, "y"))
    CUR[0] = C_PRINT
    return [t, hub]

def empty(name, loc):
    """an invisible point other objects can hang from"""
    e = bpy.data.objects.new(name, None); e.location = loc; C_HELP.objects.link(e); e.empty_display_size = 6
    return e

def parent(o, e):
    """make o move with e"""
    bpy.context.view_layer.update()
    o.parent = e; o.matrix_parent_inverse = e.matrix_world.inverted()

# Rear drive: 2 N20 motors in metal brackets under the plate
for s, side in ((1, "L"), (-1, "R")):
    CUR[0] = C_BUY
    g0, g1 = sorted((s * 22, s * 31)); m0, m1 = sorted((s * 7, s * 22.01))
    box(f"N20 gearbox {side}", XR - 6, XR + 6, g0, g1, AZ - 5, AZ + 5, M["steel"])     # top flat against the plate
    box(f"N20 motor {side}", XR - 6, XR + 6, m0, m1, AZ - 5, AZ + 5, M["brass"])
    shf = cyl(f"N20 shaft {side}", (XR, s * 36, AZ), 1.5, 10, "y", M["steel"], 16)
    cut(shf, box("flat", XR - 3, XR + 3, *sorted((s * 30, s * 42)), AZ + 1.0, AZ + 3, M["blk"]))
    for tx in (-3.5, 3.5):                                                             # the 2 solder tabs on the motor end
        t0, t1 = sorted((s * 5, s * 7.01))
        box(f"N20 tab {side}{'ab'[tx > 0]}", XR + tx - 0.4, XR + tx + 0.4, t0, t1, AZ - 1.5, AZ + 1.5, M["brass"])
    y0, y1 = sorted((s * 22.5, s * 29.5))                                              # U strap round the gearbox, feet on the plate
    brk = box(f"N20 bracket {side}", XR - 6.8, XR + 6.8, y0, y1, AZ - 5.8, AZ - 5.0, M["steel"])
    for d in (-1, 1):
        x0_, x1_ = sorted((XR + d * 6.0, XR + d * 6.8))
        f0, f1 = sorted((XR + d * 6.0, XR + d * 12.5))
        add(brk, box("side", x0_, x1_, y0, y1, AZ - 5.8, PZ0, M["steel"]), box("foot", f0, f1, y0, y1, PZ0 - 0.8, PZ0, M["steel"]))
    for dx in (-9.7, 9.7):
        cut(brk, hole((XR + dx, s * 25.5, PZ0 - 0.4), 1.1, 2))
    wheel(f"Rear {side}", XR, s * (32.0 + TW / 2), s, 1.55)
    CUR[0] = C_HW
    for k, dx in enumerate((-9.7, 9.7)):
        m2screw(f"Bracket screw M2x8 {side}{k + 1}", (XR + dx, s * 25.5, PZ + 0.05), 8)
        hexnut(f"Bracket nut M2 {side}{k + 1}", (XR + dx, s * 25.5, PZ0 - 1.6), h=1.6, af=4.0)

# Front steering: one printed beam, screwed to the servo arm and turned by it
CUR[0] = C_BUY
sv = box("MG90S servo", SX - SV_W / 2, SX + SV_W / 2, SY0, SY0 + SV_L, SV_FACE, SV_FACE + SV_H, M["servo"])
add(sv, box("tabs", SX - SV_W / 2, SX + SV_W / 2, SY0 - 4.85, SY0 + SV_L + 4.85, TAB_Z, TAB_Z + 2.5, M["servo"]),
    cyl("boss", (SX, 0, SV_FACE - 1.0), 2.9, 2.01, "z", M["servo"]))
for y in (-8.75, 18.9):
    cut(sv, hole((SX, y, TAB_Z + 1.25), 1.0, 4))
CUR[0] = C_HW
for y in (-8.75, 18.9):
    cyl2("Servo tab screw", (SX, y, TAB_Z + 4.0), (SX, y, TAB_Z - 5), 0.9, M["steel"], 12)

steer = empty("Steering pivot", (XF, 0, 0))       # everything that turns hangs from this point
BT = HORN_Z0 - 0.05                 # beam top, just under the servo arm
CUR[0] = C_PRINT
beam = box("Steering beam", XF - 5, XF + 5, -27, 27, 0, BT, M["plow"])
for s in (1, -1):
    y0, y1 = sorted((s * 26, s * 36))
    add(beam, box("end", XF - 5, XF + 5, y0, y1, 0, 12.8, M["plow"]))                # taller ends hold the wheel bolt inserts
soften(beam, 0.6)
for s in (1, -1):
    cut(beam, hole((XF, s * 31.05, AZ), 2.0, 10.1, "y"), hole((XF, s * 10, BT / 2), 1.2, BT + 2))   # insert hole; 2.4 hole for the arm screw
cut(beam, hole((XF, 0, BT / 2), 2.5, BT + 2))                                          # lets a screwdriver reach the arm's centre screw
CUR[0] = C_BUY
horn = box("Servo horn", SX - 2.6, SX + 2.6, -15, 15, HORN_Z0, HORN_Z0 + 2, M["white"])
add(horn, cyl("hub", (SX, 0, (HORN_Z0 + SV_FACE - 2.05) / 2), 3.5, SV_FACE - 2.05 - HORN_Z0, "z", M["white"]),
    cyl("e1", (SX, 15, HORN_Z0 + 1), 2.6, 2, "z", M["white"]), cyl("e2", (SX, -15, HORN_Z0 + 1), 2.6, 2, "z", M["white"]))
for y in (-10, 10):
    cut(horn, hole((SX, y, HORN_Z0 + 1), 0.6, 4))
moving = [beam, horn]
CUR[0] = C_HW
moving += [m2screw(f"Horn screw M2x8 {'LR'[y < 0]}", (SX, y, -0.05), 8, (0, 0, 1)) for y in (-10, 10)]
moving.append(m2screw("Horn centre screw", (SX, 0, HORN_Z0 - 0.05), 6, (0, 0, 1)))
for s, side in ((1, "L"), (-1, "R")):
    moving += wheel(f"Front {side}", XF, s * (36.6 + TW / 2), s, 1.6)                 # hole drilled out round, spins on the bolt
    CUR[0] = C_HW
    moving += [washer(f"Front washer in {side}", (XF, s * 36.3, AZ), "y"), washer(f"Front washer out {side}", (XF, s * 55.9, AZ), "y"),
               screw(f"Front axle bolt M3x30 {side}", (XF, s * 56.2, AZ), 30, (0, -s, 0))]
CUR[0] = C_PRINT
for o in moving:
    parent(o, steer)

def pose(theta):
    """turn the steering to theta (radians, + = left)"""
    steer.rotation_euler.z = theta
    bpy.context.view_layer.update()

# Electronics (bought)
CUR[0] = C_BUY
# battery (VICMILE 2S 1200 mAh): black wrap, orange label on top, teal end where the wires come out (left end).
# Wires: red/black pair to a red JST plug, a spare red/black pair to a white PH2.0 plug, and a 3-wire balance plug.
BL = LIPO[0] / 2
bat = rbox("LiPo 2S 1200mAh", BATX[0], BATX[1], -BL, BL - 0.6, BZ0 + 0.05, BZ0 + LIPO[2], 1.5, M["lipo"])
soften(bat, 1.2)
box("LiPo end", BATX[0] + 0.6, BATX[1] - 0.6, BL - 0.65, BL - 0.05, BZ0 + 0.6, BZ0 + LIPO[2] - 0.55, M["lipo_end"])
box("LiPo label stripe", -63.0, -59.8, -BL + 3, BL - 4, BZ0 + LIPO[2] - 0.01, BZ0 + LIPO[2] + 0.08, M["label"])

def label(name, text, size, x, y, m):
    """flat text lying on the battery top"""
    cu = bpy.data.curves.new(name, "FONT"); cu.body = text; cu.size = size; cu.extrude = 0.04
    cu.align_x = "CENTER"; cu.align_y = "CENTER"
    t = bpy.data.objects.new(name, cu); bpy.context.collection.objects.link(t)
    dg = bpy.context.evaluated_depsgraph_get(); me = bpy.data.meshes.new_from_object(t.evaluated_get(dg))
    bpy.data.objects.remove(t); bpy.data.curves.remove(cu)
    me.transform(Matrix.Translation((x, y, BZ0 + LIPO[2] + 0.04)) @ Matrix.Rotation(math.pi / 2, 4, "Z"))
    o = bpy.data.objects.new(name, me); CUR[0].objects.link(o); me.materials.append(m)
    return o

label("LiPo label 1200", "1200", 9.0, -73.5, -4.0, M["label"])
label("LiPo label mAh", "mAh 35C 7.4V", 3.0, -66.5, -4.0, M["white"])
label("LiPo label brand", "VICMILE", 3.2, -80.5, -4.0, M["label"])
# the two spare plugs lie on top of the battery
BTOP = BZ0 + LIPO[2]
box("PH2.0 plug", -74.0, -68.0, 16.0, 20.5, BTOP + 0.12, BTOP + 4.5, M["plugw"])
box("Balance plug", -85.0, -76.0, 12.0, 18.0, BTOP + 0.12, BTOP + 5.8, M["plugw"])

# Perf board (the main board): 24 x 18 holes, 2.54 apart, 4 corner screw holes
TOP = PBZ0 + 1.6
pb = rbox("Perf board", PB0, PB1, -PBY, PBY, PBZ0, TOP, 1.0, M["pcb"])
for x, y in PB_HOLES:
    cut(pb, hole((x, y, TOP - 0.8), 1.1, 3))

def ph(i, j):
    """position of a perf board hole: i = 0..23 counted from the back edge, j = 0..17 from the right edge"""
    return (PB0 + 5.8 + 2.54 * i, -21.59 + 2.54 * j, TOP)

bm = bmesh.new()                    # copper rings round every hole
for i in range(24):
    for j in range(18):
        x, y, _ = ph(i, j)
        r = bmesh.ops.create_circle(bm, cap_ends=False, radius=0.85, segments=10)["verts"]
        r2 = bmesh.ops.create_circle(bm, cap_ends=False, radius=0.5, segments=10)["verts"]
        bmesh.ops.translate(bm, verts=r + r2, vec=(x, y, TOP + 0.03))
        for k in range(10):
            bm.faces.new((r[k], r[(k + 1) % 10], r2[(k + 1) % 10], r2[k]))
mesh_obj("Perf board pads", bm, M["pad"])

def header(name, pts):
    """straight pin header: one black block per pin"""
    o = None
    for p in pts:
        b = box(name, p[0] - 1.25, p[0] + 1.25, p[1] - 1.25, p[1] + 1.25, TOP + 0.05, TOP + 2.5, M["blk"])
        o = b if o is None else add(o, b)
    return o

def terminal(name, i, j):
    """2-pin screw terminal with pins in holes (i, j) and (i, j + 2), wire openings facing the back"""
    x, y0, _ = ph(i, j); y1 = ph(i, j + 2)[1]
    t = box(name, x - 3.75, x + 3.75, y0 - 2.5, y1 + 2.5, TOP + 0.05, TOP + 10, M["term"])
    for y in (y0, y1):
        cut(t, box("opening", x - 4, x + 0.25, y - 1.1, y + 1.1, TOP + 2.4, TOP + 4.6, M["term"]),
            hole((x, y, TOP + 9.5), 1.6, 2))
        add(t, cyl("screw", (x, y, TOP + 8.9), 1.4, 1.0, "z", M["steel"], 16))
    return t

TE = TOP + 3.5                     # wire height inside a terminal opening
def t_end(i, j):
    """where a wire ends inside the terminal pin at hole (i, j)"""
    return (ph(i, j)[0] - 0.25, ph(i, j)[1], TE)

def ra_header(name, i, js):
    """right-angle pin header at the front edge, pins pointing forward past the board"""
    x = ph(i, 0)[0]
    o = None
    for j in js:
        y = ph(i, j)[1]
        b = box(name, x - 1.25, x + 1.25, y - 1.25, y + 1.25, TOP + 0.05, TOP + 2.55, M["blk"])
        add(b, box("pin", x, x + 7.5, y - 0.32, y + 0.32, TOP + 1.3 - 0.32, TOP + 1.3 + 0.32, M["steel"]))
        o = b if o is None else add(o, b)
    return o

PLUG_X = ph(23, 0)[0] + 1.3        # where a plug starts on a front header
def plug(name, j0, j1, m=None):
    return box(name, PLUG_X, PLUG_X + 14, ph(23, j0)[1] - 1.24, ph(23, j1)[1] + 1.24, TOP + 0.06, TOP + 2.54, m or M["blk"])

# Board layout (i = hole from the back edge, j = hole from the right edge):
#   screw terminals at i 2:  right motor j 3 and 5,  left motor j 7 and 9,  power j 14 (+ after the switch) and 16 (GND)
#   DRV8833 motor driver, outputs facing back:  i 5 = ULT OUT4 OUT3 OUT2 OUT1 EEP,  i 10 = IN1 IN2 VCC GND IN3 IN4  (j 4 to 9)
#   Mini360 5V board:  IN- (8,12)  IN+ (8,15)  OUT- (14,12)  OUT+ (14,15)
#   470uF capacitor:  + (17,10)  - (18,10)
#   brain sockets at i 22 and i 16, servo plug at the front edge i 23
terminal("Terminal motor R", 2, 3)
terminal("Terminal motor L", 2, 7)
terminal("Terminal power", 2, 14)
header("DRV8833 header", [ph(i, j) for i in (5, 10) for j in range(4, 10)])
cx, cy = (ph(5, 0)[0] + ph(10, 0)[0]) / 2, (ph(0, 4)[1] + ph(0, 9)[1]) / 2
drv = box("DRV8833", cx - 7.9, cx + 7.9, cy - 9.25, cy + 9.25, TOP + 2.55, TOP + 4.1, M["blk"])
add(drv, box("chip", cx - 3.2, cx + 3.2, cy - 2.5, cy + 2.5, TOP + 4.0, TOP + 5.0, M["steel"]))
header("Mini360 pins", [ph(i, j) for i in (8, 14) for j in (12, 15)])
cx, cy = (ph(8, 0)[0] + ph(14, 0)[0]) / 2, (ph(0, 12)[1] + ph(0, 15)[1]) / 2
mini = box("Mini360 5V", cx - 8.75, cx + 8.75, cy - 6.15, cy + 6.15, TOP + 2.55, TOP + 4.1, M["pcbb"])
add(mini, box("coil", cx - 3, cx + 3, cy - 3, cy + 3, TOP + 4.0, TOP + 6.5, M["blk"]))
CAPC = ((ph(17, 0)[0] + ph(18, 0)[0]) / 2, ph(0, 10)[1])
cap = cyl("470uF capacitor", (CAPC[0], CAPC[1], TOP + 7.2), 4.0, 12.0, "z", M["blk"])
for i in (17, 18):
    p = ph(i, 10)
    cyl2("cap leg", (p[0], p[1], TOP + 0.05), (CAPC[0] + (i - 17.5) * 3.5, CAPC[1], TOP + 1.3), 0.3, M["steel"], 8)

# brain: ESP32-C3 SuperMini in two 8-pin sockets at the front right corner, USB-C facing the right side
#   socket A (i 22, j 0 to 7): 5V GND 3V3 G4 G3 G2 G1 G0      socket B (i 16, j 0 to 7): G5 G6 G7 G8 G9 G10 G20 G21
for k, i in enumerate((22, 16)):
    box(f"Brain socket {'AB'[k]}", ph(i, 0)[0] - 1.27, ph(i, 0)[0] + 1.27, ph(0, 0)[1] - 1.27, ph(0, 7)[1] + 1.27,
        TOP + 0.05, TOP + 8.5, M["blk"])
C3X = (ph(16, 0)[0] + ph(22, 0)[0]) / 2
C3Y0 = ph(0, 0)[1] - 3.2                      # USB end
C3Z = TOP + 11.05
c3 = box("ESP32-C3 SuperMini", C3X - 9, C3X + 9, C3Y0, C3Y0 + 22.52, C3Z, C3Z + 1.0, M["c3"])
add(c3, box("chip", C3X - 2.5, C3X + 2.5, C3Y0 + 9, C3Y0 + 14, C3Z + 0.99, C3Z + 1.9, M["blk"]),
    box("antenna", C3X - 3.5, C3X + 3.5, C3Y0 + 18.5, C3Y0 + 20.5, C3Z + 0.99, C3Z + 2.2, M["steel"]))
box("ESP32-C3 USB-C", C3X - 4.47, C3X + 4.47, C3Y0 - 0.8, C3Y0 + 6.5, C3Z + 1.0, C3Z + 4.2, M["steel"])
for k, i in enumerate((22, 16)):
    x = ph(i, 0)[0]
    hdr = box(f"ESP32-C3 pins {'AB'[k]}", x - 1.25, x + 1.25, ph(0, 0)[1] - 1.25, ph(0, 7)[1] + 1.25, TOP + 8.55, C3Z - 0.05, M["blk"])
    for j in range(8):
        y = ph(0, j)[1]
        add(hdr, box("pin", x - 0.32, x + 0.32, y - 0.32, y + 0.32, TOP + 2.6, TOP + 8.6, M["steel"]))

def standing_resistor(name, a, b):
    """resistor standing on hole a, its top wire bent over and down into hole b"""
    pa, pb = ph(*a), ph(*b)
    r = cyl(name, (pa[0], pa[1], TOP + 3.8), 1.2, 6.2, "z", M["res"], 16)
    add(r, cyl2("leg", (pa[0], pa[1], TOP + 6.8), (pa[0], pa[1], TOP + 8.0), 0.3, M["steel"], 8),
        cyl2("leg", (pa[0], pa[1], TOP + 8.0), (pb[0], pb[1], TOP + 8.0), 0.3, M["steel"], 8),
        cyl2("leg", (pb[0], pb[1], TOP + 8.0), (pb[0], pb[1], TOP + 0.05), 0.3, M["steel"], 8))
    return r

standing_resistor("Battery resistor 47k", (19, 3), (19, 5))     # battery + -> 47k -> brain G3 -> 10k -> GND
standing_resistor("Battery resistor 10k", (20, 5), (20, 3))
ra_header("Servo header", 23, (13, 14, 15))
splug = plug("Servo plug", 13, 15)

# on/off switch in the wing: rocker on top, body below, two metal tabs pointing down
sw = box("Rocker switch", SWX - 6.5, SWX + 6.5, SWY - 4.3, SWY + 4.3, PZ - 11.15, PZ - 2.05, M["blk"])
add(sw, box("neck", SWX - 6.5, SWX + 6.5, SWY - 4.3, SWY + 4.3, PZ - 2.1, PZ - 0.05, M["blk"]),
    box("bezel", SWX - 8.5, SWX + 8.5, SWY - 5.5, SWY + 5.5, PZ + 0.05, PZ + 2.0, M["blk"]),
    box("rocker", SWX - 6.5, SWX + 6.5, SWY - 3.5, SWY + 3.5, PZ + 1.9, PZ + 4.0, M["blk"]))
SWT = {1: SWX + 3.5, 2: SWX - 3.5}  # tab x: tab 1 goes to the board, tab 2 comes from the battery
ST = PZ - 11.15 - 2.0               # wire height on the tabs
for k, x in SWT.items():
    box(f"Switch tab {k}", x - 0.4, x + 0.4, SWY - 1.5, SWY + 1.5, PZ - 15.25, PZ - 11.1, M["steel"])

# JST plug pair lying on top of the battery at its front left corner, pointing across the car
JX, JY = -65.25, 21.0              # plug centre x, and the y where the two halves meet
box("JST plug battery", JX - 2.75, JX + 2.75, JY + 0.05, JY + 5.85, BZ0 + LIPO[2] + 0.12, BZ0 + LIPO[2] + 4.12, M["red"])
box("JST plug car", JX - 2.75, JX + 2.75, JY - 6.0, JY, BZ0 + LIPO[2] + 0.12, BZ0 + LIPO[2] + 4.12, M["red"])

# Screws
CUR[0] = C_HW
for k, pts in UNDER.items():
    for i, (x, y) in enumerate(pts):
        screw(f"{k} screw M3x8 {i + 1}", (x, y, PZ0 - 0.05), 8, (0, 0, 1))
for k, pts in INTO_PLATE.items():
    for i, (x, y) in enumerate(pts):
        screw(f"{k} screw M3x8 {i + 1}", (x, y, 10 - 0.05), 8, (0, 0, 1))
for i, (x, y) in enumerate(TRAY_SCREWS):
    screw(f"Tray screw M3x6 {i + 1}", (x, y, BZ0 - 3.05), 6)
for i, (x, y) in enumerate(PB_HOLES):
    m2screw(f"Perf screw M2x6 {i + 1}", (x, y, TOP + 0.05), 6)

# Wires
WT = TOP + 0.9     # height of a wire end standing in a perf board hole

# Traces: bare wire soldered along the holes under the board, none of them cross
TZ = PBZ0 - 0.35
def trace(name, holes):
    wire("Trace " + name, [(*ph(i, j)[:2], TZ) for i, j in holes], M["tin"], 0.3, ["Perf board", "Perf board"], smooth=False)

# motor driver outputs straight back to the motor terminals
trace("OUT4", [(2, 3), (3, 3), (3, 5), (5, 5)])
trace("OUT3", [(2, 5), (2, 6), (5, 6)])
trace("OUT2", [(2, 7), (5, 7)])
trace("OUT1", [(2, 9), (3, 9), (3, 8), (5, 8)])
# battery + (after the switch) to the motor driver and the Mini360 input
trace("VIN", [(2, 14), (7, 14), (7, 6), (10, 6)])
trace("VIN Mini360", [(7, 14), (7, 15), (8, 15)])
trace("VIN sense", [(7, 6), (7, 1)])                                # out to the right edge for the battery sense wire
# ground: along the left edge, then down the middle to the brain, with branches to everything else
trace("GND", [(2, 16), (2, 17), (18, 17), (18, 1), (22, 1)])
trace("GND DRV", [(9, 17), (9, 7), (10, 7)])
trace("GND Mini360", [(8, 12), (9, 12)])
trace("GND servo", [(18, 15), (23, 15)])
trace("GND battery", [(20, 3), (20, 1)])
# 5V from the Mini360 to the capacitor and the brain's 5V pin. The servo plug gets 5V from a red wire on top.
trace("5V", [(14, 15), (15, 15), (15, 10), (17, 10), (17, 0), (22, 0)])
trace("5V plugs", [(20, 14), (23, 14)])
# brain pins: G0 servo, G3 battery level, G7 G10 G20 G21 to the motor driver IN1 to IN4
trace("SIG", [(22, 7), (22, 13), (23, 13)])
trace("VIN battery", [(19, 2), (19, 3)])
trace("BAT", [(19, 5), (20, 5), (21, 5), (21, 4), (22, 4)])
trace("IN1", [(10, 4), (15, 4), (15, 2), (16, 2)])
trace("IN2", [(10, 5), (16, 5)])
trace("IN3", [(10, 8), (15, 8), (15, 6), (16, 6)])
trace("IN4", [(10, 9), (16, 9), (16, 7)])

# Two wires on top of the board: 5V to the servo plug, battery + to the battery sense resistor
JZ_ = TOP + 0.75
def topwire(name, holes, m):
    pts = [(*ph(*holes[0])[:2], WT)] + [(*ph(*h)[:2], JZ_) for h in holes] + [(*ph(*holes[-1])[:2], WT)]
    wire(name, pts, m, 0.55, ["Perf board", "Perf board"], smooth=False)

topwire("Top wire 5V", [(15, 14), (20, 14)], M["red"])
x0, y0, _ = ph(7, 1); x1, y1, _ = ph(19, 2)
wire("Top wire battery sense", [(x0, y0, WT), (x0, y0, JZ_), (x0, -23.7, JZ_), (x1, -23.7, JZ_), (x1, y1, JZ_), (x1, y1, WT)],
     M["orange"], 0.55, ["Perf board", "Perf board"], smooth=False)

# motor wires: from the motor tabs, under the plate, up through the slot, then fan out into the
# screw terminals at the back of the board (left motor on OUT1 / OUT2, right motor on OUT3 / OUT4)
for k, (n, s, tx, m) in enumerate([("Motor L+", 1, -3.5, M["red"]), ("Motor L-", 1, 3.5, M["black"]),
                                   ("Motor R+", -1, -3.5, M["red"]), ("Motor R-", -1, 3.5, M["black"])]):
    x, y, _ = t_end(2, 9 - 2 * k)
    zu, ys = 7.4 + 1.9 * k, 2.7 - 1.8 * k      # height under the plate, and spot in the slot, so the 4 wires don't touch
    wire(n, [(XR + tx, s * 5.6, AZ), (XR + tx, s * 4.0, zu), (XR + tx, 0, zu), (LEAD_X, ys, zu), (LEAD_X, ys, PZ0 - 1.5),
             (LEAD_X, ys, PZ + 2), (LEAD_X, ys, TE), (-46, y, TE), (x, y, TE)],
         m, 0.7, [f"N20 tab {'L' if s > 0 else 'R'}{'ab'[tx > 0]}", "Terminal motor " + ("L" if s > 0 else "R")])

# battery wires out of the battery's left end: the main pair up into the JST plug on top, the spare pair
# and the balance wires over the top edge onto their plugs
BE = BL - 0.1
BTZ = BTOP + 2.12                  # wire height at the JST pins
for n, x, m in (("Battery lead red", JX + 1.2, M["red"]), ("Battery lead black", JX - 1.2, M["black"])):
    wire(n, [(x, BE, BZ0 + 9), (x, BL + 0.9, BZ0 + 10), (x, BL + 0.9, BTZ), (x, JY + 5.9, BTZ)], m, 0.8, ["LiPo end", "JST plug battery"])
for n, x, m in (("PH2.0 lead red", -70.0, M["red"]), ("PH2.0 lead black", -72.0, M["black"])):
    wire(n, [(x, BE, BZ0 + 8), (x, BL + 0.8, BZ0 + 9), (x, BL + 0.8, BTOP + 1.5), (x, 24, BTOP + 1.6), (x, 20.55, BTOP + 2)],
         m, 0.55, ["LiPo end", "PH2.0 plug"])
for x, m in ((-83, M["black"]), (-80.5, M["white_w"]), (-78, M["red"])):
    wire(f"Balance lead {x}", [(x, BE, BZ0 + 10), (x, BL + 0.7, BZ0 + 11), (x, BL + 0.7, BTOP + 1.5), (x, 22, BTOP + 2.2),
                               (x, 18.05, BTOP + 2.9)], m, 0.45, ["LiPo end", "Balance plug"])

# car side of the JST plug: both wires run forward over the tray's front edge.
# Red drops down in front of the tray, runs under the left edge of the board and down through the plate to the switch.
# Black drops onto the power terminal (GND). The switch's other tab comes back up and runs under the board to the
# power terminal (+).
(hx, hy), (vx, vy) = SW_HOLES
RL = 25.5                          # red's path under the board's left edge
wire("JST red to switch", [(JX + 1.2, JY - 6.05, BTZ), (JX + 1.2, JY - 7.5, BTZ), (-55.0, JY - 7.5, BTZ), (-55.0, RL, PZ + 6),
                           (-55.0, RL, PZ + 2.3), (hx, RL, PZ + 2.3), (hx, hy, PZ + 2.3), (hx, hy, PZ0 - 1.5), (hx + 0.5, 32, ST),
                           (SWT[2], SWY - 1, ST), (SWT[2], SWY, ST)], M["red"], 0.8, ["JST plug car", "Switch tab 2"])
x, y, _ = t_end(2, 16)
wire("JST black to GND", [(JX - 1.2, JY - 6.05, BTZ), (JX - 1.2, JY - 10, BTZ), (-51.5, JY - 10, BTZ), (-51.5, y, TE + 3),
                          (-51.5, y, TE), (-46, y, TE), (x, y, TE)], M["black"], 0.8, ["JST plug car", "Terminal power"])
x, y, _ = t_end(2, 14)
VL = ph(0, 13)[1]                  # path under the board
wire("Switch to VIN", [(SWT[1], SWY, ST), (SWT[1], SWY - 1, ST), (vx, 32, ST), (vx, vy, PZ0 - 1.5), (vx, vy, PZ + 2.3),
                       (vx, VL, PZ + 2.3), (-52.5, VL, PZ + 2.3), (-52.5, y, TE), (-46, y, TE), (x, y, TE)],
     M["red"], 0.8, ["Switch tab 1", "Terminal power"])

# Servo cable: out of the servo, back over the servo box, down onto the servo plug at the board's front edge
RB = SB0 - 1.2                     # where the cable drops, just behind the servo box
PZW = TOP + 1.3                    # plug height
ys = ph(23, 14)[1]
wire("Servo cable", [(SX, SY0 + SV_L - 0.05, SV_FACE + 19.5), (SX, 18.0, 31.0), (44, 18.0, 31.0), (40, 14.5, 31.2),
                     (RB, ys, 31.2), (RB, ys, DT + 0.5), (PLUG_X + 16.5, ys, PZW), (PLUG_X + 13.5, ys, PZW)],
     M["brown"], 1.0, ["MG90S servo", "Servo plug"])

# Finish: lift, camera, light, save
# lift the whole car so the tires sit on the ground
for o in bpy.data.objects:
    if o.type == "MESH" and o.parent is None:
        o.data.transform(Matrix.Translation((0, 0, LIFT)))
    elif o.type == "CURVE":
        for p in o.data.splines[0].points:
            p.co.z += LIFT
    elif o.type == "EMPTY":
        o.location.z += LIFT
bpy.context.view_layer.update()
pose(0.0)
cam_d = bpy.data.cameras.new("View"); cam_d.clip_end = 5000; cam_d.clip_start = 1
cam = bpy.data.objects.new("View camera", cam_d); C_HELP.objects.link(cam)
cam.location = (300, -230, 210)
cam.rotation_euler = (Vector((0, 0, 30)) - cam.location).to_track_quat("-Z", "Y").to_euler()
sc.camera = cam
sun_d = bpy.data.lights.new("Sun", "SUN"); sun_d.energy = 3
sun = bpy.data.objects.new("Sun", sun_d); C_HELP.objects.link(sun); sun.rotation_euler = (math.radians(35), math.radians(15), math.radians(30))
w = bpy.data.worlds.new("World"); sc.world = w; w.color = (0.6, 0.62, 0.66)
# steering animation: frames 1 to 120 turn left, then right, then back to straight
for f, th in ((1, 0.0), (30, STEER_MAX), (90, -STEER_MAX), (120, 0.0)):
    sc.frame_set(f); pose(th); steer.keyframe_insert("rotation_euler")
sc.frame_start, sc.frame_end = 1, 120
sc.frame_set(1); pose(0.0)
bpy.context.preferences.filepaths.save_version = 0     # no rc_car.blend1 backup copy
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("saved", OUT, len(bpy.data.objects), "objects")

# Check
def world_bvh(o, dg):
    """the object's shape, shrunk by 0.08 so parts that only touch don't count as running into each other"""
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    bm = bmesh.new(); bm.from_mesh(me); bm.transform(o.matrix_world)
    bm.normal_update()
    for v in bm.verts:
        v.co -= v.normal * 0.08
    vs = [v.co.copy() for v in bm.verts]
    t = BVHTree.FromBMesh(bm) if vs else None
    bm.faces.ensure_lookup_table()
    cen = [f.calc_center_median() for f in bm.faces]
    bm.free(); ev.to_mesh_clear()
    if not vs:
        return None
    lo = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
    hi = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
    return t, lo, hi, cen

def near(a, b):
    """do the two bounding boxes touch?"""
    return all(a[1][i] <= b[2][i] and b[1][i] <= a[2][i] for i in range(3))

# parts that are meant to touch or sit inside each other (matched by part of the name)
ALLOWED = [
    ("N20 shaft", "Rear L hub"), ("N20 shaft", "Rear R hub"), ("N20 gearbox", "N20 shaft"), ("N20 tab", "N20 motor"),
    ("cap leg", "470uF capacitor"),
    ("Servo tab screw", "MG90S servo"), ("Servo tab screw", "Chassis plate"), ("Servo header", "Servo plug"),
    ("Servo horn", "MG90S servo"), ("Horn screw", "Servo horn"), ("Horn screw", "Steering beam"),
    ("Horn centre screw", "Servo horn"), ("Horn centre screw", "MG90S servo"),
    ("Switch tab", "Rocker switch"), ("Perf screw", "Chassis plate"), ("ESP32-C3 pins", "Brain socket"),
    ("LiPo end", "LiPo 2S"), ("JST plug battery", "JST plug car"),
]

def allowed(a, b, wire_ends):
    for p, q in ALLOWED:
        if (p in a and q in b) or (p in b and q in a):
            return True
    return (a, b) in wire_ends or (b, a) in wire_ends

def seg_dist(p1, q1, p2, q2):
    """shortest distance between the line pieces p1-q1 and p2-q2"""
    d1, d2, r = q1 - p1, q2 - p2, p1 - p2
    a, e, f = d1.dot(d1), d2.dot(d2), d2.dot(r)
    c, b = d1.dot(r), d1.dot(d2)
    den = a * e - b * b
    s_ = min(max((b * f - c * e) / den, 0), 1) if den > 1e-9 else 0.0
    t = (b * s_ + f) / e if e > 1e-9 else 0.0
    if t < 0:
        t, s_ = 0.0, min(max(-c / a, 0), 1) if a > 1e-9 else 0.0
    elif t > 1:
        t, s_ = 1.0, min(max((b - c) / a, 0), 1) if a > 1e-9 else 0.0
    return ((p1 + d1 * s_) - (p2 + d2 * t)).length

def wire_pairs():
    """wires whose centre lines are closer than their two radii (they would lie in each other)"""
    lines = {o.name: ([Vector(p.co[:3]) for p in o.data.splines[0].points], o.data.bevel_depth) for o, _ in WIRES}
    out = []
    names = list(lines)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if a.startswith("Trace") and b.startswith("Trace") and a.split()[1] == b.split()[1]:
                continue            # traces of the same signal are meant to meet at a hole
            pa, ra = lines[a]; pb, rb = lines[b]
            d = min(seg_dist(pa[k], pa[k + 1], pb[j], pb[j + 1]) for k in range(len(pa) - 1) for j in range(len(pb) - 1))
            if d < ra + rb - 0.15:
                out.append((a, b, round(d, 2)))
    return out

def run_check():
    pose(0.0)
    wire_ends = {(o.name, t) for o, ends in WIRES for _, t in ends}
    wnames = {o.name for o, _ in WIRES}
    report = []
    for th, name in ((0.0, "straight"), (STEER_MAX, "full left"), (-STEER_MAX, "full right")):
        pose(th)
        dg = bpy.context.evaluated_depsgraph_get(); dg.update()
        data = {o.name: world_bvh(o, dg) for o in bpy.data.objects if o.type in ("MESH", "CURVE")}
        names = [n for n in data if data[n]]
        hits = []
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                if (a in wnames and b in wnames) or not near(data[a], data[b]) or allowed(a, b, wire_ends):
                    continue
                ov = data[a][0].overlap(data[b][0])
                if ov:
                    c = sum((data[a][3][i] for i, _ in ov), Vector()) / len(ov)
                    hits.append((a, b, len(ov), tuple(round(v, 1) for v in c)))
        report.append((name, hits))
    # every wire end must sit on (or in) the part it is meant to end on
    dg = bpy.context.evaluated_depsgraph_get()
    bad = []
    for o, ends in WIRES:
        for p, tgt in ends:
            t = bpy.data.objects.get(tgt)
            if t is None:
                bad.append((o.name, tgt, "missing")); continue
            p = Vector(p) + Vector((0, 0, LIFT))
            ok, loc, nor, _ = t.evaluated_get(dg).closest_point_on_mesh(t.matrix_world.inverted() @ p)
            wl = t.matrix_world @ loc
            dist = (wl - Vector(p)).length if ok else 99
            inside = ok and (t.matrix_world.to_3x3() @ nor).dot(Vector(p) - wl) < 0
            if dist > max(1.0, o.data.bevel_depth + 0.3) and not inside:
                bad.append((o.name, tgt, round(dist, 2)))
    return report, bad

if "--check" in ARGS:
    rep, bad = run_check()
    wp = wire_pairs()
    print("== wires lying in each other:", len(wp))
    for w_ in wp:
        print("  ", w_)
    for name, hits in rep:
        print(f"== {name}: {len(hits)} parts running into each other")
        for a, b, n, c in sorted(hits):
            print(f"   {a}  <->  {b}  ({n})  near {c}")
    print("== printed part sizes (a broken cut shows up here):")
    for o in C_PRINT.objects:
        print("  ", o.name, [round(v, 1) for v in o.dimensions])
    print("== wire ends not on their part:", len(bad))
    for b in bad:
        print("  ", b)
