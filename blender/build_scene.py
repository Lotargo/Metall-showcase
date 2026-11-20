"""Build the display model, animated Blender scene and web assets."""
import math
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / "public" / "media"
STEPS = 112

# Display proportions based on Metall-DEMO shaft-v2, in arbitrary units.
SHAFT = [
    (.31,-3.12),(.39,-3.12),(.45,-3.06),(.45,-1.56),(.48,-1.52),(.48,-1.46),
    (.47,-1.44),(.47,-1.35),(.50,-1.32),(.55,-1.27),(.55,-.79),(.57,-.75),
    (.57,-.04),(.61,.01),(.61,.85),(.64,.91),(.64,1.99),(.70,2.03),
    (.70,2.21),(.66,2.25),(.62,2.28),(.62,2.98),(.58,3.02),(.41,3.02),
    (.38,2.99),(.38,2.63),(.33,2.60),(.33,-2.02),(.30,-2.08),(.30,-3.09),
]


def material(name, tone, roughness, grain=False):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (tone, tone, tone, 1)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    shader = nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = mat.diffuse_color
    shader.inputs["Metallic"].default_value = .90
    shader.inputs["Roughness"].default_value = roughness
    if grain:
        coord = nodes.new("ShaderNodeTexCoord")
        axis = nodes.new("ShaderNodeSeparateXYZ")
        noise = nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 190
        noise.inputs["Detail"].default_value = 2
        bump = nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = .20
        bump.inputs["Distance"].default_value = .018
        links.new(coord.outputs["Object"], axis.inputs["Vector"])
        links.new(axis.outputs["Z"], noise.inputs["Vector"])
        links.new(noise.outputs["Fac"], bump.inputs["Height"])
        links.new(bump.outputs["Normal"], shader.inputs["Normal"])
    return mat


def revolve(name, profile, finish, edge, parent=None, lobes=0):
    def vertex(radius, height, step):
        angle = math.tau * step / STEPS
        if lobes and radius > .66:
            radius -= .065 * max(0, math.cos(lobes * angle)) ** 6
        return radius * math.cos(angle), radius * math.sin(angle), height

    rows = len(profile)
    points = [vertex(r, h, i) for r, h in profile for i in range(STEPS)]
    faces = []
    for row in range(rows):
        for i in range(STEPS):
            following = (i + 1) % STEPS
            end = (row + 1) % rows
            faces.append((row * STEPS + i, row * STEPS + following,
                          end * STEPS + following, end * STEPS + i))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(points, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.parent = parent
    mesh.materials.append(finish)
    mesh.materials.append(edge)
    uv = mesh.uv_layers.new(name="Turning")
    for face in mesh.polygons:
        row, col = divmod(face.index, STEPS)
        face.use_smooth = abs(profile[row][1] - profile[(row + 1) % rows][1]) > .006
        face.material_index = 0 if face.use_smooth else 1
        for loop_index, u in zip(face.loop_indices, (col, col + 1, col + 1, col)):
            z = mesh.vertices[mesh.loops[loop_index].vertex_index].co.z
            uv.data[loop_index].uv = (u / STEPS, (z + 3.3) / 6.6)
    return obj


def ring(name, inner, outer, z, width, finish, edge, parent, lobes=0):
    low, high = z - width / 2, z + width / 2
    c = min(.038, width / 5)
    return revolve(name, [(outer-c,low),(outer,low+c),(outer,high-c),(outer-c,high),
                          (inner+c,high),(inner,high-c),(inner,low+c),(inner+c,low)],
                   finish, edge, parent, lobes)


def pivot(name, travel):
    obj = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(obj)
    obj["travel"] = travel
    return obj


def bearing(name, z, inner, travel, extra):
    inner_group = pivot(name + " inner race", travel)
    outer_group = pivot(name + " outer race", travel + extra)
    balls_group = pivot(name + " rolling elements", travel + extra * .50)
    ring("Inner race", inner, inner + .145, z, .41, steel, polished, inner_group)
    ring("Outer race", inner + .38, inner + .52, z, .43, steel, polished, outer_group)
    ring("Cage", inner + .175, inner + .34, z + .015, .085, dark, dark, balls_group)
    for index in range(11):
        angle = index * math.tau / 11
        r = inner + .257
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=14, radius=.142,
                                             location=(r*math.cos(angle), r*math.sin(angle), z))
        ball = bpy.context.object
        ball.name = name + " ball"
        ball.parent = balls_group
        ball.data.materials.append(polished)
        for face in ball.data.polygons:
            face.use_smooth = True


def keyway(shaft):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(.40, 0, -2.41))
    cut = bpy.context.object
    cut.scale = (.26, .19, 1.05)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bevel = cut.modifiers.new("Round cutter", "BEVEL")
    bevel.width = .082
    bevel.segments = 6
    cut.select_set(False)
    bpy.context.view_layer.objects.active = shaft
    shaft.select_set(True)
    slot = shaft.modifiers.new("Keyway", "BOOLEAN")
    slot.object = cut
    bpy.ops.object.modifier_apply(modifier=slot.name)
    bpy.data.objects.remove(cut, do_unlink=True)


def point_at(obj, pos):
    obj.rotation_euler = (Vector(pos) - obj.location).to_track_quat("-Z", "Y").to_euler()


def area(name, position, power, width, length):
    data = bpy.data.lights.new(name, "AREA")
    data.energy, data.shape, data.size, data.size_y = power, "RECTANGLE", width, length
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = position
    point_at(obj, (0, 0, 0))


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
steel = material("Turned steel", .35, .31, grain=True)
polished = material("Polished steel", .54, .22)
dark = material("Satin steel", .16, .37, grain=True)
shaft = revolve("Stepped shaft", SHAFT, steel, polished)
keyway(shaft)
bearing("Front bearing", -1.91, .455, -1.32, -.90)
bearing("Rear bearing", 2.58, .625, .91, 1.19)
ring("Slotted locknut", .45, .70, -2.47, .32, dark, polished, pivot("Locknut", -2.59), 8)
ring("Spacer", .476, .66, -1.37, .17, polished, steel, pivot("Spacer", -.82))
ring("Retaining washer", .625, .83, 2.90, .15, dark, polished, pivot("Washer", 2.66))
parts = [obj for obj in scene.objects if obj.type in {"EMPTY", "MESH"}]
bpy.ops.object.select_all(action="DESELECT")
for obj in parts:
    obj.select_set(True)

bpy.ops.export_scene.gltf(
    filepath=str(MEDIA / "shaft.glb"), use_selection=True, export_animations=False, export_extras=True,
)
for obj in parts:
    if "travel" not in obj:
        continue
    obj.keyframe_insert(data_path="location", frame=1)
    obj.location.z = obj["travel"]
    obj.keyframe_insert(data_path="location", frame=90)
    obj.location.z = 0
    obj.keyframe_insert(data_path="location", frame=180)

scene.frame_end = 180
for frame, name in [(1, "Assembled"), (90, "Exploded"), (180, "Assembled")]:
    scene.timeline_markers.new(name, frame=frame)

cam = bpy.data.objects.new("Product camera", bpy.data.cameras.new("Product camera"))
bpy.context.collection.objects.link(cam)
cam.location = (8, -11, -7)
point_at(cam, (0, 0, 0))
cam.rotation_euler.rotate_axis("Z", math.radians(-61))
cam.data.type = "ORTHO"
cam.data.ortho_scale = 7.6
cam.data.keyframe_insert(data_path="ortho_scale", frame=1)
cam.data.ortho_scale = 12.85
cam.data.keyframe_insert(data_path="ortho_scale", frame=90)
cam.data.ortho_scale = 7.6
cam.data.keyframe_insert(data_path="ortho_scale", frame=180)
scene.camera = cam

area("Overhead softbox", (3, -5, 6), 1180, 3.6, 8)
area("Long side strip", (-4, -2, 1), 820, 2, 9)
area("Back rim strip", (1, 4, 4), 1050, 4.5, 7)
area("Front reflector", (5, 3, -1), 300, 3.5, 8)
area("End detail", (4, -2, -6), 420, 3, 3)
scene.world = bpy.data.worlds.new("Neutral studio")
scene.world.use_nodes = True
background = scene.world.node_tree.nodes["Background"]
background.inputs["Color"].default_value = (.19, .19, .19, 1)
background.inputs["Strength"].default_value = .42

scene.render.engine = "CYCLES"
scene.cycles.samples = 24
scene.cycles.use_denoising = True
scene.render.resolution_x = 1120
scene.render.resolution_y = 790
scene.render.film_transparent = True
scene.render.image_settings.file_format = "WEBP"
scene.render.image_settings.color_mode = "RGBA"
scene.render.image_settings.quality = 92
scene.view_settings.view_transform = "AgX"
scene.frame_set(1)
for screen in bpy.data.screens:
    for window_area in screen.areas:
        if window_area.type == "VIEW_3D":
            window_area.spaces.active.region_3d.view_perspective = "CAMERA"

bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / "blender" / "shaft.blend"), compress=True)
for frame, pose in [(1, "assembled"), (90, "exploded")]:
    scene.frame_set(frame)
    scene.render.filepath = str(MEDIA / f"shaft-{pose}.webp")
    bpy.ops.render.render(write_still=True)
