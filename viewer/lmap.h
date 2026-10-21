// Загрузка 2, пункт 2: карта высот и стены (hm, wl) уровня лежат в level.shr плотным массивом (3,6 МБ на L3, сжимается на 99 %).
// Рядом с уровнем лежит lmap.shr: те же байты, сжатые блоком LZ4 (tools/lmap_pack.c). Движок читает его (~0,1 МБ), распаковывает на место
// и пропускает плотный массив в level.shr (читает с конца карты). Ключ — хеш 104-байтного заголовка level.shr и его размера: файл от другого
// уровня не подходит; хеш распакованного — защита от порчи. Нет файла / ключ не тот / хеш не тот — читается плотный массив, как раньше.
// level.shr при этом НЕ меняется (формат SHR7, все инструменты читают его как прежде). LMAP_OLD=1 — без lmap.shr
#ifndef LMAP_H
#define LMAP_H
#include <string.h>
#include <stdint.h>
#define LMAP_MAGIC "LMP1"
typedef struct { char magic[4]; uint32_t ver, key, denseBytes, compBytes, denseHash, pad[2]; } LmapHead;   // 32 Б, дальше блок LZ4
static inline unsigned lmapHash(const void *p, unsigned n) {   // тот же приём, что mcProbeHash (viewer/msncar.c): слова + хвост
  const unsigned char *b = (const unsigned char *)p; unsigned h = 2166136261u ^ n, i = 0;
  for (; i + 4 <= n; i += 4) { unsigned w = (unsigned)b[i] | (unsigned)b[i + 1] << 8 | (unsigned)b[i + 2] << 16 | (unsigned)b[i + 3] << 24; h = (h ^ w) * 16777619u; h ^= h >> 15; }
  for (; i < n; i++) h = (h ^ b[i]) * 16777619u;
  return h;
}
static inline unsigned lmapKey(const void *hdr104, unsigned fileSize) { return lmapHash(hdr104, 104) * 31u ^ fileSize; }
// плотный массив: от 104 до конца стен (выровнено по 16), как считает levelLoad
static inline unsigned lmapDenseEnd(unsigned hw, unsigned hh) {
  unsigned p = 104; p += hw * hh * 4 * 2; p = (p + 15) & ~15u; p += hw * hh * 2 * 2; p = (p + 15) & ~15u; return p;
}
// блок LZ4 (https://github.com/lz4/lz4/blob/dev/doc/lz4_Block_format.md) -> ровно dn байт; 0 — ок, -1 — битый
static inline int lmapUnpack(const unsigned char *s, unsigned sn, unsigned char *d, unsigned dn) {
  const unsigned char *se = s + sn; unsigned char *dp = d, *de = d + dn;
  while (s < se) {
    unsigned t = *s++, ll = t >> 4, c;
    if (ll == 15) { do { if (s >= se) return -1; c = *s++; ll += c; } while (c == 255); }
    if (ll > (unsigned)(se - s) || ll > (unsigned)(de - dp)) return -1;
    memcpy(dp, s, ll); dp += ll; s += ll;
    if (s >= se) break;
    if (se - s < 2) return -1;
    unsigned off = (unsigned)s[0] | (unsigned)s[1] << 8; s += 2;
    if (!off || off > (unsigned)(dp - d)) return -1;
    unsigned ml = t & 15; if (ml == 15) { do { if (s >= se) return -1; c = *s++; ml += c; } while (c == 255); }
    ml += 4; if (ml > (unsigned)(de - dp)) return -1;
    const unsigned char *m = dp - off;
    if (off >= ml) { memcpy(dp, m, ml); dp += ml; } else while (ml--) *dp++ = *m++;
  }
  return dp == de ? 0 : -1;
}
#endif
