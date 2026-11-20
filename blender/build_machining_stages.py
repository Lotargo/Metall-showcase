"""Build three states of an original display spindle in Blender 5.2.

From the repository root run blender -b --python blender/build_machining_stages.py.
The axis is X throughout. Coordinates are illustration units. Each profile row
gives the axial station, radius and material of the segment ending at that row.
"""

import math
from pathlib import Path

import bpy
from mathutils import Quaternion, Vector


ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / "public" / "media"
SIDES = 120
STATES = ("blank", "rough", "finished")


def metal(name, rgb, roughness, metallic=.95):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*rgb, 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes["Principled BSDF"]
    shader.inputs["Base Color"].default_value = mat.diffuse_color
    shader.inputs["Metallic"].default_value = metallic
    shader.inputs["Roughness"].default_value = roughness
    return mat


def revolve(name, profile, materials):
    vertices, faces, material_ids, previous = [], [], [], []
    for x, radius, material in profile:
        count = 1 if radius == 0 else SIDES
        ring = []
        for index in range(count):
            a = math.tau * index / count
            ring.append(len(vertices))
            vertices.append((x, radius * math.cos(a), radius * math.sin(a)))
        if previous:
            for j in range(SIDES):
                k = (j + 1) % SIDES
                if len(previous) == 1:
                    face = (previous[0], ring[k], ring[j])
                elif len(ring) == 1:
                    face = (previous[j], previous[k], ring[0])
                else:
                    face = (previous[j], previous[k], ring[k], ring[j])
                faces.append(face)
                material_ids.append(materials.index(material))
        previous = ring
    mesh = bpy.data.meshes.new(name + " | revolved section")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    for mat in materials:
        mesh.materials.append(mat)
    for polygon, material_id in zip(mesh.polygons, material_ids):
        polygon.material_index = material_id
    body = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(body)
    return body


def cut_keyseat(body, wall_material):
    # Mill a blind capsule-shaped pocket into the long land. The mouth follows
    # the curved OD, with a small real chamfer and a radiused transition below.
    surface = .696
    radial = Vector((0, -.60, .80))
    tangent = Vector((0, .80, .60))
    centers = (-.525, .67)
    steps = 24
    vertices, faces = [], []
    rings = [(.148, .495, False), (.160, .498, False), (.171, .511, False),
             (.175, .527, False), (.175, -.027, True), (.205, .003, True),
             (.205, .20, True)]
    for radius, height, relative in rings:
        for center, start in [(centers[1], -math.pi / 2), (centers[0], math.pi / 2)]:
            for j in range(steps + 1):
                a = start + math.pi * j / steps
                x, v = center + radius * math.cos(a), radius * math.sin(a)
                u = math.sqrt(surface ** 2 - v ** 2) + height if relative else height
                vertices.append(Vector((x, 0, 0)) + tangent * v + radial * u)
    count = 2 * (steps + 1)
    faces.append(tuple(reversed(range(count))))
    for j in range(len(rings) - 1):
        for i in range(count):
            k = (i + 1) % count
            faces.append((j * count + i, j * count + k, (j + 1) * count + k, (j + 1) * count + i))
    faces.append(tuple(range((len(rings) - 1) * count, len(rings) * count)))
    mesh = bpy.data.meshes.new("Keyseat tool")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    mesh.materials.append(wall_material)
    cutter = bpy.data.objects.new("Keyseat tool", mesh)
    bpy.context.collection.objects.link(cutter)
    bpy.context.view_layer.objects.active = body
    difference = body.modifiers.new("Keyseat", "BOOLEAN")
    difference.operation = "DIFFERENCE"
    difference.solver = "EXACT"
    difference.material_mode = "TRANSFER"
    difference.object = cutter
    bpy.ops.object.modifier_apply(modifier=difference.name)
    bpy.data.objects.remove(cutter, do_unlink=True)
    bpy.data.meshes.remove(mesh)


def surface_normals(body, wall_material):
    # Split normals per profile segment preserve the sharp break at a shoulder
    # and the cylindrical highlight on the OD right up to the pocket opening.
    mesh = body.data
    normals = [(0, 0, 0)] * len(mesh.loops)
    for polygon in mesh.polygons:
        polygon.use_smooth = True
        normal = polygon.normal.copy()
        pocket = mesh.materials[polygon.material_index] == wall_material
        radial = math.hypot(normal.y, normal.z)
        for index in polygon.loop_indices:
            x, y, z = mesh.vertices[mesh.loops[index].vertex_index].co
            radius = math.hypot(y, z)
            if pocket or radial < .0001 or radius < .0001:
                normals[index] = normal
            else:
                weight = math.copysign(radial / radius, normal.y * y + normal.z * z)
                normals[index] = (normal.x, y * weight, z * weight)
    mesh.normals_split_custom_set(normals)
    mesh.update()


def add_grain(mat, kind, amplitude, grain_scale):
    """Add studio-only microroughness after exporting the portable PBR values."""
    tree = mat.node_tree
    shader = tree.nodes["Principled BSDF"]
    tex = tree.nodes.new("ShaderNodeTexCoord")
    multiply = tree.nodes.new("ShaderNodeVectorMath")
    multiply.operation = "MULTIPLY"
    multiply.inputs[1].default_value = grain_scale
    tree.links.new(tex.outputs["Object"], multiply.inputs[0])
    noise = tree.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 1
    noise.inputs["Detail"].default_value = 2
    tree.links.new(multiply.outputs[0], noise.inputs["Vector"])
    texture = noise.outputs["Fac"]
    if kind == "face":
        # Circular face-tool marks remain concentric with the bore.
        mask = tree.nodes.new("ShaderNodeVectorMath")
        mask.operation = "MULTIPLY"
        mask.inputs[1].default_value = (0, 1, 1)
        tree.links.new(tex.outputs["Object"], mask.inputs[0])
        distance = tree.nodes.new("ShaderNodeVectorMath")
        distance.operation = "LENGTH"
        tree.links.new(mask.outputs[0], distance.inputs[0])
        wave = tree.nodes.new("ShaderNodeTexWave")
        wave.wave_type, wave.bands_direction = "BANDS", "X"
        wave.inputs["Scale"].default_value = 46
        wave.inputs["Distortion"].default_value = .45
        tree.links.new(distance.outputs["Value"], wave.inputs["Vector"])
        texture = wave.outputs["Fac"]
    finish = tree.nodes.new("ShaderNodeMapRange")
    base = shader.inputs["Roughness"].default_value
    finish.inputs["To Min"].default_value = base - amplitude
    finish.inputs["To Max"].default_value = base + amplitude
    tree.links.new(texture, finish.inputs["Value"])
    tree.links.new(finish.outputs["Result"], shader.inputs["Roughness"])
    bump = tree.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = .17
    bump.inputs["Distance"].default_value = .0028 if kind == "scale" else .0011
    tree.links.new(texture, bump.inputs["Height"])
    tree.links.new(bump.outputs["Normal"], shader.inputs["Normal"])
    if kind == "scale":
        slow = tree.nodes.new("ShaderNodeTexNoise")
        slow.inputs["Scale"].default_value = 6
        slow.inputs["Detail"].default_value = 4
        tree.links.new(tex.outputs["Object"], slow.inputs["Vector"])
        ramp = tree.nodes.new("ShaderNodeValToRGB")
        for element, factor in zip(ramp.color_ramp.elements, (.80, 1.22)):
            element.color = tuple(value * factor for value in mat.diffuse_color[:3]) + (1,)
        tree.links.new(slow.outputs["Fac"], ramp.inputs[0])
        tree.links.new(ramp.outputs["Color"], shader.inputs["Base Color"])


def configure_studio(scene):
    studio = bpy.data.collections.new("Studio")
    scene.collection.children.link(studio)
    camera = bpy.data.objects.new("Product view", bpy.data.cameras.new("Orthographic lens"))
    studio.objects.link(camera)
    camera.location = (8, -13, 8)
    camera.rotation_euler = (-camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 8.15
    scene.camera = camera

    def softbox(name, position, watts, width, height, tint):
        lamp = bpy.data.lights.new(name, "AREA")
        lamp.shape, lamp.energy, lamp.size, lamp.size_y = "RECTANGLE", watts, width, height
        lamp.color = tint
        obj = bpy.data.objects.new(name, lamp)
        studio.objects.link(obj)
        obj.location = position
        direction = (-obj.location).normalized()
        # Orient the long side along the projected shaft axis.
        rotation = direction.to_track_quat("-Z", "Y")
        local_axis = rotation.inverted() @ Vector((1, 0, 0))
        rotation = rotation @ Quaternion((0, 0, 1), math.atan2(local_axis.y, local_axis.x))
        obj.rotation_euler = rotation.to_euler()

    softbox("Long overhead silk", (0, -3.1, 5.8), 560, 10, 3.2, (1, .97, .91))
    softbox("Far edge strip", (-.8, 3.1, 3), 620, 10, .9, (.91, .95, 1))
    softbox("Lower reflection", (0, -3.6, -2.4), 270, 9, 1.15, (.94, .97, 1))
    softbox("Front face silk", (7, -1.2, 2.8), 360, 3.5, 4.5, (1, .98, .94))
    softbox("Rear edge fill", (-6, -.2, 1.5), 190, 3, 3.5, (.95, .97, 1))
    world = bpy.data.worlds.new("Studio ambient")
    world.use_nodes = True
    background = world.node_tree.nodes["Background"]
    background.inputs["Color"].default_value = (.34, .35, .36, 1)
    background.inputs["Strength"].default_value = .29
    scene.world = world
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 64
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = 1400, 790
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "WEBP"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.quality = 98
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"


def use_available_gpu(scene):
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for backend in ("OPTIX", "CUDA", "HIP", "METAL", "ONEAPI"):
        try:
            prefs.compute_device_type = backend
            prefs.refresh_devices()
            if any(device.type == backend for device in prefs.devices):
                for device in prefs.devices:
                    device.use = device.type == backend
                scene.cycles.device = "GPU"
                return
        except (TypeError, RuntimeError):
            continue


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scale = metal("Oxide skin", (.125, .136, .145), .59, .84)
    saw = metal("Sawn end", (.40, .40, .39), .44)
    rough = metal("Rough-turned steel", (.39, .40, .405), .43)
    steel = metal("Finish-turned steel", (.60, .615, .63), .26)
    face = metal("Faced steel", (.55, .561, .57), .33)
    edge = metal("Broken edges", (.66, .671, .68), .25)
    recess = metal("Relieved land", (.415, .427, .438), .34)
    mill = metal("Milled keyseat", (.38, .396, .405), .38)
    bore = metal("Bored steel", (.46, .476, .486), .345)
    blank = revolve("blank", [
        (-3.65, 0, saw), (-3.65, .984, saw), (-3.633, 1, scale),
        (3.633, 1, scale), (3.65, .984, saw), (3.65, 0, saw),
    ], [scale, saw])
    roughed = revolve("rough", [
        (-3.49, 0, saw), (-3.49, .713, saw), (-3.475, .73, rough),
        (-1.60, .73, rough), (-1.578, .748, rough), (-1.578, .943, rough),
        (-1.561, .961, rough), (-.77, .961, rough), (-.75, .942, rough),
        (-.75, .781, rough), (-.728, .76, rough), (1.48, .76, rough),
        (1.5, .74, rough), (1.5, .615, rough), (1.522, .594, rough),
        (3.472, .594, rough), (3.49, .577, rough), (3.49, 0, rough),
    ], [rough, saw])
    finished = revolve("finished", [
        (-3.42, 0, face), (-3.42, .475, face), (-3.375, .52, edge), (-2.48, .52, steel),
        (-2.458, .537, edge), (-2.458, .629, face), (-2.422, .665, edge),
        (-1.60, .665, steel), (-1.587, .650, edge), (-1.525, .650, recess),
        (-1.51, .668, edge), (-1.51, .844, face), (-1.458, .896, edge),
        (-.901, .896, steel), (-.85, .845, edge), (-.85, .718, face),
        (-.825, .696, edge), (1.079, .696, steel), (1.115, .66, edge),
        (1.115, .596, face), (1.144, .57, edge), (1.315, .57, steel),
        (1.343, .542, edge), (1.343, .515, face), (1.367, .495, edge),
        (1.455, .495, recess), (1.477, .524, edge), (2.968, .524, steel),
        (2.987, .495, edge), (2.987, .466, face), (3.083, .466, recess),
        (3.083, .495, face), (3.101, .524, edge), (3.357, .524, steel),
        (3.42, .461, edge), (3.42, .364, face), (3.387, .331, edge),
        (3.240, .331, bore), (3.222, .313, edge), (3.222, .292, face),
        (3.206, .278, edge), (2.456, .278, bore), (2.35, 0, bore),
    ], [steel, face, edge, recess, bore])
    cut_keyseat(finished, mill)
    bodies = (blank, roughed, finished)
    for body in bodies:
        surface_normals(body, mill)
    MEDIA.mkdir(exist_ok=True, parents=True)
    bpy.ops.export_scene.gltf(filepath=str(MEDIA / "machining-stages.glb"), export_animations=False,
                              export_cameras=False, export_lights=False, export_yup=True,
                              export_texcoords=False, export_tangents=False)

    add_grain(scale, "scale", .16, (65, 50, 50))
    add_grain(saw, "saw", .17, (1, 160, 3))
    add_grain(rough, "turned", .15, (165, 2, 2))
    add_grain(steel, "turned", .11, (270, 2, 2))
    add_grain(face, "face", .09, (1, 140, 140))
    add_grain(mill, "milled", .10, (4, 108, 108))
    configure_studio(scene)
    scene.frame_end = len(STATES)
    for i, state in enumerate(STATES, 1):
        scene.timeline_markers.new(state.capitalize(), frame=i)
        for body in bodies:
            body.hide_render = body.hide_viewport = body.name != state
            body.keyframe_insert("hide_render", frame=i)
            body.keyframe_insert("hide_viewport", frame=i)
    scene.frame_set(3)
    bpy.ops.object.select_all(action="DESELECT")
    finished.select_set(True)
    bpy.context.view_layer.objects.active = finished
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.spaces.active.region_3d.view_perspective = "CAMERA"
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / "blender" / "machining-stages.blend"), compress=True)
    use_available_gpu(scene)
    for i, state in enumerate(STATES, 1):
        scene.frame_set(i)
        scene.render.filepath = str(MEDIA / f"machining-{state}.webp")
        bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()
