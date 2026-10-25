// Гейт правки Роба 892 на Маке (tests/tone/window892.sh): viewer/tone.c, режим Cartoon, настоящие палитры level.shr (L1).
// Окна вдалеке «слишком светлые»: общая доля рисунка toonTex стягивала тёмное стекло к среднему цвету текстуры. Печатает:
//   DEPTH  — глубина тёмного (запись темнее среднего текстуры по яркости больше 55 из 255) после тона к исходной, по текстурам, взвешено точками: 1,00 — рисунок как есть
//   SAME   — хеш палитр «земли» (байт 9 заголовка), ровных текстур (k = 0) и режима без Cartoon: при OLD=0 и OLD=1 обязан совпасть побайтно
//   cc -O1 -I viewer [-DTONE_WIN892_OLD=1] tests/tone/window892_host.c viewer/tone.c -lm -o /tmp/w892 && /tmp/w892 level.shr
#include "tone.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static unsigned u32(const unsigned char *p) { unsigned v; memcpy(&v, p, 4); return v; }
static unsigned long long fnv(unsigned long long h, const unsigned char *p, int n) { for (int i = 0; i < n; i++) { h ^= p[i]; h *= 1099511628211ULL; } return h; }
static float lum(const unsigned char *c) { return .299f * c[0] + .587f * c[1] + .114f * c[2]; }
int main(int argc, char **argv) {
  FILE *f = fopen(argc > 1 ? argv[1] : "build/level.shr", "rb"); if (!f) { printf("FAIL: нет файла\n"); return 1; }
  fseek(f, 0, SEEK_END); long sz = ftell(f); fseek(f, 0, SEEK_SET); unsigned char *d = malloc(sz); if (fread(d, 1, sz, f) != (size_t)sz) { printf("FAIL: чтение\n"); return 1; }
  unsigned ntex = u32(d + 4); int hw = (int)u32(d + 68), hh = (int)u32(d + 72); size_t p = 104 + (size_t)hw * hh * 8; p = (p + 15) & ~15u; p += (size_t)hw * hh * 4; p = (p + 15) & ~15u;
  toneSetSat(156); toneSetContrast(150); toneToonTex(45);
  double sumRaw = 0, sumTone = 0, wsum = 0; int used = 0;
  unsigned long long hGround = 14695981039346656037ULL, hFlat = hGround, hPlain = hGround; int nGround = 0, nFlat = 0, nPlain = 0;
  for (unsigned i = 0; i < ntex; i++) {
    unsigned short *t = (unsigned short *)(d + p); int w = t[0], h = t[1], lv = t[2], t4 = d[p + 6] == 4, pre = d[p + 7] == 1, ground = d[p + 9] == 1;
    unsigned char *pal = d + p + 16, *px = pal + 1024; int rb0 = t4 ? (w / 2 < 16 ? 16 : w / 2) : (pre && w < 16 ? 16 : w), rows0 = pre ? (h + 7) & ~7 : h;
    unsigned cnt[256] = {0}; unsigned n = (unsigned)rb0 * rows0, step = n > 4096 ? 3 : 1;   // как texToonStat (main_levels.h)
    if (t4) for (unsigned j = 0; j < n; j += step) { cnt[px[j] & 15]++; cnt[px[j] >> 4]++; } else for (unsigned j = 0; j < n; j += step) cnt[px[j]]++;
    float sr = 0, sg = 0, sb = 0, sl = 0, sll = 0, sw = 0;
    for (int j = 0; j < 256; j++) { if (!cnt[j]) continue; const unsigned char *c = pal + j * 4; if (c[3] < 16) continue; float wt = (float)cnt[j], l = lum(c); sr += wt * c[0]; sg += wt * c[1]; sb += wt * c[2]; sl += wt * l; sll += wt * l * l; sw += wt; }
    unsigned char st[5] = {0, 0, 0, 0, (unsigned char)(ground ? 4 : 0)};
    if (sw > 0) { float m = sl / sw, var = sll / sw - m * m, sd = var > 0 ? sqrtf(var) : 0, k = (sd - 10.f) / 40.f; k = k < 0 ? 0 : k > 1 ? 1 : k; k = .10f + k * .50f;
      st[0] = (unsigned char)(sr / sw + .5f); st[1] = (unsigned char)(sg / sw + .5f); st[2] = (unsigned char)(sb / sw + .5f); st[3] = (unsigned char)(k * 255.f + .5f); }
    int flat = st[3] <= 46 && !ground;
    unsigned char a[1024], b[1024]; memcpy(a, pal, 1024); memcpy(b, pal, 1024);
    toneSetToon(1); toneSetStat(sw > 0 ? st : 0); tonePal(a); toneSetStat(0);
    toneSetToon(0); tonePal(b);
    if (ground) { hGround = fnv(hGround, a, 1024); nGround++; }
    if (flat && sw > 0) { hFlat = fnv(hFlat, a, 1024); nFlat++; }
    hPlain = fnv(hPlain, b, 1024); nPlain++;
    if (sw > 0 && !ground && !flat) {   // глубина тёмного: средняя яркость точек после тона против исходной, у записей темнее среднего больше 55
      float lm = sl / sw; double wd = 0, rawD = 0, toneD = 0, rawM = 0, toneM = 0, wAll = 0;
      for (int j = 0; j < 256; j++) { if (!cnt[j] || pal[j * 4 + 3] < 16) continue; rawM += cnt[j] * lum(pal + j * 4); toneM += cnt[j] * lum(a + j * 4); wAll += cnt[j]; }
      rawM /= wAll; toneM /= wAll;
      for (int j = 0; j < 256; j++) { if (!cnt[j] || pal[j * 4 + 3] < 16) continue; if (lm - lum(pal + j * 4) > 55.f) { wd += cnt[j]; rawD += cnt[j] * (rawM - lum(pal + j * 4)); toneD += cnt[j] * (toneM - lum(a + j * 4)); } }
      if (wd > 0 && rawD > 0) { sumRaw += rawD; sumTone += toneD; wsum += wd; used++; }
    }
    // следующая запись: пропуск уровней
    size_t q = p + 16 + 1024; int lw = w, lh = h;
    for (int l = 0; l < lv; l++) { int rb = t4 ? (lw / 2 < 16 ? 16 : lw / 2) : (pre && lw < 16 ? 16 : lw); q += (size_t)rb * (pre ? (lh + 7) & ~7 : lh); q = (q + 15) & ~15u; lw >>= 1; lh = lh > 1 ? lh >> 1 : 1; }
    p = q;
  }
  double ratio = sumRaw > 0 ? sumTone / sumRaw : 0;
  printf("DEPTH %.3f textures %d dark-points %.0f\n", ratio, used, wsum);
  printf("SAME ground %d %016llx flat %d %016llx plain %d %016llx\n", nGround, hGround, nFlat, hFlat, nPlain, hPlain);
  return 0;
}
