"""16-битные текстурные координаты для GE PSP (правка Роба 43, 28.09: «вывеска SCHOOL будто срезана треугольником,
коврик Welcome поломан, и вот так всё»).

Причина семейства: GE читает 16-битные u, v БЕЗ знака (u16; с sceGuTexScale(128, 128) число/256 = повторы текстуры,
0…65535 = 0…256 повторов). Экспорт писал u*256 со знаком (int16): у треугольника, где одни вершины < 0 (−0.004 у края
вывески), а другие ≥ 0, отрицательное число читается как ≈256 повторов, и на один треугольник ложатся сотни повторов
текстуры — он рисуется плоским средним цветом (половина вывески школы, клин на коврике, пятна травы/дороги вдали).
Правило (для всех уровней и всех наборов с 16-битными UV): координаты сдвигаются на ЦЕЛОЕ число повторов (при GU_REPEAT
картинка та же, фильтр и мипы те же), чтобы у каждого треугольника все вершины были ≥ 0 и < 256 повторов:
  * без индексов (вершины по 3 на треугольник, флаг 16) — свой сдвиг у каждого треугольника (числа остаются малыми);
  * с общими вершинами (полосы, индексы) — один сдвиг на всю партию вершин (uv16_batch).
Данные те же: меняется только запись чисел, не картинка.

  tri_i16(u, v)   -> (u, v) как int16 для полей '<i2' (биты = u16), вход — float UV, по 3 вершины на треугольник
  batch_i16(u, v) -> то же одним сдвигом на все вершины
  span(uv_u16)    -> размах UV треугольников так, как их видит GE (для проверки tools/decals.py)"""
import numpy as np

SCALE = 256          # число в файле = uv * 256 (движок: sceGuTexScale(128, 128), 16 бит / 32768 * 128)
U16_MAX = 65535
REPEATS = (U16_MAX + 1) // SCALE   # 256 повторов текстуры — весь диапазон u16


def _shift(raw, groups):
    """raw (N, 2) int64 -> сдвиг на целое число повторов (кратно SCALE) по группам вершин (N // groups, groups, 2)"""
    r = raw.reshape(-1, groups, 2)
    lo = r.min(1)
    k = -np.floor_divide(lo, SCALE) * SCALE            # наименьшая вершина — в первый повтор [0, 1): числа малые, без переполнения
    r = r + k[:, None, :]
    return r.reshape(-1, 2)


def _pack(raw):
    over = int(((raw < 0) | (raw > U16_MAX)).any(1).sum())
    raw = np.clip(raw, 0, U16_MAX).astype(np.int64)
    out = raw.astype(np.uint16).view(np.int16)
    return out[:, 0].copy(), out[:, 1].copy(), over


def tri_i16(u, v):
    """float u, v (по 3 вершины на треугольник) -> int16 u, v (биты u16) со своим целым сдвигом у каждого треугольника"""
    raw = np.stack([np.round(np.asarray(u, np.float64) * SCALE), np.round(np.asarray(v, np.float64) * SCALE)], 1).astype(np.int64)
    if len(raw) % 3: raise ValueError('uvq.tri_i16: вершин не кратно 3')
    if not len(raw): return raw[:, 0].astype(np.int16), raw[:, 1].astype(np.int16)
    uu, vv, _ = _pack(_shift(raw, 3))
    return uu, vv


def tri_i16_clampv(u, v):
    """небо (№511): u — как tri_i16 (целый сдвиг на повторы, REPEAT), v — как есть в [0, 1] без сдвига: движок рисует небо с GU_CLAMP по v,
    значение за краем и так прижимается к краю. -> int16 u, v (биты u16)"""
    raw = np.stack([np.round(np.asarray(u, np.float64) * SCALE), np.round(np.asarray(v, np.float64) * SCALE)], 1).astype(np.int64)
    if len(raw) % 3: raise ValueError('uvq.tri_i16_clampv: вершин не кратно 3')
    if not len(raw): return raw[:, 0].astype(np.int16), raw[:, 1].astype(np.int16)
    r = raw.reshape(-1, 3, 2); k = -np.floor_divide(r[..., 0].min(1), SCALE) * SCALE
    raw[:, 0] = (r[..., 0] + k[:, None]).reshape(-1)
    raw[:, 1] = np.clip(raw[:, 1], 0, SCALE)
    uu, vv, _ = _pack(raw)
    return uu, vv


def batch_i16(u, v):
    """float u, v -> int16 u, v (биты u16) одним целым сдвигом на всю партию (общие вершины: полосы, индексы)"""
    raw = np.stack([np.round(np.asarray(u, np.float64) * SCALE), np.round(np.asarray(v, np.float64) * SCALE)], 1).astype(np.int64)
    if not len(raw): return raw[:, 0].astype(np.int16), raw[:, 1].astype(np.int16)
    uu, vv, _ = _pack(_shift(raw, len(raw)))
    return uu, vv


def ge_uv(u_i16, v_i16):
    """int16 из файла -> UV так, как их читает GE (без знака), float в повторах текстуры"""
    return (np.asarray(u_i16).astype(np.int16).view(np.uint16).astype(np.float64) / SCALE,
            np.asarray(v_i16).astype(np.int16).view(np.uint16).astype(np.float64) / SCALE)
