# Renders a picture of one printed part (or the whole car) from blender/rc_car.blend.
# The part-alone pictures go on the drawing PDFs (make_drawings.py).
#
#   Blender --background blender/rc_car.blend --python blender/scripts/render_part.py -- --part "Chassis plate"
#       -> docs/renders/01-chassis-plate.png
#   Blender --background blender/rc_car.blend --python blender/scripts/render_part.py -- --part "Tow hook" --with "Chassis plate"
#       -> docs/renders/07-tow-hook-on-car.png
#
# Options after "--":
#   --part NAME          the part to show, in orange
#   --with NAME NAME     other parts to show around it, in light grey
#   --all                show the whole car in its real colors instead
#   --focus NAME NAME    zoom in on these parts only
#   --view X,Y,Z         direction the camera looks from (default 1,-1.25,0.9: front right, from above)
#   --res WxH            picture size in pixels (default 1600x1100)
#   --out FILE           where to save the PNG. Default: docs/renders/NN-name.png, or NN-name-on-car.png with --with
import bpy, os, sys
from mathutils import Vector

RENDERS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "docs", "renders"))
FILES = {"Chassis plate": "01-chassis-plate", "Steering beam": "02-steering-beam", "Battery tray": "03-battery-tray",
         "Front bumper": "04-front-bumper", "Servo box": "05-servo-box", "Antenna": "06-antenna", "Tow hook": "07-tow-hook"}

a = sys.argv[sys.argv.index("--") + 1:]

def names_after(flag):
    """the names that follow a flag, up to the next flag"""
    out = []
    if flag in a:
        for t in a[a.index(flag) + 1:]:
            if t.startswith("--"):
                break
            out.append(t)
    return out

part = a[a.index("--part") + 1] if "--part" in a else None
ALL = "--all" in a
others = names_after("--with")
if "--out" in a:
    out = a[a.index("--out") + 1]
else:
    out = os.path.join(RENDERS, FILES[part] + ("-on-car" if others else "") + ".png")
focus = names_after("--focus")
view = Vector(tuple(float(v) for v in a[a.index("--view") + 1].split(","))) if "--view" in a else Vector((1.0, -1.25, 0.9))
RX, RY = (int(v) for v in a[a.index("--res") + 1].split("x")) if "--res" in a else (1600, 1100)

# hide everything that is not shown, and color what is
sc = bpy.context.scene
keep = {o.name for o in bpy.data.objects if o.type in ("MESH", "CURVE")} if ALL else {part, *others}
for o in bpy.data.objects:
    if o.type in ("MESH", "CURVE"):
        o.hide_render = o.name not in keep
if not ALL:
    for n in keep:
        bpy.data.objects[n].color = (1.0, 0.62, 0.25, 1) if n == part else (0.78, 0.79, 0.8, 1)

# simple flat look with dark outlines, see-through background
sc.render.engine = "BLENDER_WORKBENCH"
sc.view_settings.view_transform = "Standard"
sh = sc.display.shading
sh.light = "STUDIO"; sh.color_type = "MATERIAL" if ALL else "OBJECT"; sh.show_cavity = True; sh.cavity_type = "BOTH"
sh.show_object_outline = True; sh.object_outline_color = (0.1, 0.1, 0.1)
sc.render.film_transparent = True
sc.render.resolution_x, sc.render.resolution_y = RX, RY
sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGBA"

# point a flat (no perspective) camera at the shown parts and zoom so they fill the picture
pts = []
for n in (focus or keep):
    o = bpy.data.objects[n]
    pts += [o.matrix_world @ Vector(c) for c in o.bound_box]
lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
c = (lo + hi) / 2
cam_d = bpy.data.cameras.new("sheet"); cam_d.type = "ORTHO"; cam_d.clip_end = 10000
cam = bpy.data.objects.new("sheet cam", cam_d); sc.collection.objects.link(cam)
cam.location = c + view.normalized() * 1000
cam.rotation_euler = (c - cam.location).to_track_quat("-Z", "Y").to_euler()
bpy.context.view_layer.update()
inv = cam.matrix_world.inverted()
cp = [inv @ p for p in pts]
w = max(p.x for p in cp) - min(p.x for p in cp); h = max(p.y for p in cp) - min(p.y for p in cp)
mid = Vector(((max(p.x for p in cp) + min(p.x for p in cp)) / 2, (max(p.y for p in cp) + min(p.y for p in cp)) / 2, 0))
cam.location = cam.location + cam.matrix_world.to_3x3() @ mid
cam_d.ortho_scale = max(w, h * RX / RY) * 1.06
sc.camera = cam
sc.render.filepath = out
bpy.ops.render.render(write_still=True)
print("wrote", out)
