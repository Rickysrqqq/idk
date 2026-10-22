"""BMW M3 (G80) - procedural Blender build + studio render.

Run:  python build_m3_g80.py [preview|final] [shot ...]
Car faces +X, Y is width, Z is up. Units are metres (real G80: 4.79 x 1.90 x 1.43, wheelbase 2.86).
"""
import math
import os
import sys

import bpy
import bmesh
import numpy as np
from mathutils import Euler, Matrix, Vector
from scipy.interpolate import PchipInterpolator

HERE = os.path.dirname(os.path.abspath(__file__))
MODE = sys.argv[1] if len(sys.argv) > 1 else "preview"
SHOTS = sys.argv[2:] or ["front34"]

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
col = scene.collection


# ----------------------------------------------------------------------------- helpers
def table(rows):
    rows = sorted(rows)
    return PchipInterpolator([r[0] for r in rows], [r[1] for r in rows], extrapolate=False)


def link(obj):
    col.objects.link(obj)
    return obj


def smooth(me, angle=40.0):
    """Smooth-shade, keeping hard edges where adjacent faces differ by more than `angle` degrees."""
    bm = bmesh.new()
    bm.from_mesh(me)
    lim = math.radians(angle)
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:
        if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > lim:
            e.smooth = False
    bm.to_mesh(me)
    bm.free()


def obj_from_bm(name, bm, mats=()):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    smooth(me)
    return link(bpy.data.objects.new(name, me))


def bake(obj):
    """Replace obj's mesh with its evaluated (modifiers applied) mesh."""
    dg = bpy.context.evaluated_depsgraph_get()
    new = bpy.data.meshes.new_from_object(obj.evaluated_get(dg))
    old = obj.data
    obj.modifiers.clear()
    obj.data = new
    bpy.data.meshes.remove(old)
    smooth(new)
    return obj


def add_mod(obj, kind, **kw):
    m = obj.modifiers.new(kind.title(), kind)
    for k, v in kw.items():
        setattr(m, k, v)
    return m


def loft(name, stations, ring_fn, mats, mat_fn=None):
    """Closed loft: ring_fn(x) -> list of (y, z) loop; caps are n-gons."""
    bm = bmesh.new()
    rings = []
    for x in stations:
        rings.append([bm.verts.new((x, y, z)) for (y, z) in ring_fn(x)])
    n = len(rings[0])
    for a, b in zip(rings[:-1], rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((a[i], a[j], b[j], b[i]))
    bm.faces.new(rings[0])
    bm.faces.new(rings[-1][::-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if mat_fn:
        for f in bm.faces:
            f.material_index = mat_fn(f.calc_center_median(), f.normal)
    return obj_from_bm(name, bm, mats)


def revolve(name, profile, mat, steps=96, closed=True, r_axis="Y"):
    """Revolve (r, y) profile about the Y axis."""
    bm = bmesh.new()
    rings = []
    for i in range(steps):
        t = 2 * math.pi * i / steps
        c, s = math.cos(t), math.sin(t)
        rings.append([bm.verts.new((r * c, y, r * s)) for (r, y) in profile])
    m = len(profile)
    last = m if closed else m - 1
    for i in range(steps):
        a, b = rings[i], rings[(i + 1) % steps]
        for j in range(last):
            k = (j + 1) % m
            bm.faces.new((a[j], a[k], b[k], b[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return obj_from_bm(name, bm, [mat])


def boxes(name, specs, mat, bevel=0.0, seg=2):
    """specs: list of (center, size, rot_euler_xyz)."""
    bm = bmesh.new()
    for c, s, r in specs:
        M = Matrix.Translation(c) @ Euler(r).to_matrix().to_4x4() @ Matrix.Diagonal((*s, 1.0))
        bmesh.ops.create_cube(bm, size=1.0, matrix=M)
    if bevel:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=seg, affect="EDGES")
    return obj_from_bm(name, bm, [mat])


# ----------------------------------------------------------------------------- materials
def mat(name, base=(0.5, 0.5, 0.5, 1), metal=0.0, rough=0.5, **kw):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = base
    b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rough
    for k, v in kw.items():
        b.inputs[k.replace("_", " ")].default_value = v
    return m


def paint_material():
    m = mat("Paint_PortimaoBlue", (0.004, 0.03, 0.30, 1), metal=0.0, rough=0.28)
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Metallic"].default_value = 0.55
    b.inputs["Coat Weight"].default_value = 1.0
    b.inputs["Coat Roughness"].default_value = 0.015
    b.inputs["Coat IOR"].default_value = 1.5
    # metallic flake: fine voronoi drives a subtle normal perturbation under the clearcoat
    tc = nt.nodes.new("ShaderNodeTexCoord")
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 900
    vor.feature = "F1"
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.08
    bump.inputs["Distance"].default_value = 0.002
    nt.links.new(tc.outputs["Object"], vor.inputs["Vector"])
    nt.links.new(vor.outputs["Distance"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    # flakes also modulate roughness slightly
    ramp = nt.nodes.new("ShaderNodeMapRange")
    ramp.inputs["From Min"].default_value = 0.0
    ramp.inputs["From Max"].default_value = 0.6
    ramp.inputs["To Min"].default_value = 0.22
    ramp.inputs["To Max"].default_value = 0.38
    nt.links.new(vor.outputs["Distance"], ramp.inputs["Value"])
    nt.links.new(ramp.outputs["Result"], b.inputs["Roughness"])
    return m


def carbon_material():
    m = mat("CarbonFibre", (0.02, 0.02, 0.022, 1), metal=0.0, rough=0.25)
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Coat Weight"].default_value = 1.0
    b.inputs["Coat Roughness"].default_value = 0.02
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (260, 260, 260)
    mp.inputs["Rotation"].default_value = (0, 0, math.radians(45))
    chk = nt.nodes.new("ShaderNodeTexChecker")
    chk.inputs["Scale"].default_value = 1.0
    chk.inputs["Color1"].default_value = (0.012, 0.012, 0.014, 1)
    chk.inputs["Color2"].default_value = (0.05, 0.05, 0.055, 1)
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.inputs["Scale"].default_value = 1.0
    wave.inputs["Distortion"].default_value = 0.0
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.25
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], chk.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], wave.inputs["Vector"])
    nt.links.new(chk.outputs["Color"], b.inputs["Base Color"])
    nt.links.new(wave.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def slat_material():
    """Kidney grille: dark with vertical bars (bump + colour)."""
    m = mat("GrilleSlats", (0.01, 0.01, 0.011, 1), metal=0.3, rough=0.35)
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = "Y"
    wave.wave_profile = "SAW"
    wave.inputs["Scale"].default_value = 85
    wave.inputs["Distortion"].default_value = 0
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 1.0
    bump.inputs["Distance"].default_value = 0.01
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.002, 0.002, 0.003, 1)
    ramp.color_ramp.elements[1].color = (0.03, 0.03, 0.034, 1)
    nt.links.new(tc.outputs["Object"], wave.inputs["Vector"])
    nt.links.new(wave.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def mesh_material():
    """Lower intake: black honeycomb-ish mesh via bump."""
    m = mat("IntakeMesh", (0.006, 0.006, 0.007, 1), metal=0.4, rough=0.45)
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    br = nt.nodes.new("ShaderNodeTexBrick")
    br.inputs["Scale"].default_value = 120
    br.inputs["Mortar Size"].default_value = 0.25
    br.inputs["Brick Width"].default_value = 0.5
    br.inputs["Row Height"].default_value = 0.5
    bump = nt.nodes.new("ShaderNodeBump")
    bump.invert = True
    bump.inputs["Strength"].default_value = 1.0
    bump.inputs["Distance"].default_value = 0.01
    nt.links.new(tc.outputs["Object"], br.inputs["Vector"])
    nt.links.new(br.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


M = {
    "paint": paint_material(),
    "carbon": carbon_material(),
    "glass": mat("Glass", (0.004, 0.005, 0.007, 1), metal=0.0, rough=0.01, Coat_Weight=0.0),
    "trim": mat("TrimBlack", (0.008, 0.008, 0.009, 1), metal=0.0, rough=0.18, Coat_Weight=0.6),
    "plastic": mat("PlasticMatte", (0.015, 0.015, 0.016, 1), rough=0.55),
    "arch": mat("WheelWell", (0.004, 0.004, 0.004, 1), rough=0.9),
    "tyre": mat("Rubber", (0.012, 0.012, 0.012, 1), rough=0.62),
    "rim": mat("Rim_OrbitGrey", (0.17, 0.17, 0.18, 1), metal=1.0, rough=0.22),
    "disc": mat("BrakeDisc", (0.45, 0.45, 0.47, 1), metal=1.0, rough=0.38),
    "caliper": mat("Caliper_Red", (0.55, 0.01, 0.01, 1), rough=0.3, Coat_Weight=1.0),
    "chrome": mat("Chrome", (0.9, 0.9, 0.92, 1), metal=1.0, rough=0.04),
    "exhaust": mat("BlackChrome", (0.03, 0.03, 0.035, 1), metal=1.0, rough=0.12),
    "slats": slat_material(),
    "intake": mesh_material(),
    "white": mat("RoundelWhite", (0.8, 0.8, 0.8, 1), rough=0.2),
    "blue": mat("RoundelBlue", (0.02, 0.15, 0.7, 1), rough=0.2),
    "shut": mat("ShutLine", (0.0, 0.0, 0.0, 1), rough=0.9),
}
# tail lights: red glass with LED glow
tl = mat("TailLight", (0.35, 0.0, 0.005, 1), rough=0.05, Coat_Weight=1.0)
tl.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = (1.0, 0.02, 0.01, 1)
tl.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 1.2
M["tail"] = tl
tl_in = mat("TailLightLED", (0.05, 0, 0, 1), rough=0.2)
tl_in.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = (1.0, 0.03, 0.02, 1)
tl_in.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 12.0
M["tail_led"] = tl_in
hl = mat("HeadLight", (0.02, 0.02, 0.025, 1), rough=0.03, Coat_Weight=1.0)
M["head"] = hl
drl = mat("DRL", (0.9, 0.7, 0.2, 1), rough=0.1)
drl.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = (1.0, 0.78, 0.25, 1)
drl.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 18.0
M["drl"] = drl

# ----------------------------------------------------------------------------- body
HW = table([(-2.40, .66), (-2.36, .74), (-2.25, .84), (-2.0, .915), (-1.7, .955), (-1.5, .96), (-1.0, .955),
            (0, .95), (1.0, .945), (1.5, .95), (1.95, .945), (2.2, .90), (2.32, .83), (2.40, .70)])
ZB = table([(-2.40, .40), (-2.36, .34), (-2.20, .26), (-2.0, .19), (-1.7, .15), (0, .145),
            (1.7, .14), (2.1, .13), (2.30, .16), (2.40, .30)])
ZT = table([(-2.40, .93), (-2.36, .975), (-2.0, 1.02), (-1.6, 1.005), (-1.0, .985), (0.0, .965),
            (0.6, .975), (1.0, 1.0), (1.4, .99), (1.9, .945), (2.2, .87), (2.36, .80), (2.40, .76)])
BULGE = table([(-2.4, 0), (1.9, 0), (1.6, .018), (1.2, .028), (0.8, .01), (0.6, 0), (2.4, 0)])
BULGE = lambda x, _t=table([(-2.4, 0), (-0.5, 0), (0.7, 0), (1.0, .012), (1.3, .026), (1.7, .024), (2.0, .008), (2.4, 0)]): float(_t(x))

SIDE = [(0.00, 0.00), (0.66, 0.00), (0.92, 0.04), (0.99, 0.16), (1.00, 0.40), (1.005, 0.58),
        (0.965, 0.70), (0.945, 0.86), (0.925, 0.95), (0.84, 0.995)]


def body_ring(x):
    hw, zb, zt = float(HW(x)), float(ZB(x)), float(ZT(x))
    h = zt - zb
    pts = [(f * hw, zb + g * h) for f, g in SIDE]
    bu = BULGE(x)
    pts.append((hw * 0.45, zt + bu * 0.7))
    pts.append((0.0, zt + bu))
    left = [(-y, z) for (y, z) in pts[1:-1]][::-1]
    return pts + left


st = np.concatenate([np.linspace(-2.40, -2.0, 9), np.linspace(-2.0, 2.0, 41)[1:], np.linspace(2.0, 2.40, 9)[1:]])
body = loft("Body", st, body_ring, [M["paint"], M["arch"]])
add_mod(body, "SUBSURF", levels=3, render_levels=3)

# wheel geometry
WB_F, WB_R = 1.50, -1.36
R_F, R_R = 0.335, 0.352
Y_F, Y_R = 0.805, 0.815
ARCH_GAP = 0.038
ARCHES = [(WB_F, R_F), (WB_R, R_R)]

bm = bmesh.new()
for cx, r in ARCHES:
    for sgn in (1, -1):
        c = Vector((cx, sgn * 0.67, r))
        M_ = Matrix.Translation(c) @ Matrix.Rotation(math.radians(90), 4, "X")
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=72, radius1=r + ARCH_GAP,
                              radius2=r + ARCH_GAP, depth=0.76, matrix=M_)
cutter = obj_from_bm("ArchCutter", bm)
add_mod(body, "BOOLEAN", operation="DIFFERENCE", object=cutter, solver="EXACT")
bake(body)
bpy.data.objects.remove(cutter)
# arch faces -> wheel-well black
for p in body.data.polygons:
    c = p.center
    for cx, r in ARCHES:
        d = math.hypot(c.x - cx, c.z - r)
        if d <= r + ARCH_GAP + 0.004 and abs(c.y) >= 0.28 and c.z < r + ARCH_GAP + 0.02 \
                and (abs(p.normal.y) < 0.6 or abs(c.y) < 0.4):
            p.material_index = 1
body_obj = body

# ----------------------------------------------------------------------------- greenhouse
ZR = table([(0.95, 1.01), (0.75, 1.15), (0.45, 1.34), (0.15, 1.42), (-0.3, 1.43), (-0.8, 1.41),
            (-1.2, 1.335), (-1.55, 1.18), (-1.80, 1.045)])
GR = table([(0.95, .74), (0.6, .69), (0.2, .65), (-0.3, .635), (-1.0, .625), (-1.5, .62), (-1.80, .62)])
GB = table([(0.95, .76), (0.5, .765), (0, .765), (-1.0, .765), (-1.8, .74)])


def gh_ring(x):
    zroof = float(ZR(x))
    zbase = float(ZT(x)) - 0.045
    H = zroof - zbase
    gb, gr = float(GB(x)), float(GR(x))
    half = [(gb, zbase), (gb - 0.012, zbase + 0.25 * H), (gr + 0.06, zbase + 0.62 * H),
            (gr, zroof - 0.045 * min(1, H / 0.2)), (gr * 0.62, zroof - 0.008), (0.0, zroof)]
    left = [(-y, z) for (y, z) in half[1:-1]][::-1]
    return [(0.0, zbase)] + half + left


def gh_mat(c, n):
    ax = abs(c.y)
    if n.z > 0.5:  # roof, windscreen, rear glass
        if -1.28 < c.x < 0.12 and ax < 0.56:
            return 1  # carbon roof
        return 0
    if 0.52 > c.x > -0.30 or -0.43 > c.x > -1.02:
        return 0  # side glass
    if c.x > 0.52:
        return 2  # A-pillar
    if -0.43 <= c.x <= -0.30:
        return 2  # B-pillar
    return 3  # C-pillar / rear quarter -> paint


gst = np.concatenate([np.linspace(-1.80, -1.5, 6), np.linspace(-1.5, 0.6, 22)[1:], np.linspace(0.6, 0.95, 8)[1:]])
gh = loft("Greenhouse", gst, gh_ring, [M["glass"], M["carbon"], M["trim"], M["paint"]], gh_mat)
add_mod(gh, "SUBSURF", levels=2, render_levels=2)
bake(gh)

# ----------------------------------------------------------------------------- conforming detail patches
def patch(name, pts, material, axis="X", start=3.5, dirn=-1, offset=0.003, thick=0.0, sub=4, target=None):
    target = target or body_obj
    bm = bmesh.new()

    def P(u, v):
        return {"X": (start, u, v), "Y": (u, start, v), "Z": (u, v, start)}[axis]

    vs = [bm.verts.new(P(*p)) for p in pts]
    f = bm.faces.new(vs)
    bmesh.ops.triangulate(bm, faces=[f])
    for _ in range(sub):
        bmesh.ops.subdivide_edges(bm, edges=list(bm.edges), cuts=1, use_grid_fill=True)
    ob = obj_from_bm(name, bm, [material])
    sw = add_mod(ob, "SHRINKWRAP", target=target, wrap_method="PROJECT", offset=offset, cull_face="OFF",
                 use_negative_direction=(dirn < 0), use_positive_direction=(dirn > 0))
    setattr(sw, "use_project_" + axis.lower(), True)
    bake(ob)
    idx = {"X": 0, "Y": 1, "Z": 2}[axis]
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bad = [v for v in bm.verts if abs(v.co[idx] - start) < 1e-3]
    bmesh.ops.delete(bm, geom=bad, context="VERTS")
    bm.to_mesh(ob.data)
    bm.free()
    if thick:
        add_mod(ob, "SOLIDIFY", thickness=thick, offset=1.0, use_even_offset=True)
        bake(ob)
    smooth(ob.data)
    return ob


def rr(cx, cy, w, h, r, n=5, taper=0.0):
    """Rounded rect polygon as (u,v) points. taper narrows the bottom."""
    pts = []
    for (sx, sy, a0) in ((1, 1, 0), (-1, 1, 90), (-1, -1, 180), (1, -1, 270)):
        ccx = cx + sx * (w / 2 - r) - (sx * taper * (0 if sy > 0 else 1))
        ccy = cy + sy * (h / 2 - r)
        for i in range(n + 1):
            t = math.radians(a0 + 90 * i / n)
            pts.append((ccx + r * math.cos(t), ccy + r * math.sin(t)))
    return pts


# kidney grilles (front, project -X)
for sgn in (1, -1):
    yc = sgn * 0.118
    frame = patch(f"KidneyFrame{sgn}", rr(yc, 0.615, 0.222, 0.330, 0.03, taper=0.012), M["trim"], offset=0.012)
    grille = patch(f"Kidney{sgn}", rr(yc, 0.615, 0.196, 0.304, 0.024, taper=0.010), M["slats"], offset=0.006)
# lower centre intake + corner intakes
patch("IntakeCentre", [(-0.46, 0.35), (-0.40, 0.45), (0.40, 0.45), (0.46, 0.35), (0.38, 0.30), (-0.38, 0.30)],
      M["intake"], offset=0.006)
for sgn in (1, -1):
    pts = [(sgn * 0.54, 0.31), (sgn * 0.58, 0.47), (sgn * 0.80, 0.50), (sgn * 0.86, 0.41), (sgn * 0.78, 0.31)]
    patch(f"IntakeCorner{sgn}", pts, M["intake"], offset=0.006)
    # headlight: slim angular housing + yellow DRL accent
    hp = [(sgn * 0.50, 0.700), (sgn * 0.54, 0.735), (sgn * 0.80, 0.755), (sgn * 0.89, 0.715),
          (sgn * 0.84, 0.668), (sgn * 0.62, 0.652)]
    patch(f"Headlight{sgn}", hp, M["head"], offset=0.004, thick=0.012, sub=4)
    dp = [(sgn * 0.57, 0.706), (sgn * 0.82, 0.730), (sgn * 0.855, 0.716), (sgn * 0.60, 0.692)]
    patch(f"DRL{sgn}", dp, M["drl"], offset=0.020, sub=4)
    # taillight: wraparound L-shape in red glass with LED bars
    tp = [(sgn * 0.52, 0.845), (sgn * 0.56, 0.905), (sgn * 0.86, 0.915), (sgn * 0.90, 0.87),
          (sgn * 0.88, 0.835), (sgn * 0.72, 0.822), (sgn * 0.70, 0.800), (sgn * 0.56, 0.800)]
    patch(f"Taillight{sgn}", tp, M["tail"], start=-3.5, dirn=+1, offset=0.004, thick=0.010, sub=4)
    lp = [(sgn * 0.58, 0.864), (sgn * 0.84, 0.886), (sgn * 0.86, 0.872), (sgn * 0.60, 0.850)]
    patch(f"TaillightLED{sgn}", lp, M["tail_led"], start=-3.5, dirn=+1, offset=0.020, sub=4)

# BMW roundel on the bonnet + front fender gills
for i, (a0, m) in enumerate(((0, "blue"), (90, "white"), (180, "blue"), (270, "white"))):
    pts = [(2.075, 0.0)] + [(2.075 + 0.026 * math.cos(math.radians(a0 + k * 15)),
                              0.026 * math.sin(math.radians(a0 + k * 15))) for k in range(7)]
    patch(f"Roundel{i}", pts, M[m], axis="Z", start=3.0, dirn=-1, offset=0.006, sub=2)
for sgn in (1, -1):
    gill = [(1.50, 0.612), (1.52, 0.680), (1.72, 0.690), (1.74, 0.625)]
    patch(f"Gill{sgn}", gill, M["trim"], axis="Y", start=sgn * 3.0, dirn=-sgn, offset=0.004, thick=0.0, sub=3)
    # shut lines (door cuts) on both sides
    for nm, x0, z0, z1 in (("DoorF", 0.60, 0.33, 1.00), ("DoorB", -0.37, 0.29, 1.00), ("DoorR", -1.14, 0.30, 0.98)):
        patch(f"{nm}{sgn}", [(x0 - 0.0016, z0), (x0 + 0.0016, z0), (x0 + 0.0016, z1), (x0 - 0.0016, z1)],
              M["shut"], axis="Y", start=sgn * 3.0, dirn=-sgn, offset=0.0015, sub=5)
    # door handles
    patch(f"Handle{sgn}", rr(0.18, 0.855, 0.16, 0.026, 0.012), M["paint"], axis="Y", start=sgn * 3.0,
          dirn=-sgn, offset=0.010, sub=3)
    patch(f"HandleR{sgn}", rr(-0.82, 0.855, 0.16, 0.026, 0.012), M["paint"], axis="Y", start=sgn * 3.0,
          dirn=-sgn, offset=0.010, sub=3)
    # side window surround trim
    patch(f"BeltTrim{sgn}", [(0.52, 0.968), (-1.05, 0.968), (-1.05, 0.982), (0.52, 0.982)], M["trim"],
          axis="Y", start=sgn * 3.0, dirn=-sgn, offset=0.004, sub=6)

# ----------------------------------------------------------------------------- aero + rear
boxes("Splitter", [((2.29, 0, 0.138), (0.26, 1.52, 0.024), (0, 0, 0))], M["carbon"], bevel=0.008)
boxes("Diffuser", [((-2.27, 0, 0.255), (0.36, 1.30, 0.20), (0, 0, 0))], M["trim"], bevel=0.016)
boxes("DiffuserFins", [((-2.40, y, 0.19), (0.18, 0.012, 0.10), (0, 0, 0)) for y in (-0.62, -0.20, 0.0, 0.20, 0.62)],
      M["plastic"], bevel=0.002)
boxes("TrunkLip", [((-2.31, 0, 1.040), (0.07, 1.05, 0.020), (0, math.radians(-8), 0))], M["carbon"], bevel=0.006)
boxes("Skirts", [((-0.07, s * 0.915, 0.20), (2.2, 0.05, 0.075), (0, 0, 0)) for s in (1, -1)], M["trim"], bevel=0.02)
# plate recess
patch("PlateRecess", rr(0.0, 0.62, 0.40, 0.11, 0.012), M["white"], start=-3.5, dirn=+1, offset=0.004, sub=3)

# quad exhaust: hollow tubes
for y in (-0.57, -0.40, 0.40, 0.57):
    tube = revolve("ExhaustTip", [(0.040, -0.07), (0.047, -0.07), (0.047, 0.07), (0.040, 0.07)], M["exhaust"], steps=40)
    tube.rotation_euler = (0, 0, math.radians(90))
    tube.location = (-2.405, y, 0.335)
    inner = revolve("ExhaustIn", [(0.0, 0.0), (0.040, 0.0)], M["arch"], steps=40, closed=False)
    inner.rotation_euler = (0, 0, math.radians(90))
    inner.location = (-2.36, y, 0.335)

# mirrors
for sgn in (1, -1):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=40, v_segments=24, radius=0.5,
                              matrix=Matrix.Diagonal((0.17, 0.115, 0.095, 1.0)))
    mir = obj_from_bm(f"Mirror{sgn}", bm, [M["paint"]])
    mir.location = (0.44, sgn * 1.00, 1.075)
    mir.rotation_euler = (0, 0, math.radians(-8 * sgn))
    boxes(f"MirrorBase{sgn}", [((0.48, sgn * 0.90, 1.015), (0.08, 0.17, 0.035), (0, 0, math.radians(-12 * sgn)))],
          M["trim"], bevel=0.008)

# ----------------------------------------------------------------------------- wheels
def build_wheel(R, tw, rr_, label):
    parts = []
    # tyre: closed profile (r, y)
    t = tw / 2
    half = [(rr_ - 0.004, 0.80 * t), (rr_ + 0.022, 0.97 * t), (R - 0.050, 1.00 * t),
            (R - 0.014, 0.90 * t), (R - 0.003, 0.60 * t), (R, 0.30 * t)]
    prof = [(r, -y) for r, y in half] + [(r, y) for r, y in reversed(half)]
    # open at centreline
    prof = [(r, -y) for r, y in half] + [(r, y) for r, y in reversed(half)]
    tyre = revolve(f"Tyre_{label}", prof, M["tyre"], steps=120)
    parts.append(tyre)
    # barrel / lip
    barrel = revolve(f"Barrel_{label}", [(rr_ + 0.010, -0.115), (rr_ + 0.010, 0.128), (rr_ - 0.012, 0.133),
                                        (rr_ - 0.030, 0.108), (rr_ - 0.030, -0.115)], M["rim"], steps=96)
    parts.append(barrel)
    # hub + centre cap
    hub = revolve(f"Hub_{label}", [(0.0, 0.070), (0.062, 0.066), (0.072, 0.052), (0.080, 0.040), (0.082, 0.0),
                                   (0.0, 0.0)], M["rim"], steps=48)
    parts.append(hub)
    cap = revolve(f"Cap_{label}", [(0.0, 0.082), (0.030, 0.080), (0.034, 0.072), (0.0, 0.072)], M["blue"], steps=32)
    parts.append(cap)
    # M double-spoke: 5 pairs
    specs = []
    for k in range(5):
        base = 2 * math.pi * k / 5
        for off in (-0.115, 0.115):
            a = base + off
            rc = (0.07 + rr_ - 0.018) / 2
            L = rr_ - 0.018 - 0.055
            c = Vector((rc * math.cos(a), 0.088, rc * math.sin(a)))
            specs.append((c, (L, 0.022, 0.028), (0, -a, 0)))
    sp = boxes(f"Spokes_{label}", specs, M["rim"], bevel=0.004)
    parts.append(sp)
    # brake disc + caliper
    disc = revolve(f"Disc_{label}", [(0.095, -0.015), (0.185, -0.015), (0.185, 0.015), (0.095, 0.015)], M["disc"], steps=72)
    parts.append(disc)
    hat = revolve(f"DiscHat_{label}", [(0.0, 0.028), (0.108, 0.028), (0.108, -0.005), (0.0, -0.005)], M["disc"], steps=48)
    parts.append(hat)
    ang = math.radians(-20)
    cal = boxes(f"Caliper_{label}", [(Vector((0.175 * math.cos(ang), 0.012, 0.175 * math.sin(ang))),
                                      (0.060, 0.092, 0.150), (0, -ang, 0))], M["caliper"], bevel=0.012, seg=3)
    parts.append(cal)
    return parts


def place_wheels(parts, label, cx, cy, cz):
    empty = bpy.data.objects.new(f"Wheel_{label}", None)
    link(empty)
    empty.location = (cx, cy, cz)
    if cy < 0:
        empty.rotation_euler = (0, 0, math.radians(180))
    for p in parts:
        p.parent = empty
    return empty


front_parts = build_wheel(R_F, 0.255, 0.241, "F")
rear_parts = build_wheel(R_R, 0.285, 0.254, "R")
for lab, parts, cx, cy, cz in (("FL", front_parts, WB_F, Y_F, R_F), ("RL", rear_parts, WB_R, Y_R, R_R)):
    place_wheels(parts, lab, cx, cy, cz)
# mirrored copies (linked data) for the other side
for lab, parts, cx, cy, cz in (("FR", front_parts, WB_F, -Y_F, R_F), ("RR", rear_parts, WB_R, -Y_R, R_R)):
    empty = bpy.data.objects.new(f"Wheel_{lab}", None)
    link(empty)
    empty.location = (cx, cy, cz)
    empty.rotation_euler = (0, 0, math.radians(180))
    for p in parts:
        q = p.copy()
        q.data = p.data
        link(q)
        q.parent = empty
        q.matrix_parent_inverse = Matrix.Identity(4)
        q.location = p.location
        q.rotation_euler = p.rotation_euler

# ----------------------------------------------------------------------------- studio + camera
floor_mat = mat("Floor", (0.018, 0.018, 0.02, 1), rough=0.3)
bpy.ops.mesh.primitive_plane_add(size=80)
floor = bpy.context.active_object
floor.data.materials.append(floor_mat)

world = bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs["Color"].default_value = (0.018, 0.018, 0.02, 1)
bg.inputs["Strength"].default_value = 1.0


def area(name, loc, target, size, power, shape="RECTANGLE", color=(1, 1, 1)):
    ld = bpy.data.lights.new(name, "AREA")
    ld.shape = shape
    ld.size = size[0]
    if shape == "RECTANGLE":
        ld.size_y = size[1]
    ld.energy = power
    ld.color = color
    ob = link(bpy.data.objects.new(name, ld))
    ob.location = loc
    d = Vector(target) - Vector(loc)
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    return ob


area("Top", (0.0, 0.0, 4.2), (0, 0, 0.6), (6.0, 2.8), 500)
area("StripL", (0.3, -3.6, 1.6), (0, 0, 0.7), (7.0, 0.7), 350)
area("StripR", (0.3, 3.6, 1.6), (0, 0, 0.7), (7.0, 0.7), 350)
area("Key", (5.5, -4.5, 2.8), (0, 0, 0.5), (3.5, 2.2), 500, color=(1.0, 0.97, 0.93))
area("Rim", (-5.5, 4.2, 2.4), (0, 0, 0.7), (3.0, 1.5), 700, color=(0.85, 0.92, 1.0))
area("Front", (7.0, 3.0, 1.2), (0, 0, 0.6), (3.0, 1.2), 250)

cam_data = bpy.data.cameras.new("Cam")
cam_data.lens = 70
cam = link(bpy.data.objects.new("Cam", cam_data))
scene.camera = cam
tgt = link(bpy.data.objects.new("CamTarget", None))
tgt.location = (0.0, 0.0, 0.62)
con = cam.constraints.new("TRACK_TO")
con.target = tgt
con.track_axis = "TRACK_NEGATIVE_Z"
con.up_axis = "UP_Y"

SHOT = {
    "front34": ((8.4, -6.4, 1.15), 70, (0.0, 0.0, 0.62)),
    "rear34": ((-8.0, -6.6, 1.25), 70, (-0.1, 0.0, 0.66)),
    "side": ((0.0, -11.5, 0.78), 85, (0.0, 0.0, 0.70)),
    "front": ((11.0, 0.5, 0.80), 85, (0.0, 0.0, 0.68)),
    "low34": ((6.3, 4.2, 0.55), 55, (0.5, 0.0, 0.55)),
}

# ----------------------------------------------------------------------------- render settings
scene.render.engine = "CYCLES"
cy = scene.cycles
cy.device = "CPU"
cy.use_denoising = True
cy.denoiser = "OPENIMAGEDENOISE"
cy.max_bounces = 12
cy.glossy_bounces = 8
cy.transmission_bounces = 4
cy.sample_clamp_indirect = 8
scene.render.film_transparent = False
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_depth = "8"
scene.render.filter_size = 1.2
try:
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
except Exception:
    pass
scene.view_settings.exposure = 0.0
if MODE == "final":
    scene.render.resolution_x, scene.render.resolution_y = 1920, 1080
    cy.samples = int(os.environ.get('M3_SAMPLES', 160))
else:
    scene.render.resolution_x, scene.render.resolution_y = 960, 540
    cy.samples = 48
scene.render.resolution_percentage = 100

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "BMW_M3_G80.blend"))

for s in SHOTS:
    loc, lens, tg = SHOT[s]
    cam.location = loc
    cam_data.lens = lens
    tgt.location = tg
    scene.render.filepath = os.path.join(HERE, "renders", f"m3_g80_{s}_{MODE}.png")
    bpy.ops.render.render(write_still=True)
    print("rendered", scene.render.filepath)
