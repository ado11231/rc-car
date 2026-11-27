# Renders the black-and-white line pictures for the brass inserts guide (make_inserts_guide.py).
# Each picture shows one printed part from the side the inserts go in, with those insert holes filled black.
#
#   Blender --background blender/rc_car.blend --python blender/scripts/render_inserts.py -- OUT_DIR
#
# Writes OUT_DIR/<view>.png (white lines on see-through background is NOT used: black lines, white faces).
import bpy, os, sys, math, json
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

OUT = sys.argv[sys.argv.index("--") + 1]
os.makedirs(OUT, exist_ok=True)
LIFT = 12.5
PZ0, PZ, DT = 14.0 + LIFT, 18.0 + LIFT, 29.0 + LIFT
AZ = 9.0 + LIFT

# insert holes: (center of the hole opening, direction pointing OUT of the part)
PLATE_TOP = [((-84, -16, PZ), (0, 0, 1)), ((-84, 16, PZ), (0, 0, 1))]                       # battery tray
PLATE_BOT = [((78, -6, PZ0), (0, 0, -1)), ((78, 6, PZ0), (0, 0, -1)),                       # bumper
             ((-85, 0, PZ0), (0, 0, -1)), ((-78, 0, PZ0), (0, 0, -1))]                      # tow hook
BOX_BOT = [((x, y, PZ), (0, 0, -1)) for x, y in [(39, -10), (39, 10), (78, -13), (78, 13)]]
BOX_TOP = [((81, -17.5, DT), (0, 0, 1)), ((81, 17.5, DT), (0, 0, 1))]
BEAM = [((56, -36, AZ), (0, -1, 0)), ((56, 36, AZ), (0, 1, 0))]

VIEWS = {   # name: (parts, holes, camera direction, picture size). All straight-on views.
    "plate-top":    (["Chassis plate"], PLATE_TOP, (0, 0, 1), (2200, 1000)),
    "plate-bottom": (["Chassis plate"], PLATE_BOT, (0, 0, -1), (2200, 1000)),
    "box-bottom":   (["Servo box"], BOX_BOT, (0, 0, -1), (1400, 1400)),
    "box-top":      (["Servo box"], BOX_TOP, (0, 0, 1), (1400, 1400)),
    "beam-front":   (["Steering beam"], BEAM, (1, 0, 0), (2000, 800)),
    "beam-end":     (["Steering beam"], BEAM, (0, -1, 0), (900, 900)),
}

sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE"
sc.view_settings.view_transform = "Standard"
sc.render.film_transparent = True
sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGBA"
sc.render.use_freestyle = True
sc.render.line_thickness_mode = "ABSOLUTE"; sc.render.line_thickness = 3.0
ls = sc.view_layers[0].freestyle_settings.linesets[0] if sc.view_layers[0].freestyle_settings.linesets else sc.view_layers[0].freestyle_settings.linesets.new("lines")
ls.select_by_visibility = True; ls.visibility = "VISIBLE"
ls.select_silhouette = ls.select_border = ls.select_crease = True
ls.select_contour = True
sc.view_layers[0].freestyle_settings.crease_angle = math.radians(140)
if ls.linestyle is None:
    ls.linestyle = bpy.data.linestyles.new("ink")
ls.linestyle.color = (0, 0, 0); ls.linestyle.thickness = 3.0

def flat(name, rgb):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    e = nt.nodes.new("ShaderNodeEmission"); e.inputs["Color"].default_value = (*rgb, 1); e.inputs["Strength"].default_value = 1
    o = nt.nodes.new("ShaderNodeOutputMaterial"); nt.links.new(e.outputs[0], o.inputs[0])
    return m

WHITE, BLACK = flat("white", (1, 1, 1)), flat("black", (0, 0, 0))

def marker(c, d):
    """thin black disc just outside the hole opening, so the hole reads as filled black"""
    c, d = Vector(c), Vector(d).normalized()
    bpy.ops.mesh.primitive_cylinder_add(vertices=40, radius=2.0, depth=0.15, location=c + d * 0.12)
    o = bpy.context.object
    o.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    o.data.materials.append(BLACK)
    return o

cam_d = bpy.data.cameras.new("ins"); cam_d.type = "ORTHO"; cam_d.clip_end = 10000
cam = bpy.data.objects.new("ins cam", cam_d); sc.collection.objects.link(cam); sc.camera = cam

for name, (parts, holes, view, (RX, RY)) in VIEWS.items():
    for o in bpy.data.objects:
        if o.type in ("MESH", "CURVE"):
            o.hide_render = o.name not in parts
    for n in parts:
        o = bpy.data.objects[n]; o.data.materials.clear(); o.data.materials.append(WHITE)
    marks = [marker(c, d) for c, d in holes]
    sc.render.resolution_x, sc.render.resolution_y = RX, RY
    pts = []
    for n in parts:
        o = bpy.data.objects[n]
        pts += [o.matrix_world @ Vector(c) for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    c = (lo + hi) / 2
    v = Vector(view).normalized()
    cam.location = c + v * 1000
    f = (c - cam.location).normalized()                  # look direction
    up = Vector((0, 0, 1)) if abs(v.z) < 0.8 else Vector((0, 1 if v.z > 0 else -1, 0)) * 1   # keep the car's front to the right
    r = f.cross(up).normalized(); u = r.cross(f)
    from mathutils import Matrix
    cam.matrix_world = Matrix((r, u, -f)).transposed().to_4x4() @ Matrix.Identity(4)
    cam.location = c + v * 1000
    bpy.context.view_layer.update()
    inv = cam.matrix_world.inverted()
    cp = [inv @ p for p in pts]
    w = max(p.x for p in cp) - min(p.x for p in cp); h = max(p.y for p in cp) - min(p.y for p in cp)
    mid = Vector(((max(p.x for p in cp) + min(p.x for p in cp)) / 2, (max(p.y for p in cp) + min(p.y for p in cp)) / 2, 0))
    cam.location = cam.location + cam.matrix_world.to_3x3() @ mid
    cam_d.ortho_scale = max(w, h * RX / RY) * 1.08
    sc.render.filepath = os.path.join(OUT, name + ".png")
    bpy.context.view_layer.update()
    uv = [list(world_to_camera_view(sc, cam, Vector(c))[:2]) for c, d in holes]      # 0..1 from bottom left, for rings on the PDF
    json.dump(uv, open(os.path.join(OUT, name + ".json"), "w"))
    bpy.ops.render.render(write_still=True)
    print("wrote", sc.render.filepath)
    for m in marks:
        bpy.data.objects.remove(m)
