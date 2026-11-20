"""Build the sectioned spindle assembly, its inspection animation and website assets.

Run with Blender in background mode. All dimensions are display units. The turned
shaft follows the stepped, through-bored form of the public Metall shaft-v2.
"""
import math
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / "public" / "media"
TAU = math.tau
SEGMENTS = 112


def finish(name, color, roughness, grain=None):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.use_backface_culling = True
    mat.diffuse_color = (*color, 1)
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = mat.diffuse_color
    shader.inputs["Metallic"].default_value = .96
    shader.inputs["Roughness"].default_value = roughness
    if grain:
        tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = grain
        normal = mat.node_tree.nodes.new("ShaderNodeNormalMap")
        normal.inputs["Strength"].default_value = .35
        mat.node_tree.links.new(tex.outputs["Color"], normal.inputs["Color"])
        mat.node_tree.links.new(normal.outputs["Normal"], shader.inputs["Normal"])
    return mat


def turning_normal():
    # A packed, seamless normal strip works in both the renderer and glTF.
    width, height = 16, 1024
    phase = np.arange(height) * TAU / height
    slope = (.36 * np.sin(phase * 131) + .25 * np.sin(phase * 197 + .6)
             + .16 * np.cos(phase * 279) + .12 * np.sin(phase * 37))
    pixels = np.ones((height, width, 4), dtype=np.float32)
    pixels[:, :, 0] = .5
    pixels[:, :, 1] = .5 + .5 * slope[:, None] / np.sqrt(1 + slope[:, None] ** 2)
    pixels[:, :, 2] = .5 + .5 / np.sqrt(1 + slope[:, None] ** 2)
    img = bpy.data.images.new("Circumferential turning marks", width, height, alpha=False)
    img.colorspace_settings.name = "Non-Color"
    img.pixels.foreach_set(pixels.ravel())
    img.pack()
    return img


def mesh_object(name, vertices, faces, materials, parent=None):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    for mat in materials:
        mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.parent = parent
    return obj


def lathe(name, profile, materials, parent=None, shape=None, count=SEGMENTS):
    """Closed radial section, traced up the outside and down the bore.

    A third field on a station chooses the finish of the strip that follows.
    Optional radial shaping cuts spanner slots or forms a polygonal socket.
    """
    vertices, faces = [], []
    for row, station in enumerate(profile):
        r, z = station[:2]
        for i in range(count):
            a = TAU * i / count
            radius = shape(row, r, a) if shape else r
            vertices.append((radius * math.cos(a), radius * math.sin(a), z))
    for row in range(len(profile)):
        following = (row + 1) % len(profile)
        for i in range(count):
            j = (i + 1) % count
            faces.append((row * count + i, row * count + j, following * count + j, following * count + i))
    obj = mesh_object(name, vertices, faces, materials, parent)
    mesh = obj.data
    uv = mesh.uv_layers.new(name="Tool feed")
    for face in mesh.polygons:
        row, col = divmod(face.index, count)
        face.use_smooth = True
        face.material_index = profile[row][2] if len(profile[row]) > 2 else 0
        for loop_index, u in zip(face.loop_indices, (col, col + 1, col + 1, col)):
            vertex = vertices[mesh.loops[loop_index].vertex_index]
            uv.data[loop_index].uv = u / count, vertex[2] / 1.6
    mesh.set_sharp_from_angle(angle=math.radians(35))
    return obj


def group(name, distance):
    obj = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(obj)
    obj.empty_display_type = "PLAIN_AXES"
    obj.empty_display_size = .15
    obj["travel"] = distance
    return obj


def ring(name, inner, outer, z0, z1, bevel, materials, parent, shape=None, count=SEGMENTS):
    c = bevel
    return lathe(name, [(outer-c,z0), (outer,z0+c), (outer,z1-c), (outer-c,z1),
                        (inner+c,z1), (inner,z1-c), (inner,z0+c), (inner+c,z0)],
                 materials, parent, shape, count)


def transform_apply(obj, modifier):
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=modifier.name)


def subtract(obj, cutter):
    modifier = obj.modifiers.new("Cutter path", "BOOLEAN")
    modifier.object = cutter
    transform_apply(obj, modifier)
    bpy.data.objects.remove(cutter, do_unlink=True)


def keyseat(shaft):
    # An end mill approaching radially leaves a flat bed and a semicircular stop.
    angle = math.radians(-21)
    outward = Vector((math.cos(angle), math.sin(angle), 0))
    across = Vector((-math.sin(angle), math.cos(angle), 0))
    radius, stop = .095, -2.37
    contour = [(-radius, -3.29), (radius, -3.29)]
    for i in range(25):
        a = math.pi * i / 24
        contour.append((radius * math.cos(a), stop + radius * math.sin(a)))
    vertices = [tuple(outward * depth + across * side + Vector((0, 0, z)))
                for depth in (.337, .61) for side, z in contour]
    n = len(contour)
    faces = [tuple(reversed(range(n))), tuple(range(n, 2*n))]
    faces.extend((i, (i+1) % n, n + (i+1) % n, n+i) for i in range(n))
    subtract(shaft, mesh_object("Keyseat mill", vertices, faces, []))


def spindle():
    stations = [
        (.398,-3.18,1),(.425,-3.151),(.425,-2.302),(.418,-2.288),
        (.418,-2.258),(.473,-2.239),(.473,-1.993),(.465,-1.980),
        (.465,-1.958),(.496,-1.944),(.496,-1.421),(.489,-1.409),
        (.489,-1.384),(.572,-1.384,1),(.592,-1.363),(.592,-.823),
        (.586,-.809),(.586,-.775),(.621,-.758,1),(.643,-.73),
        (.643,-.073),(.636,-.057),(.636,-.029),(.681,-.013,1),
        (.70,.011),(.70,.815),(.694,.833),(.694,.853),
        (.733,.873,1),(.752,.899),(.752,1.91),(.745,1.93),
        (.745,1.951),(.807,1.951,1),(.836,1.98),(.836,2.119),
        (.810,2.147,1),(.647,2.147),(.632,2.16),(.632,2.19),
        (.641,2.211),(.641,2.829),(.633,2.838),(.633,2.858),
        (.641,2.87),(.641,2.979),(.611,3.009,1),
        (.434,3.009,1),(.403,2.976,2),(.403,2.72,2),
        (.366,2.684,2),(.366,-1.385,2),(.287,-1.46,2),
        (.287,-2.884,2),(.302,-2.90,2),(.302,-3.148,2),(.331,-3.18,1),
        (.350,-3.18,1),(.353,-3.177,1),(.357,-3.177,1),(.360,-3.18,1),
    ]
    shaft = lathe("Spindle | bored and stepped", stations, [turned, ground, graphite])
    keyseat(shaft)
    for i in range(4):
        a = TAU * (i + .125) / 4
        x, y = .525 * math.cos(a), .525 * math.sin(a)
        bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=.047, depth=.29, location=(x,y,2.95))
        subtract(shaft, bpy.context.object)
    return shaft


def threaded_land(name, root, major, pitch, turns, start, per_turn, material, parent=None):
    # One continuously swept trapezoidal helical crest with tapered run-outs.
    section = [(root,-pitch*.39),(major,-pitch*.10),(major,pitch*.10),(root,pitch*.39)]
    vertices, faces = [], []
    for i in range(turns * per_turn + 1):
        a = TAU * i / per_turn
        fade = min(1, i / (per_turn*.55), (turns*per_turn-i) / (per_turn*.55))
        for r, dz in section:
            radius = root + (r-root)*fade
            vertices.append((radius*math.cos(a), radius*math.sin(a), start + pitch*i/per_turn + dz))
    for i in range(turns*per_turn):
        for k in range(4):
            nxt = (k+1) % 4
            faces.append((4*i+k,4*(i+1)+k,4*(i+1)+nxt,4*i+nxt))
    obj = mesh_object(name, vertices, faces, [material], parent)
    for face in obj.data.polygons:
        face.use_smooth = True
    obj.data.set_sharp_from_angle(angle=.55)
    return obj


def rounded_elements(name, pitch_radius, count, z, radial, axial, parent, mat, offset=0, slices=24, stacks=12):
    """Batch the rolling elements or upset rivet heads in a single web draw call."""
    vertices, faces = [], []
    for i in range(count):
        a = TAU * (i + offset) / count
        x, y = pitch_radius * math.cos(a), pitch_radius * math.sin(a)
        base = len(vertices)
        vertices.append((x,y,z-axial))
        for j in range(1, stacks):
            latitude = math.pi * j / stacks - math.pi/2
            rr = radial * math.cos(latitude)
            for k in range(slices):
                theta = TAU * k / slices
                vertices.append((x + rr*math.cos(theta), y + rr*math.sin(theta), z + axial*math.sin(latitude)))
        top = len(vertices)
        vertices.append((x,y,z+axial))
        for k in range(slices):
            following = (k+1) % slices
            faces.append((base,base+1+following,base+1+k))
            for j in range(stacks-2):
                n = base+1+j*slices
                faces.append((n+k,n+following,n+slices+following,n+slices+k))
            n = top-slices
            faces.append((n+k,n+following,top))
    obj = mesh_object(name, vertices, faces, [mat], parent)
    for face in obj.data.polygons:
        face.use_smooth = True


def cage(name, pitch_radius, ball_radius, count, z, cage_parent):
    # Two stamped shells arch around every ball and meet at riveted flats.
    width, divisions = .067, count * 24
    for side in (-1, 1):
        vertices, faces = [], []
        for i in range(divisions):
            a = TAU * i / divisions
            arc = abs((a + math.pi/count) % (TAU/count) - math.pi/count)
            for dr, depth in [(-width,.016),(width,.016),(width,0),(-width,0)]:
                chord_sq = dr*dr + 2*pitch_radius*(pitch_radius+dr)*(1-math.cos(arc))
                rise = max(.027, math.sqrt(max(0, (ball_radius+.007)**2 - chord_sq)))
                r = pitch_radius + dr
                vertices.append((r*math.cos(a), r*math.sin(a), z + side*(rise+depth)))
        for i in range(divisions):
            for j in range(4):
                idx = (4*i+j,4*((i+1)%divisions)+j,4*((i+1)%divisions)+(j+1)%4,4*i+(j+1)%4)
                faces.append(tuple(reversed(idx)) if side == 1 else idx)
        obj = mesh_object(name + (" | cage, upper" if side == 1 else " | cage, lower"), vertices, faces, [cage_metal], cage_parent)
        for f in obj.data.polygons:
            f.use_smooth = True
        obj.data.set_sharp_from_angle(angle=.65)
        rounded_elements(name+" | rivets", pitch_radius, count, z+side*.044, .045, .018, cage_parent, graphite,
                         offset=.5, slices=14, stacks=6)


def bearing(name, bore, z, travel, count):
    inner, rolling, outer = [group(name+" | "+label, distance) for label, distance in zip(("inner ring","ball train","outer ring"),travel)]
    pitch, ball, half = bore+.326, .18, .231
    rim, shoulder, t = pitch+.312, .141, .128
    race = [(math.sqrt((ball+.006)**2-(t*j/8)**2),t*j/8) for j in range(-8,9)]
    profile = [(pitch-shoulder-.025,z-half,1),(pitch-shoulder,z-half+.024),
               (pitch-shoulder,z-t-.008)]
    profile += [(pitch-r,z+h,1) for r,h in race]
    profile += [(pitch-shoulder,z+t+.008),(pitch-shoulder,z+half-.023),
                (pitch-shoulder-.025,z+half,1),(bore+.025,z+half,1),
                (bore,z+half-.025),(bore,z-half+.025),(bore+.025,z-half,1)]
    lathe(name+" | ground inner track", profile, [turned,ground], inner)
    profile = [(rim-.035,z-half,1),(rim,z-half+.035),(rim,z+half-.035),
               (rim-.035,z+half,1),(pitch+shoulder+.024,z+half,1),
               (pitch+shoulder,z+half-.024),(pitch+shoulder,z+t+.008)]
    profile += [(pitch+r,z+h,1) for r,h in reversed(race)]
    profile += [(pitch+shoulder,z-t-.008),(pitch+shoulder,z-half+.024),(pitch+shoulder+.024,z-half,1)]
    lathe(name+" | ground outer track", profile, [turned,ground], outer)
    # A turned seal register on each exposed outer-ring face.
    for side in (-1,1):
        face_z = z + side*half
        ring(name+" | seal register", rim-.111, rim-.094, face_z-.0014, face_z+.0014, .0008, [graphite], outer)
    rounded_elements(name+" | polished rolling elements", pitch, count, z, ball, ball, rolling, chrome)
    cage(name, pitch, ball, count, z, rolling)


def front_hardware():
    collar = group("Front | spanner nut", -3.94)
    def notched(row, r, a):
        delta = abs((a+math.pi/8) % (TAU/8) - math.pi/8)
        return r - .086 * max(0,min(1,(.135-delta)/.039)) if row < 4 else r
    nut = ring("Front | eight-slot bearing nut", .476,.741,-2.194,-2.008,.034,[satin],collar,notched,192)
    # Shallow pin-spanner bores drilled into the accessible front face.
    for i in range(4):
        a = TAU * (i+.27)/4
        bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=.047, depth=.14,
                                            location=(.598*math.cos(a),.598*math.sin(a),-2.184))
        subtract(nut,bpy.context.object)
    lock = group("Front | locking plate", -3.38)
    def tabs(row,r,a):
        delta = abs((a+math.pi/8) % (TAU/8)-math.pi/8)
        return r+.077*max(0,min(1,(.17-delta)/.037)) if row < 4 else r
    ring("Front | tab lock washer", .494,.695,-2.005,-1.966,.008,[ground],lock,tabs,192)
    spacer = group("Front | distance sleeve", -.76)
    ring("Front | ground distance sleeve", .497,.646,-1.50,-1.384,.016,[ground],spacer)


def rear_hardware():
    rear_spacer = group("Rear | distance sleeve", .70)
    ring("Rear | sleeve",.642,.808,2.147,2.312,.018,[ground],rear_spacer)
    plate = group("Rear | retaining flange",3.38)
    cap = ring("Rear | counterbored retaining flange",.408,.774,2.996,3.126,.024,[satin],plate)
    fasteners = group("Rear | four socket screws",4.06)
    for i in range(4):
        a = TAU*(i+.125)/4
        x,y = .525*math.cos(a),.525*math.sin(a)
        for radius, bottom, top in [(.055,2.95,3.18),(.094,3.071,3.19)]:
            bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=radius, depth=top-bottom,location=(x,y,(top+bottom)/2))
            subtract(cap,bpy.context.object)
        def hex_socket(row,r,a):
            return r/math.cos((a+math.pi/6)%(TAU/6)-math.pi/6) if row in (6,7) else r
        screw = lathe("Rear | socket-head cap screw",[(.041,2.846),(.050,2.855),(.050,3.07),
                      (.081,3.071),(.087,3.08),(.087,3.144),(.041,3.152),(.041,3.102),(.001,3.101),(.001,2.846)],
                      [graphite],fasteners,hex_socket,48)
        screw.location.x, screw.location.y = x,y
        thread = threaded_land("Rear | rolled screw thread",.0495,.055,.017,8,2.86,28,satin,fasteners)
        thread.location.x, thread.location.y = x,y
    rear_sleeve = group("Rear | clamp sleeve",2.88)
    ring("Rear | bearing clamp sleeve",.642,.799,2.774,2.996,.018,[ground],rear_sleeve)


def aim(obj, target):
    obj.rotation_euler = (Vector(target)-obj.location).to_track_quat("-Z","Y").to_euler()


def softbox(name, position, target, power, width, length):
    data = bpy.data.lights.new(name,"AREA")
    data.shape, data.energy, data.size, data.size_y = "RECTANGLE", power, width,length
    obj = bpy.data.objects.new(name,data)
    bpy.context.collection.objects.link(obj)
    obj.location = position
    aim(obj,target)


def studio(scene):
    cam = bpy.data.objects.new("Orthographic product camera",bpy.data.cameras.new("Product camera"))
    bpy.context.collection.objects.link(cam)
    cam.data.type = "ORTHO"
    for frame, position, target, roll, scale in [
            (1,(8,-11,-7),(0,0,-.02),-61,7.55),
            (90,(7,-14,-5.5),(0,0,.43),-65,13.95),
            (180,(8,-11,-7),(0,0,-.02),-61,7.55)]:
        cam.location = position
        aim(cam,target)
        cam.rotation_euler.rotate_axis("Z",math.radians(roll))
        cam.data.ortho_scale = scale
        cam.keyframe_insert(data_path="location",frame=frame)
        cam.keyframe_insert(data_path="rotation_euler",frame=frame)
        cam.data.keyframe_insert(data_path="ortho_scale",frame=frame)
    scene.camera = cam
    softbox("Key | long silk",(-3,-4,2),(0,0,0),800,2.8,12)
    softbox("Rim | strip bank",(1,4,2),(0,0,0),1100,2.0,12)
    softbox("Fill | broad bank",(6,-1,0),(0,0,0),420,4.7,12)
    softbox("End face | front",(-2,-1,-7),(0,0,-1),470,3.8,3.8)
    softbox("End face | rear",(-1,2,7),(0,0,2),600,4,4)
    scene.world = bpy.data.worlds.new("Neutral product studio")
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (.19,.19,.19,1)
    bg.inputs["Strength"].default_value = .65


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
turned = finish("Turned steel",(.45,.46,.47),.31,turning_normal())
ground = finish("Precision-ground steel",(.63,.65,.67),.225)
satin = finish("Satin gunmetal",(.26,.275,.286),.32)
graphite = finish("Black-oxide steel",(.106,.115,.127),.35)
chrome = finish("Polished bearing steel",(.76,.79,.82),.135)
cage_metal = finish("Zinc-plated pressed steel",(.52,.462,.349),.31)
spindle()
threaded_land("Spindle | retaining thread",.472,.494,.039,6,-2.227,72,ground)
front_hardware()
bearing("Front bearing",.497,-1.735,(-1.52,-2.18,-2.88),11)
bearing("Rear bearing",.642,2.543,(1.16,1.83,2.49),13)
rear_hardware()

MEDIA.mkdir(parents=True,exist_ok=True)
bpy.ops.export_scene.gltf(filepath=str(MEDIA/"shaft.glb"),export_animations=False,export_extras=True)
for obj in scene.objects:
    if "travel" in obj:
        for frame, factor in [(1,0),(90,1),(180,0)]:
            obj.location.z = factor * obj["travel"]
            obj.keyframe_insert(data_path="location",frame=frame)
scene.frame_end = 180
for frame, name in [(1,"Assembled"),(90,"Exploded"),(180,"Assembled")]:
    scene.timeline_markers.new(name,frame=frame)

studio(scene)
scene.render.engine = "CYCLES"
scene.cycles.samples = 36
scene.cycles.use_denoising = True
scene.render.resolution_x,scene.render.resolution_y = 1440,960
scene.render.film_transparent = True
scene.render.image_settings.file_format = "WEBP"
scene.render.image_settings.color_mode = "RGBA"
scene.render.image_settings.quality = 95
scene.view_settings.view_transform = "AgX"
scene.frame_set(1)
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == "VIEW_3D":
            area.spaces.active.region_3d.view_perspective = "CAMERA"
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/"blender"/"shaft.blend"),compress=True)
# Render on a GPU if Cycles offers one, leaving the saved scene portable.
preferences = bpy.context.preferences.addons["cycles"].preferences
for backend in ("OPTIX","CUDA","HIP","METAL"):
    try:
        preferences.compute_device_type = backend
        preferences.refresh_devices()
        gpu_devices = [device for device in preferences.devices if device.type == backend]
        if gpu_devices:
            for device in preferences.devices:
                device.use = device in gpu_devices
            scene.cycles.device = "GPU"
            break
    except (TypeError,RuntimeError):
        continue
for frame, pose in [(1,"assembled"),(90,"exploded")]:
    scene.frame_set(frame)
    scene.render.filepath = str(MEDIA/f"shaft-{pose}.webp")
    bpy.ops.render.render(write_still=True)
