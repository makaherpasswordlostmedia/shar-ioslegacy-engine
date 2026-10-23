# Монета-спрайт (Роб 17.10: «генерируешь заранее на макбуке, запекаешь красиво в гифку без фона… одну на всех»): Blender без окна рисует оборот
# настоящей монеты игры (tools/coin/coin_dump.py → coin.json, coin_tex.png) — N кадров ровно на 360° (бесшовная петля: кадр N = кадр 0, не рисуется),
# прозрачный фон, золото с бликом, торец виден. Запуск: Blender -b --factory-startup -P tools/coin/coin_blender.py -- SRC_DIR OUT_DIR N RES
import bpy, json, math, os, sys
a = sys.argv[sys.argv.index('--') + 1:]; SRC, OUT, N, RES = a[0], a[1], int(a[2]), int(a[3]); os.makedirs(OUT, exist_ok=True)
d = json.load(open(os.path.join(SRC, 'coin.json'))); P, T, UV, C = d['P'], d['T'], d['UV'], d['C']
bpy.ops.wm.read_factory_settings(use_empty=True); sc = bpy.context.scene
xs, ys, zs = [p[0] for p in P], [p[1] for p in P], [p[2] for p in P]
cx, cy, cz = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2
FLIP = float(os.environ.get('COIN_FLIP', '1'))   # игра (x, y вверх, z) -> Blender (x, -z, y): ось вращения — вертикаль через центр монеты
V = [(FLIP * (p[0] - cx), -(p[2] - cz), p[1] - cy) for p in P]
# №880 (как в принятой сцене SHAR_coin.blend, канон навыка psp-render): игра рисует монету двусторонне — грань оборота (|n| вдоль толщины, центр
# с другой стороны, чем смотрит нормаль) развёрнута внутрь; разворачиваем наружу и зеркалим картинку (u, v -> 1-u, 1-v), чтобы знак читался сзади
FL = set()
def _nrm(t):
    a, b, c = (V[i] for i in t); u = [b[k] - a[k] for k in range(3)]; w = [c[k] - a[k] for k in range(3)]
    n = (u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]); l = math.sqrt(sum(x * x for x in n)) or 1.0
    return [x / l for x in n]
TT = []
for fi, t in enumerate(T):
    n = _nrm(t); cyy = sum(V[i][1] for i in t) / 3
    if os.environ.get('COIN_BACK_OLD') != '1' and abs(n[1]) > .9 and (n[1] > 0) != (cyy > 0): FL.add(fi); t = [t[0], t[2], t[1]]
    TT.append(tuple(t))
me = bpy.data.meshes.new('coin'); me.from_pydata(V, [], TT); me.update()
me.uv_layers.new(name='UV'); me.color_attributes.new(name='Col', type='FLOAT_COLOR', domain='CORNER')
uvl = me.uv_layers['UV']; col = me.color_attributes['Col']   # №880: Blender 5 — ссылка на слой развёртки устаревает после color_attributes.new: брать по имени
for poly in me.polygons:
    for li in poly.loop_indices:
        vi = me.loops[li].vertex_index; col.data[li].color = C[vi]
        uvl.data[li].uv = (1.0 - UV[vi][0], 1.0 - UV[vi][1]) if poly.index in FL else (UV[vi][0], 1.0 - UV[vi][1])
ob = bpy.data.objects.new('coin', me); sc.collection.objects.link(ob)
mat = bpy.data.materials.new('coin'); mat.use_nodes = True; nt = mat.node_tree; bs = nt.nodes['Principled BSDF']
tx = nt.nodes.new('ShaderNodeTexImage'); tx.image = bpy.data.images.load(os.path.join(SRC, 'coin_tex.png')); tx.interpolation = 'Linear'
um = nt.nodes.new('ShaderNodeUVMap'); um.uv_map = 'UV'; nt.links.new(um.outputs['UV'], tx.inputs['Vector'])   # №880: без явной развёртки картинка ложится повтором
vc = nt.nodes.new('ShaderNodeVertexColor'); vc.layer_name = 'Col'
mu = nt.nodes.new('ShaderNodeVectorMath'); mu.operation = 'MULTIPLY'
nt.links.new(tx.outputs['Color'], mu.inputs[0]); nt.links.new(vc.outputs['Color'], mu.inputs[1]); nt.links.new(mu.outputs['Vector'], bs.inputs['Base Color'])
bs.inputs['Metallic'].default_value = float(os.environ.get('COIN_METAL', '0.55')); bs.inputs['Roughness'].default_value = float(os.environ.get('COIN_ROUGH', '0.32'))
me.materials.append(mat)
def light(name, loc, power, size):
    L = bpy.data.lights.new(name, 'AREA'); L.energy = power; L.size = size; o = bpy.data.objects.new(name, L); o.location = loc; sc.collection.objects.link(o)
    tc = o.constraints.new('TRACK_TO'); tc.target = ob; tc.track_axis = 'TRACK_NEGATIVE_Z'; tc.up_axis = 'UP_Y'
light('key', (-1.4, 2.2, 1.6), 90.0, 1.6); light('fill', (1.8, 1.6, 0.2), 25.0, 2.0); light('rim', (0.4, -2.2, 1.8), 70.0, 1.2)   # №880: как в принятой сцене SHAR_coin.blend (вид с +Y)
w = bpy.data.worlds.new('w'); w.use_nodes = True; bg = w.node_tree.nodes['Background']; bg.inputs['Color'].default_value = (0.55, 0.55, 0.6, 1); bg.inputs['Strength'].default_value = 0.5; sc.world = w
cd = bpy.data.cameras.new('cam'); cd.type = 'ORTHO'; cd.ortho_scale = max(max(xs) - min(xs), max(ys) - min(ys)) * 1.08
cam = bpy.data.objects.new('cam', cd); cam.location = (0, 4, 0); cam.rotation_euler = (math.pi / 2, 0, math.pi); sc.collection.objects.link(cam); sc.camera = cam   # №880: камера принятой сцены
sc.render.engine = 'CYCLES'; sc.cycles.samples = int(os.environ.get('COIN_SAMPLES', '96')); sc.cycles.use_denoising = False; sc.cycles.device = 'CPU'
sc.render.film_transparent = True; sc.render.resolution_x = sc.render.resolution_y = RES; sc.render.resolution_percentage = 100; sc.render.filter_size = 1.2
sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGBA'; sc.render.image_settings.color_depth = '8'
sc.view_settings.view_transform = 'Standard'; sc.view_settings.look = 'None'
for k in range(N):
    ob.rotation_euler = (0, 0, 2 * math.pi * k / N); sc.render.filepath = os.path.join(OUT, f'f_{k:02d}.png'); bpy.ops.render.render(write_still=True)
print('COINBAKE готово', N, 'кадров', RES, 'px; ortho', round(cd.ortho_scale, 4), 'центр', round(cx, 4), round(cy, 4), round(cz, 4))
