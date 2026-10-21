#!/usr/bin/env python3
"""Body PhysicsObject selection over every disc car; --red uses old first chunk.
BV proxies have different joints, inertia and bounds and may occur first.
"""
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import psp_export as P

red = '--red' in sys.argv
checked = bad = reordered = 0
for path in sorted((P.GAME / 'art/cars').glob('*.p3d')):
    root = P.read(path)
    objects = [c for c in root.children if c.id == 0x7011000]
    bodies = [c for c in objects if not P.string(c.data)[0].lower().endswith('bv')]
    if not bodies:
        continue
    if len(bodies) != 1:
        raise ValueError('Ambiguous native body: ' + path.name)
    actual = objects[0] if red else P.car_physics_object(root)
    checked += 1
    reordered += objects[0] is not bodies[0]
    if actual is not bodies[0]:
        bad += 1
        native = sum(struct.unpack_from('<I', c.data, 20)[0] == 1 for c in bodies[0].children if c.id == 0x7011020)
        old = sum(struct.unpack_from('<I', c.data, 20)[0] == 1 for c in actual.children if c.id == 0x7011020)
        print('FAIL', path.name, 'selected', P.string(actual.data)[0], 'hinges', old, 'native', native)
if checked < 80 or reordered < 20:
    raise ValueError('Native fleet coverage incomplete')
print('cars', checked, 'BV-first', reordered, 'failures', bad)
raise SystemExit(bool(bad))
