"""Ключ кластера ботов (Т1.1, docs/handoff/ДВА_ТЕСТИРОВЩИКА_2026-09-28.md §3): уровень + событие + слой опоры + объект + клетка 8 м.
Слой и объект считает C (bwWhere в tools/bots/world.c): слой 0 — нижняя опора (земля, дорога), 1+ — крыша, эстакада, навес над ней,
-1 — ниже всех опор; объект — примитив коллизии рядом ("b12" ящик, "c3" цилиндр, "t45" треугольник, "s6" забор, "-" ничего).
Дорога и крыша в одной клетке — два разных ключа; координаты точные остаются в записи кластера для повтора.
BOTS_KEY_FLAT=1 — отрицательный контроль гейта: ключ как до Т1.1 (только событие и клетка), этаж и объект сливаются."""
import math, os

LEVEL = 1


def cluster_key(kind, x, z, layer=0, obj='-', level=LEVEL):
    cx, cz = int(math.floor(x / 8)) * 8, int(math.floor(z / 8)) * 8
    if os.environ.get('BOTS_KEY_FLAT'): return f'bots:{kind}:{cx}:{cz}'
    return f'bots:L{level}:{kind}:{layer}:{obj}:{cx}:{cz}'


def parse_key(key):
    """ключ -> dict(level, kind, layer, obj, cx, cz); старый ключ (bots:kind:x:z) — слой 0, объект '-'"""
    f = key.split(':')
    if len(f) == 7: return dict(level=int(f[1][1:]), kind=f[2], layer=int(f[3]), obj=f[4], cx=int(f[5]), cz=int(f[6]))
    return dict(level=LEVEL, kind=f[1], layer=0, obj='-', cx=int(f[2]), cz=int(f[3]))


def obj_name(obj, names):
    """'b12' -> 'l1r3/имя_объекта' по build/sandbox/colnames-l1.json (tools/cartest/colnames.py); треугольник — земля, s — забор"""
    if not obj or obj == '-': return '—'
    t, i = obj[0], int(obj[1:])
    try:
        if t == 'b' and names: nm, sc = names['box'][i]; return f'{sc}/{nm}'
        if t == 'c' and names: nm, sc = names['cyl'][i]; return f'{sc}/{nm}'
    except (IndexError, KeyError, TypeError): pass
    return {'t': 'земля/стена (треугольник)', 's': 'забор'}.get(t, obj) + f' {obj}'
