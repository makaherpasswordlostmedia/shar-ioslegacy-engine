"""Близнецы · общее (docs/handoff/БЛИЗНЕЦЫ_2026-10-01.md): пути, пакет §1, перевод координат порт ↔ оригинал.

Код — в рабочей копии (WT), данные и результаты — в основной папке проекта (DATA, по git common dir; TWINS_ROOT — вручную):
диск и состояния оригинала build/ps2ref/, сборка порта build/, итог близнецов build/twins/.

Пакет — одна строка JSON от стороны на точку, ключи ровно как в ТЗ §1. Чего сторона не знает — null (не выдумка);
пустой список [] — сторона знает, что там пусто.
  point, side ('orig' | 'port_light' | 'port_full'), frame (кадр стороны от синхронизации; темп — SIDE_FPS),
  pos [x, y, z] и vel [vx, vy, vz] — в осях ОРИГИНАЛА (мир PS2, м, м/с): порт отзеркален по z (z_ps2 = -z_порта),
  pos — начало модели машины (у оригинала — перенос матрицы рисования, у порта — низ колёс + lift машины),
  heading — курс носа в мире оригинала, рад: atan2(нос.x, нос.z) (нос оригинала — строка 2 матрицы; у порта нос = (sin h, cos h)),
  onfoot, room, cam {pos, target, fov}, loaded [], events [], mem {free МБ, ge КБ}, counters {tris, ge_bytes, draws, cells, cars, peds},
  shot — путь кадра относительно папки прогона."""
import hashlib, json, math, os, subprocess
from pathlib import Path

WT = Path(__file__).resolve().parents[2]


def _data_root():
    env = os.environ.get('TWINS_ROOT')
    if env: return Path(env).resolve()
    try:
        cd = subprocess.run(['git', '-C', str(WT), 'rev-parse', '--git-common-dir'], capture_output=True, text=True, check=True).stdout.strip()
        p = Path(cd) if os.path.isabs(cd) else (WT / cd)
        return p.resolve().parent
    except (OSError, subprocess.CalledProcessError):
        return WT


DATA = _data_root()
OUT = DATA / 'build/twins'
BIN = OUT / 'bin'
SIDE_FPS = {'orig': 50.0, 'port_light': 60.0, 'port_full': 60.0}   # счётчик frame: оригинал PAL 0x5167d8 (+2 за такт 25 Гц), порт 1/60 с
# профиль PCSX2 близнецов. По умолчанию observer1 (PINE 28121): единственный, чей скрытый запуск доказан вживую (30.09, 38 прогонов
# ask.py: фокус и окна чисто, личный профиль Роба те же хеши). observer3 01.10 01:31 и 01:33 дважды не стартовал: `open` вернул -10810
# до создания процесса (окна не было); причина не найдена — открытый вопрос в tools/twins/README.md. Занятость observer1 оракулом
# ask.py проверяет сам (свой PID уже запущен -> отказ). TWINS_PROFILE=3 — только после разбора -10810.
PROFILE = int(os.environ.get('TWINS_PROFILE', '1'))


def clock():
    """Время в журналах — только из date (память Роба: время на глаз запрещено)."""
    return subprocess.check_output(['date', '+%Y-%m-%d %H:%M:%S %Z'], text=True).strip()


def stamp():
    return subprocess.check_output(['date', '+%Y%m%d-%H%M%S'], text=True).strip()


def sha256(path, n=None):
    h = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    return h[:n] if n else h


def git_head():
    r = subprocess.run(['git', '-C', str(WT), 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True)
    d = subprocess.run(['git', '-C', str(WT), 'status', '--porcelain', '--', 'viewer', 'tools/bots', 'tools/twins'], capture_output=True, text=True)
    return r.stdout.strip() + ('+правки' if d.stdout.strip() else '')


def packet(point, side):
    return {'point': point, 'side': side, 'frame': None, 'pos': None, 'heading': None, 'vel': None, 'onfoot': None, 'room': None,
            'cam': {'pos': None, 'target': None, 'fov': None}, 'loaded': None, 'events': None,
            'mem': {'free': None, 'ge': None},
            'counters': {'tris': None, 'ge_bytes': None, 'draws': None, 'cells': None, 'cars': None, 'peds': None},
            'shot': None}


_SHAPE = packet('', '')


def check_packet(p):
    """Схема §1 дословно: те же ключи верхнего уровня и вложенных cam/mem/counters; сторона из SIDE_FPS."""
    if set(p) != set(_SHAPE): raise ValueError(f'пакет: ключи {sorted(set(p) ^ set(_SHAPE))} не по схеме §1')
    for k in ('cam', 'mem', 'counters'):
        if not isinstance(p[k], dict) or set(p[k]) != set(_SHAPE[k]): raise ValueError(f'пакет: {k} не по схеме §1')
    if p['side'] not in SIDE_FPS: raise ValueError(f'пакет: сторона {p["side"]!r} не из {sorted(SIDE_FPS)}')
    for k in ('pos', 'vel'):
        if p[k] is not None and (len(p[k]) != 3 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in p[k])):
            raise ValueError(f'пакет {p["side"]}: {k} не тройка чисел')
    return p


def line(p):
    return json.dumps(check_packet(p), ensure_ascii=False, separators=(',', ':'))


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def yaw_of_port(h):
    """курс порта h (нос (sin h, cos h) в осях порта) -> курс в мире оригинала"""
    return wrap(math.pi - h)


def port_h_of_yaw(yaw):
    return wrap(math.pi - yaw)


def yaw_of_mat(m):
    """матрица рисования оригинала (16 float, строки): нос — строка 2"""
    return math.atan2(m[8], m[10])


def z_flip(v):
    return [v[0], v[1], -v[2]]


def level_lift(level_shr):
    """lift машины уровня (CAR1 @ заголовок+100, float @ +32 — как carVisInit и tools/bots/world.c)"""
    import struct
    b = Path(level_shr).read_bytes()
    if b[:4] != b'SHR7': raise ValueError(f'{level_shr}: не SHR7')
    c1 = struct.unpack_from('<I', b, 100)[0]
    return struct.unpack_from('<f', b, c1 + 32)[0] if c1 else 0.0


def level_spawn(level_shr):
    """спавн уровня из заголовка SHR7 (x y z курс, оси порта)"""
    import struct
    return list(struct.unpack_from('<4f', Path(level_shr).read_bytes(), 12 + 6 * 4))
