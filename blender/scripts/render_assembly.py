# Renders the black-and-white line pictures for the assembly guide (make_assembly_guide.py).
#
#   Blender --background blender/rc_car.blend --python blender/scripts/render_assembly.py -- IMG_DIR [view ...]
#
# Every picture: parts already on the car in thin lines, the parts of this step in thick lines,
# pulled out along the way they go in (exploded). Writes IMG_DIR/<view>.png and IMG_DIR/<view>.json
# (label anchor points and insert-path end points, 0..1 from the bottom left of the picture).
#
# The main board in the .blend still has the old layout, so this script rebuilds it from
# kicad/main-board/scripts/design.py (terminals row B, driver H/N 11-16, Mini360 F3/F7/L3/L7,
# cap P1/P3, servo plug T2-V2) and moves the wire ends to the new terminals.
import bpy, os, sys, math, json
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector, Matrix

ARGV = sys.argv[sys.argv.index("--") + 1:]
OUT = ARGV[0]
ONLY = set(ARGV[1:])
os.makedirs(OUT, exist_ok=True)
sc = bpy.context.scene

# ---------------------------------------------------------------- materials / collections
def flat(name, rgb):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    e = nt.nodes.new("ShaderNodeEmission"); e.inputs["Color"].default_value = (*rgb, 1); e.inputs["Strength"].default_value = 1
    o = nt.nodes.new("ShaderNodeOutputMaterial"); nt.links.new(e.outputs[0], o.inputs[0])
    return m

WHITE, BLACK = flat("white", (1, 1, 1)), flat("black", (0, 0, 0))
NEWC = bpy.data.collections.new("NEW"); sc.collection.children.link(NEWC)
EXTRA = bpy.data.collections.new("Extra"); sc.collection.children.link(EXTRA)

# unparent everything (keep where it is), so moving one part never drags another
for o in bpy.data.objects:
    if o.parent:
        mw = o.matrix_world.copy(); o.parent = None; o.matrix_world = mw

# ---------------------------------------------------------------- the main board, as in design.py
TOP = 38.1                                  # board top (world)
ROWS = "ABCDEFGHIJKLMNOPQRSTUVWX"
def H(hole, z=TOP):
    """world position of a KiCad hole like 'B14' (row A back .. X front, column 1 car left .. 18)"""
    i, c = ROWS.index(hole[0]), int(hole[1:])
    return Vector((-44.2 + 2.54 * i, -21.59 + 2.54 * (18 - c), z))

def add_box(name, x0, x1, y0, y1, z0, z1, coll=EXTRA):
    bpy.ops.mesh.primitive_cube_add(size=1, location=((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
    o = bpy.context.object; o.name = name; o.scale = (x1 - x0, y1 - y0, z1 - z0)
    bpy.ops.object.transform_apply(scale=True)
    for c in o.users_collection: c.objects.unlink(o)
    coll.objects.link(o); return o

def add_cyl(name, c, r, d, axis="z", n=32, coll=EXTRA):
    bpy.ops.mesh.primitive_cylinder_add(vertices=n, radius=r, depth=d, location=c)
    o = bpy.context.object; o.name = name
    if axis == "x": o.rotation_euler = (0, math.pi / 2, 0)
    if axis == "y": o.rotation_euler = (math.pi / 2, 0, 0)
    bpy.ops.object.transform_apply(rotation=True)
    for cc in o.users_collection: cc.objects.unlink(o)
    coll.objects.link(o); return o

def join(name, objs):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join(); objs[0].name = name; return objs[0]

OLD_BOARD = ["Terminal motor R", "Terminal motor L", "Terminal power", "DRV8833 header", "DRV8833", "Mini360 pins",
             "Mini360 5V", "470uF capacitor", "cap leg", "cap leg.001", "Battery resistor 47k", "Battery resistor 10k",
             "Servo header", "Servo plug", "Top wire 5V", "Top wire battery sense", "Servo cable"]
for n in OLD_BOARD:
    bpy.data.objects[n].hide_render = True; bpy.data.objects[n]["gone"] = True
for o in bpy.data.objects:
    if o.name.startswith("Trace"):
        o.hide_render = True; o["gone"] = True

def terminal(name, a, b):
    """2-pin screw terminal, wire openings to the back, screws on top"""
    pa, pb = H(a), H(b)
    t = add_box(name, pa.x - 3.75, pa.x + 3.75, pb.y - 2.5, pa.y + 2.5, TOP + 0.05, TOP + 10)
    parts = [t]
    for p in (pa, pb):
        parts.append(add_cyl("s", (p.x + 0.6, p.y, TOP + 10.3), 1.5, 0.6, n=20))
        parts.append(add_box("o", p.x - 3.9, p.x - 3.7, p.y - 1.2, p.y + 1.2, TOP + 2.4, TOP + 4.8))
    return join(name, parts)

terminal("New terminal battery", "B1", "B3")
terminal("New terminal motor B", "B10", "B12")
terminal("New terminal motor A", "B14", "B16")
# HW-627 on two 6-pin sockets, rows H and N, columns 11-16
h0, h1 = H("H11"), H("N16")
join("New driver", [add_box("sk", h0.x - 1.27, h0.x + 1.27, h1.y - 1.27, h0.y + 1.27, TOP + 0.05, TOP + 8.5),
                    add_box("sk", h1.x - 1.27, h1.x + 1.27, h1.y - 1.27, h0.y + 1.27, TOP + 0.05, TOP + 8.5),
                    add_box("pcb", h0.x - 1.6, h1.x + 1.6, h1.y - 2.0, h0.y + 2.0, TOP + 11.0, TOP + 12.6),
                    add_box("chip", (h0.x + h1.x) / 2 - 3, (h0.x + h1.x) / 2 + 3, (h0.y + h1.y) / 2 - 2.5, (h0.y + h1.y) / 2 + 2.5, TOP + 12.5, TOP + 13.5)])
# Mini360 on 4 corner pins, F3 F7 L3 L7
m0, m1 = H("F3"), H("L7")
join("New Mini360", [add_box("pcb", m0.x - 1.2, m1.x + 1.2, m1.y - 1.8, m0.y + 1.8, TOP + 2.6, TOP + 4.1),
                     add_box("coil", (m0.x + m1.x) / 2 - 3, (m0.x + m1.x) / 2 + 3, (m0.y + m1.y) / 2 - 3, (m0.y + m1.y) / 2 + 3, TOP + 4.0, TOP + 6.5),
                     add_box("pot", m1.x - 4.5, m1.x - 1.0, m0.y - 3.5, m0.y - 0.3, TOP + 4.0, TOP + 7.0)])
# 470uF standing between P1 and P3
c0, c1 = H("P1"), H("P3")
add_cyl("New capacitor", ((c0.x + c1.x) / 2, (c0.y + c1.y) / 2, TOP + 7.2), 4.0, 12.0)
# resistors lying flat
r0, r1 = H("P10"), H("S10")
add_cyl("New 47k", ((r0.x + r1.x) / 2, r0.y, TOP + 1.4), 1.2, 6.2, "x", 16)
r0, r1 = H("U14"), H("U17")
add_cyl("New 10k", (r0.x, (r0.y + r1.y) / 2, TOP + 1.4), 1.2, 6.2, "y", 16)
# straight 3-pin servo header T2 U2 V2, servo plug pushed down onto it
s0, s1 = H("T2"), H("V2")
add_box("New servo header", s0.x - 1.27, s1.x + 1.27, s0.y - 1.27, s0.y + 1.27, TOP + 0.05, TOP + 2.5)
add_box("Servo plug new", s0.x - 1.3, s1.x + 1.3, s0.y - 1.3, s0.y + 1.3, TOP + 2.6, TOP + 16.6)

def curve(name, pts, r, coll=EXTRA):
    cu = bpy.data.curves.new(name, "CURVE"); cu.dimensions = "3D"; cu.bevel_depth = r; cu.bevel_resolution = 3
    sp = cu.splines.new("POLY"); sp.points.add(len(pts) - 1)
    for p, q in zip(sp.points, pts): p.co = (*q, 1)
    o = bpy.data.objects.new(name, cu); coll.objects.link(o); return o

# insulated 3V3 wire on top: T16 -> T9 -> G9 -> G16
curve("New top wire 3V3", [H(h, TOP + 0.9) for h in ("T16", "T9", "G9", "G16")], 0.55)
# servo cable: same path from the servo, then down onto the new plug
old = bpy.data.objects["Servo cable"]
pts = [old.matrix_world @ p.co.to_3d() for p in old.data.splines[0].points]
pts = [p for p in pts if p.x > 33]
top = H("U2", TOP + 16.6)
pts += [Vector((22, 18.5, 52)), Vector((top.x + 4, top.y, top.z + 3)), Vector((top.x, top.y, top.z + 1.5)), top]
curve("Servo cable new", pts, 1.0)

# wire ends moved from the old terminals to the new ones: x one row back, y by the column change
MOVE_Y = {"Motor L+": -2.54, "Motor L-": -2.54, "Motor R+": -2.54, "Motor R-": -2.54,
          "JST black to GND": 2.54, "Switch to VIN": 2.54}
for n, dy in MOVE_Y.items():
    o = bpy.data.objects[n]; inv = o.matrix_world.inverted()
    for p in o.data.splines[0].points:
        w = o.matrix_world @ p.co.to_3d()
        if w.z > 40.5 and w.x > -50.5:
            p.co = (*(inv @ (w + Vector((-2.54, dy, 0)))), 1)

# screws that are not in the .blend: bumper tabs into the servo box top
def screw(name, head_top, length, down, r=1.5, hr=2.75, hh=3.0):
    """M3 (or M2 with r=1) cap screw: head at head_top, shaft going `down`"""
    d = Vector(down).normalized(); ht = Vector(head_top)
    hd = add_cyl(name, ht + d * hh / 2, hr, hh, n=28)
    sh = add_cyl("sh", ht + d * (hh + length / 2), r, length, n=20)
    o = join(name, [hd, sh])
    o.rotation_mode = "QUATERNION"
    q = Vector((0, 0, -1)).rotation_difference(d)
    # rotate about head top
    o.matrix_world = Matrix.Translation(ht) @ q.to_matrix().to_4x4() @ Matrix.Translation(-ht) @ o.matrix_world
    return o

for k, y in enumerate((-17.5, 17.5)):
    screw(f"bumper tab screw M3x8 {k + 1}", (81, y, 44.5 + 0.05), 8, (0, 0, -1))

# ---------------------------------------------------------------- render settings
sc.render.engine = "BLENDER_EEVEE"
sc.view_settings.view_transform = "Standard"
sc.render.film_transparent = True
sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGBA"
sc.render.use_freestyle = True
sc.render.line_thickness_mode = "ABSOLUTE"
fs = sc.view_layers[0].freestyle_settings
fs.crease_angle = math.radians(140)
for l in list(fs.linesets): fs.linesets.remove(l)

def lineset(name, thick, negate):
    ls = fs.linesets.new(name)
    ls.select_by_visibility = True; ls.visibility = "VISIBLE"
    ls.select_silhouette = ls.select_border = ls.select_crease = ls.select_contour = True
    ls.select_by_collection = True; ls.collection = NEWC
    ls.collection_negation = "EXCLUSIVE" if negate else "INCLUSIVE"
    ls.linestyle = bpy.data.linestyles.new(name); ls.linestyle.color = (0, 0, 0); ls.linestyle.thickness = thick
    return ls

lineset("old", 2.6, True)
lineset("new", 5.0, False)

for o in bpy.data.objects:
    if o.type in ("MESH", "CURVE") and o.data is not None:
        o.data.materials.clear(); o.data.materials.append(WHITE)

cam_d = bpy.data.cameras.new("asm"); cam_d.type = "ORTHO"; cam_d.clip_end = 10000
cam = bpy.data.objects.new("asm cam", cam_d); sc.collection.objects.link(cam); sc.camera = cam

# ---------------------------------------------------------------- groups of parts
G = {}
def g(name, *names):
    out = []
    for n in names:
        if n.endswith("*"):
            out += [o.name for o in bpy.data.objects if o.name.startswith(n[:-1]) and not o.get("gone")]
        else:
            out.append(n)
    G[name] = out

g("plate", "Chassis plate")
g("motors", "N20 gearbox L", "N20 motor L", "N20 shaft L", "N20 tab La", "N20 tab Lb", "N20 bracket L",
  "N20 gearbox R", "N20 motor R", "N20 shaft R", "N20 tab Ra", "N20 tab Rb", "N20 bracket R")
g("motor wires", "Motor L+", "Motor L-", "Motor R+", "Motor R-")
g("bracket screws", "Bracket screw*")
g("bracket nuts", "Bracket nut*")
g("servo", "MG90S servo")
g("servo screws", "Servo tab screw*")
g("horn", "Servo horn")
g("horn centre", "Horn centre screw")
g("beam", "Steering beam")
g("horn screws", "Horn screw M2x8*")
g("front wheels", "Front L tire", "Front L hub", "Front R tire", "Front R hub")
g("washers in", "Front washer in*")
g("washers out", "Front washer out*")
g("axle bolts", "Front axle bolt*")
g("rear wheels", "Rear L tire", "Rear L hub", "Rear R tire", "Rear R hub")
g("box", "Servo box")
g("box screws", "servo box screw*")
g("bumper", "Front bumper", "Bumper stripe L", "Bumper stripe R")
g("bumper screws", "bumper screw*")
g("bumper tab screws", "bumper tab screw*")
g("hook", "Tow hook")
g("hook screws", "tow hook screw*")
g("switch", "Rocker switch", "Switch tab 1", "Switch tab 2")
g("switch wires", "JST red to switch", "Switch to VIN", "JST black to GND")
g("board", "Perf board", "Perf board pads", "New terminal battery", "New terminal motor B", "New terminal motor A",
  "New driver", "New Mini360", "New capacitor", "New 47k", "New 10k", "New servo header", "New top wire 3V3",
  "Brain socket A", "Brain socket B", "ESP32-C3 SuperMini", "ESP32-C3 USB-C", "ESP32-C3 pins A", "ESP32-C3 pins B")
g("board screws", "Perf screw*")
g("servo plug", "Servo plug new", "Servo cable new")
g("tray", "Battery tray")
g("tray screws", "Tray screw*")
g("antenna", "Antenna")
g("battery", "LiPo 2S 1200mAh", "LiPo end", "LiPo label*", "PH2.0 plug", "Balance plug", "PH2.0 lead*", "Balance lead*",
  "Battery lead red", "Battery lead black", "JST plug battery", "JST plug car")
ALL_GROUPS = list(G)

def ctr(names):
    pts = []
    for n in names:
        o = bpy.data.objects[n]
        pts += [o.matrix_world @ Vector(c) for c in o.bound_box]
    return sum(pts, Vector()) / len(pts)

def bbox(names):
    pts = []
    for n in names:
        o = bpy.data.objects[n]
        pts += [o.matrix_world @ Vector(c) for c in o.bound_box]
    return pts

# ---------------------------------------------------------------- views
# camera direction is from the car toward the camera, in car axes (front +X, left +Y, up +Z).
# flip=True: the car is upside down on the table (looked at from underneath, top of picture = down).
ISO = (1.0, -1.15, 0.85)
UNDER = (1.0, 1.15, -0.85)          # flipped car, seen like ISO
X = lambda v: Vector(v)

V = {}
def view(name, show, new, explode, cam_dir, up=(0, 0, 1), size=(2400, 1500), anchors=None, paths=(), focus=None, pad=1.06):
    V[name] = dict(show=show, new=new, explode=explode, cam_dir=cam_dir, up=up, size=size, anchors=anchors or {},
                   paths=paths, focus=focus, pad=pad)

BUILT = []
def upto(*gs):
    return [x for x in gs]

# reference / cover
everything = [k for k in ALL_GROUPS]
view("cover", everything, [], {}, (1.0, -1.25, 0.75), size=(2600, 1500))

# 1 motors: car upside down, motor + bracket lifted off the plate, nuts above that; screws already pushed through from the top
view("motors", ["plate", "motors", "bracket screws", "bracket nuts", "motor wires"],
     ["motors", "bracket screws", "bracket nuts", "motor wires"],
     {"motors": (0, 0, -16), "motor wires": (0, 0, -16), "bracket nuts": (0, 0, -30)},
     UNDER, up=(0, 0, -1),
     anchors={"MOTOR + BRACKET x2": ("N20 bracket R", (0, -14, -24)), "M2 NUT x4": ("Bracket nut M2 R1", (0, 0, -30)),
              "M2 x 8 x4": ("Bracket screw M2x8 R2", (0, 0, 0)), "WIRES UP THROUGH SLOT": ((-53, 0, 26.5), None),
              "FRONT": ((92, 0, 30), None)},
     paths=[("Bracket screw M2x8 R1", (0, 0, 0), (0, 0, -30)), ("Bracket screw M2x8 R2", (0, 0, 0), (0, 0, -30)),
            ("Bracket screw M2x8 L1", (0, 0, 0), (0, 0, -30)), ("Bracket screw M2x8 L2", (0, 0, 0), (0, 0, -30))],
     focus=None)

# 2 servo: car right way up, servo dropped in from the top, wire first
view("servo", ["plate", "motors", "bracket screws", "motor wires", "servo", "servo screws"],
     ["servo", "servo screws"], {"servo": (0, 0, 30), "servo screws": (0, 0, 52)},
     (1.0, -1.2, 1.1),
     anchors={"SERVO": ("MG90S servo", (-6, -14, 30)), "SHAFT DOWN": ((56, 0, 22), (0, 0, 30)),
              "ITS 2 SCREWS": ("Servo tab screw", (0, 0, 52)), "FRONT": ((92, 0, 36), None)},
     paths=[("Servo tab screw", (0, 0, 52), (0, 0, 30)), ("Servo tab screw.001", (0, 0, 52), (0, 0, 30))],
     focus=None)

# 3 arm + beam: upside down, stack pulled off the shaft
view("beam", ["plate", "motors", "bracket screws", "motor wires", "servo", "horn", "horn centre", "beam", "horn screws"],
     ["horn", "horn centre", "beam", "horn screws"],
     {"horn": (0, 0, -14), "horn centre": (0, 0, -26), "beam": (0, 0, -40), "horn screws": (0, 0, -58)},
     UNDER, up=(0, 0, -1),
     anchors={"SERVO ARM": ("Servo horn", (0, -14, -14)), "ARM SCREW": ("Horn centre screw", (0, 0, -26)),
              "BEAM": ("Steering beam", (0, -30, -40)), "M2 x 8 x2": ("Horn screw M2x8 R", (0, 0, -58)),
              "FRONT": ((92, 0, 30), None)},
     paths=[("Horn screw M2x8 R", (0, 0, -58), (0, 0, -14)), ("Horn screw M2x8 L", (0, 0, -58), (0, 0, -14)),
            ((56, 0, 22), (0, 0, 0), (0, 0, -26))],
     focus=None)

# servo close-ups -------------------------------------------------------------
SERVO_ON = ["plate", "motors", "bracket screws", "motor wires", "servo", "servo screws"]
CLOSE = ["MG90S servo", "Servo tab screw", "Servo tab screw.001"]
# a: servo dropped in from the top, wire end toward the car's left
view("servo-in", SERVO_ON, ["servo", "servo screws"], {"servo": (0, 0, 46), "servo screws": (0, 0, 74)},
     (0.8, -1.0, 1.7),
     anchors={"SERVO": ("MG90S servo", (0, 0, 0)), "WIRE": ((57, 19, 41 + 46), None),
              "SHAFT": ((56, 0, 21.7 + 46), None), "SCREWS": ("Servo tab screw", (0, 0, 0)),
              "FRONT": ((78, -20, 36.5), None)},
     paths=[("Servo tab screw", (0, 0, 74), (0, 0, 46)), ("Servo tab screw.001", (0, 0, 74), (0, 0, 46)),
            ((56, 0, 0), (0, 0, 21 + 46), (0, 0, 37))],
     focus=CLOSE, pad=1.6, size=(2200, 1500))
# b: arm + arm screw, car upside down
view("arm", SERVO_ON + ["horn", "horn centre"], ["horn", "horn centre"], {"horn": (0, 0, -16), "horn centre": (0, 0, -32)},
     UNDER, up=(0, 0, -1),
     anchors={"ARM": ("Servo horn", (0, 0, 0)), "ARM SCREW": ("Horn centre screw", (0, 0, 0)),
              "FRONT": ((80, 0, 36.5), None)},
     paths=[((56, 0, 0), (0, 0, -14), (0, 0, 21))],
     focus=CLOSE + ["Servo horn"], pad=1.35, size=(2200, 1500))
# b2: arm seen straight from underneath: straight across the car
view("arm-under", SERVO_ON + ["horn", "horn centre"], ["horn", "horn centre"], {}, (0.0001, 0, -1), up=(1, 0, 0),
     anchors={"ARM": ("Servo horn", (0, 12, 0))},
     focus=["MG90S servo", "Servo horn"], pad=2.2, size=(1400, 1400))
# c: beam + 2 screws, car upside down
view("beam-on", SERVO_ON + ["horn", "horn centre", "beam", "horn screws"], ["beam", "horn screws"],
     {"beam": (0, 0, -18), "horn screws": (0, 0, -40)},
     UNDER, up=(0, 0, -1),
     anchors={"BEAM": ("Steering beam", (0, -30, 0)), "M2 x 8": ("Horn screw M2x8 R", (0, 0, 0)),
              "FRONT": ((80, 0, 36.5), None)},
     paths=[("Horn screw M2x8 R", (0, 0, -40), (0, 0, 0)), ("Horn screw M2x8 L", (0, 0, -40), (0, 0, 0))],
     focus=CLOSE + ["Steering beam"], pad=1.3, size=(2200, 1500))

# 4 wheels: right way up, seen from the front right, wheels pulled out sideways
view("wheels", ["plate", "motors", "bracket screws", "motor wires", "servo", "servo screws", "horn", "horn centre", "beam",
                "horn screws", "front wheels", "washers in", "washers out", "axle bolts", "rear wheels"],
     ["front wheels", "washers in", "washers out", "axle bolts", "rear wheels"],
     {"Front R tire": (0, -22, 0), "Front R hub": (0, -22, 0), "Front washer out R": (0, -40, 0), "Front axle bolt M3x30 R": (0, -56, 0),
      "Front washer in R": (0, -10, 0),
      "Front L tire": (0, 22, 0), "Front L hub": (0, 22, 0), "Front washer out L": (0, 40, 0), "Front axle bolt M3x30 L": (0, 56, 0),
      "Front washer in L": (0, 10, 0),
      "Rear R tire": (0, -26, 0), "Rear R hub": (0, -26, 0), "Rear L tire": (0, 26, 0), "Rear L hub": (0, 26, 0)},
     (0.75, -1.3, 0.75),
     anchors={"FRONT STACK": ("Front axle bolt M3x30 R", (0, -56, 0)), "PUSH ON (D SHAFT)": ("Rear R tire", (0, -26, 0)),
              "FRONT": ((100, 0, 25), None)},
     paths=[((56, -36, 21.5), (0, 0, 0), (0, -88, 0)), ((-64, -31, 21.2), (0, 0, 0), (0, -30, 0))],
     focus=None, size=(2600, 1500))

# 4b front wheel stack, close up from the front: bolt, washer, wheel, washer, beam end
view("wheel-stack", ["horn", "beam", "Front R tire", "Front R hub", "Front washer in R", "Front washer out R", "Front axle bolt M3x30 R"],
     ["Front R tire", "Front R hub", "Front washer in R", "Front washer out R", "Front axle bolt M3x30 R"],
     {"Front R tire": (0, -24, 0), "Front R hub": (0, -24, 0), "Front washer out R": (0, -46, 0),
      "Front axle bolt M3x30 R": (0, -86, 0), "Front washer in R": (0, -10, 0)},
     (1.0, -0.3, 0.45),
     anchors={"M3 x 30": ("Front axle bolt M3x30 R", (0, -86, 0)), "WASHER": ("Front washer out R", (0, -46, 0)),
              "WHEEL": ("Front R tire", (0, -24, 0)), "WASHER ": ("Front washer in R", (0, -10, 0)),
              "INSERT": ((56, -36, 21.5), None)},
     paths=[((56, -36, 21.5), (0, 0, 0), (0, -112, 0))],
     focus=None,
     size=(2200, 1300))

# 5 servo box + bumper (top side)
FRONT_ON = ["plate", "motors", "bracket screws", "motor wires", "servo", "servo screws", "horn", "horn centre", "beam",
            "horn screws", "front wheels", "washers in", "washers out", "axle bolts", "rear wheels"]
SIDE = (0, -1, 0.0001)           # straight from the car's right side, front to the right
BOX_ON = FRONT_ON + ["box", "box screws"]
NO_WHEELS = [g_ for g_ in FRONT_ON if g_ not in ("front wheels", "washers in", "washers out", "axle bolts", "rear wheels")] + ["box", "box screws"]
BUMP = ["bumper", "bumper screws", "bumper tab screws"]

# 5 servo box: straight side view, box lifted, 4 screws below the plate
view("box-side", NO_WHEELS, ["box", "box screws"], {"box": (0, 0, 24), "box screws": (0, 0, -24)}, SIDE,
     anchors={"SERVO BOX": ("Servo box", (0, 0, 0)), "M3 x 8 x4": ("servo box screw M3x8 3", (0, 0, 0))},
     paths=[("servo box screw M3x8 3", (0, 0, -24), (0, 0, -6)), ("servo box screw M3x8 1", (0, 0, -24), (0, 0, -6)),
            ((60, 0, 41.5), (0, 0, 21), (0, 0, 2))],
     size=(2600, 1000))
view("box-iso", BOX_ON, ["box", "box screws"], {}, (0.9, -1.25, 0.8), size=(1800, 1200),
     anchors={"SERVO BOX": ("Servo box", (0, 0, 0))})

# 6 bumper: straight side view, bumper pulled forward, 2 screws on top (tabs), 2 below (tongue)
view("bumper-side", NO_WHEELS + BUMP, BUMP,
     {"bumper": (40, 0, 0), "bumper tab screws": (40, 0, 26), "bumper screws": (40, 0, -24)}, SIDE,
     anchors={"BUMPER": ("Front bumper", (0, 0, 0)), "M3 x 8 x2 TOP": ("bumper tab screw M3x8 1", (0, 0, 0)),
              "M3 x 8 x2 UNDER": ("bumper screw M3x8 1", (0, 0, 0))},
     paths=[("bumper tab screw M3x8 1", (40, 0, 26), (40, 0, 7)), ("bumper screw M3x8 1", (40, 0, -24), (40, 0, -6)),
            ((84, 0, 24), (36, 0, 0), (4, 0, 0))],
     size=(2600, 1000))
view("bumper-iso", BOX_ON + BUMP, BUMP, {}, (0.9, -1.25, 0.8), size=(1800, 1200),
     anchors={"BUMPER": ("Front bumper", (0, 0, 0))})

view("hook", BOX_ON + BUMP + ["hook", "hook screws"],
     ["hook", "hook screws"], {"hook": (0, 0, -14), "hook screws": (0, 0, -34)},
     (-1.0, 1.1, -0.9), up=(0, 0, -1),
     anchors={"TOW HOOK": ("Tow hook", (0, 0, -14)), "M3 x 8 x2": ("tow hook screw M3x8 1", (0, 0, -34)),
              "BACK": ((-96, 0, 30), None)},
     paths=[("tow hook screw M3x8 1", (0, 0, -34), (0, 0, -14)), ("tow hook screw M3x8 2", (0, 0, -34), (0, 0, -14))],
     focus=None)

# 7 switch: snaps into the wing from the top
AFTER_HOOK = FRONT_ON + ["box", "box screws", "bumper", "bumper screws", "bumper tab screws", "hook", "hook screws"]
view("switch", AFTER_HOOK + ["switch"], ["switch"], {"switch": (0, 0, 34)},
     (0.5, 1.2, 0.9),
     anchors={"SWITCH": ("Rocker switch", (0, 0, 34)), "SNAP IN FROM TOP": ((-30, 38, 36.5), None),
              "FRONT": ((92, 0, 36), None)},
     paths=[((-30, 38, 36.5), (0, 0, 22), (0, 0, 2))],
     focus=None)

# 8 main board on its 4 posts
AFTER_SW = AFTER_HOOK + ["switch"]
view("board", AFTER_SW + ["board", "board screws"], ["board", "board screws"],
     {"board": (0, 0, 26), "board screws": (0, 0, 48)},
     (0.7, -1.2, 1.25),
     anchors={"MAIN BOARD": ("Perf board", (0, -20, 26)), "M2 x 6 x4": ("Perf screw M2x6 4", (0, 0, 48)),
              "USB": ("ESP32-C3 USB-C", (0, 0, 26)), "TERMINALS TO THE BACK": ("New terminal motor A", (0, 0, 26)),
              "FRONT": ((100, 0, 30), None)},
     paths=[(f"Perf screw M2x6 {i}", (0, 0, 48), (0, 0, 26)) for i in (1, 2, 3, 4)],
     size=(2600, 1600))

# 9 wires: straight down on the board area
AFTER_BOARD = AFTER_SW + ["board", "board screws"]
view("wires", AFTER_BOARD + ["motor wires", "switch wires", "servo plug"], ["motor wires", "switch wires", "servo plug"],
     {}, (0.0001, 0, 1), up=(1, 0, 0), size=(2400, 1700),
     anchors={"MOTOR A": ("New terminal motor A", (-8, 0, 0)), "MOTOR B": ("New terminal motor B", (-8, 0, 0)),
              "BATTERY": ("New terminal battery", (-8, 0, 0)), "SERVO PLUG": ("Servo plug new", (0, 0, 0)),
              "SWITCH": ("Rocker switch", (0, 0, 0)), "LEFT MOTOR": ("N20 motor L", (0, 0, 0)), "RIGHT MOTOR": ("N20 motor R", (0, 0, 0)),
              "FRONT": ((70, 0, 40), None)},
     focus=None, pad=1.08)

# 9b terminal row close up, from the top
view("wires-close", ["board", "board screws", "motors", "switch", "motor wires", "switch wires", "JST plug car", "Servo plug new"], ["motor wires", "switch wires"],
     {}, (0.0001, 0, 1), up=(1, 0, 0), size=(2200, 1500),
     anchors={"-": (tuple(H("B1", TOP + 11)), (-6, 0, 0)), "+": (tuple(H("B3", TOP + 11)), (-6, 0, 0)),
              "MOTOR B": ("New terminal motor B", (0, 0, 0)), "MOTOR A": ("New terminal motor A", (0, 0, 0)),
              "BATTERY": ("New terminal battery", (0, 0, 0)),
              "LEFT MOTOR": ("N20 motor L", (0, 0, 0)), "RIGHT MOTOR": ("N20 motor R", (0, 0, 0)),
              "SWITCH": ("Rocker switch", (0, 0, 0)), "SERVO": ("Servo plug new", (0, 0, 0))},
     focus=None, pad=1.15)

# 10 tray, antenna, battery
view("tray", AFTER_BOARD + ["motor wires", "switch wires", "servo plug", "tray", "tray screws", "antenna", "battery"],
     ["tray", "tray screws", "antenna", "battery"],
     {"tray": (0, 0, 24), "tray screws": (0, 0, 36), "antenna": (0, 0, 70), "battery": (0, 0, 58)},
     (-0.55, -1.2, 1.0),
     anchors={"BATTERY TRAY": ("Battery tray", (0, -14, 24)), "M3 x 6 x2": ("Tray screw M3x6 1", (0, 0, 36)),
              "ANTENNA": ("Antenna", (0, 0, 70)), "BATTERY (LAST)": ("LiPo 2S 1200mAh", (0, -16, 58)),
              "BACK": ((-96, 0, 30), None)},
     paths=[("Tray screw M3x6 1", (0, 0, 36), (0, 0, 24)), ("Tray screw M3x6 2", (0, 0, 36), (0, 0, 24)),
            ((-92.4, 22, 41.5), (0, 0, 70), (0, 0, 0))],
     focus=None, size=(2400, 1600))

# reference views
view("ref-top", everything, [], {}, (0.0001, 0, 1), up=(1, 0, 0), size=(2000, 1400))
view("ref-under", everything, [], {}, (0.0001, 0, -1), up=(1, 0, 0), size=(2000, 1400))
view("ref-side", everything, [], {}, (0, -1, 0.0001), size=(2400, 900),
     anchors={"PLATE": ((-15, 0, 26.5), None), "GROUND": ((-15, 0, 0), None)})
view("ref-back", everything, [], {}, (-1.0, 1.2, 0.8), size=(2000, 1300))

# ---------------------------------------------------------------- render
def names(groups):
    out = []
    for gname in groups:
        out += G[gname] if gname in G else [gname]
    return out

for vname, v in V.items():
    if ONLY and vname not in ONLY:
        continue
    show = set(names(v["show"])); new = set(names(v["new"]))
    for o in bpy.data.objects:
        if o.type in ("MESH", "CURVE"):
            o.hide_render = (o.name not in show) or bool(o.get("gone"))
    for o in list(NEWC.objects): NEWC.objects.unlink(o)
    for n in new: NEWC.objects.link(bpy.data.objects[n])
    # explode: group offsets, or single object offsets
    moved = []
    for key, d in v["explode"].items():
        for n in (G[key] if key in G else [key]):
            o = bpy.data.objects[n]; o.location += Vector(d); moved.append((o, Vector(d)))
    bpy.context.view_layer.update()

    RX, RY = v["size"]; sc.render.resolution_x, sc.render.resolution_y = RX, RY
    fnames = [f[:-1] if f.endswith("!") else f for f in (v["focus"] or [])]
    pts = bbox(names(fnames) if fnames else [n for n in show if not bpy.data.objects[n].get("gone")])
    for key, d in v["explode"].items():                   # keep exploded parts in the picture
        pts += bbox(G[key] if key in G else [key])
    if fnames and vname != "wires":
        pts += bbox(list(new))
    c = sum(pts, Vector()) / len(pts)
    vd = Vector(v["cam_dir"]).normalized()
    f = -vd; up = Vector(v["up"])
    r = f.cross(up).normalized(); u = r.cross(f)
    cam.matrix_world = Matrix((r, u, -f)).transposed().to_4x4()
    cam.location = c + vd * 1500
    bpy.context.view_layer.update()
    inv = cam.matrix_world.inverted()
    cp = [inv @ p for p in pts]
    w = max(p.x for p in cp) - min(p.x for p in cp); h = max(p.y for p in cp) - min(p.y for p in cp)
    mid = Vector(((max(p.x for p in cp) + min(p.x for p in cp)) / 2, (max(p.y for p in cp) + min(p.y for p in cp)) / 2, 0))
    cam.location = cam.location + cam.matrix_world.to_3x3() @ mid
    cam_d.ortho_scale = max(w, h * RX / RY) * v["pad"]
    bpy.context.view_layer.update()

    def proj(p):
        return list(world_to_camera_view(sc, cam, Vector(p))[:2])
    info = {"anchors": {}, "paths": [], "scale": RX / cam_d.ortho_scale}
    for label, (where, off) in v["anchors"].items():
        if isinstance(where, str):
            p = ctr([where])                               # already moved by the explode
        else:
            p = Vector(where) + Vector(off or (0, 0, 0))
        info["anchors"][label] = proj(p)
    for where, a, b in v["paths"]:
        base = ctr([where]) if isinstance(where, str) else Vector(where)
        if isinstance(where, str):                         # object already moved by `a`
            base = base - Vector(a)
        info["paths"].append([proj(base + Vector(a)), proj(base + Vector(b))])
    json.dump(info, open(os.path.join(OUT, vname + ".json"), "w"))
    sc.render.filepath = os.path.join(OUT, vname + ".png")
    bpy.ops.render.render(write_still=True)
    print("wrote", sc.render.filepath)
    for o, d in moved:
        o.location -= d
    bpy.context.view_layer.update()
