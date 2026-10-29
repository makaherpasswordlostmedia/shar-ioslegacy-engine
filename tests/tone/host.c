// Гейт правки Роба 144 на Маке (tests/tone/run.sh): viewer/tone.c на настоящих палитрах build/level.shr.
//  1) обратимость: загрузка при 1.36 -> ползунок 1.60 -> 1.00 -> снова 1.36 = побайтно палитры свежей загрузки
//     (палитры перечитываются из файла; -DTONE_INPLACE — кривая поверх уже тонированной, как palTone до 01.10 -> КРАСНОЕ)
//  2) насыщенность по умолчанию выше прежней (1.28, жёсткий кламп): хрома цветов, не упёршихся в край, >= x1.04
//     (-DTONE_SAT_DEF=128 -DTONE_SOFT=0 — прежний код -> КРАСНОЕ)
//  3) мягкий потолок держит оттенок: наибольший сдвиг тона ярких насыщенных цветов <= 3 градусов
//     (-DTONE_SOFT=0 — жёсткий кламп по каналам -> КРАСНОЕ)
//  4) палитра вне зарегистрированных блоков (HUD, ui.shr) не трогается: toneRedo = -1 и байты те же
//   cc -O1 -I viewer tests/tone/host.c viewer/tone.c -lm -o build/tone-host && build/tone-host build/level.shr
#include "tone.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static FILE *lvf;
static int rd(void *u, unsigned file, unsigned off, void *dst, unsigned n) {
  (void)u; (void)file;
  return fseek(lvf, (long)off, SEEK_SET) || fread(dst, 1, n, lvf) != n ? -1 : 0;
}
static unsigned u32(const unsigned char *p) { unsigned v; memcpy(&v, p, 4); return v; }

// палитры текстур уровня по правилу строки движка (viewer/main.c levelLoad; байт 6 = 4 — T4, строка вдвое короче)
static int walk(unsigned char *d, unsigned *pals, int max) {
  unsigned ntex = u32(d + 4); int hw = (int)u32(d + 68), hh = (int)u32(d + 72);
  size_t p = 104; p += (size_t)hw * hh * 8; p = (p + 15) & ~15u; p += (size_t)hw * hh * 4; p = (p + 15) & ~15u;
  int n = 0;
  for (unsigned i = 0; i < ntex && n < max; i++) {
    unsigned short *t = (unsigned short *)(d + p); int w = t[0], h = t[1], lv = t[2], t4 = d[p + 6] == 4, pre = d[p + 7] == 1;
    pals[n++] = (unsigned)(p + 16); p += 16 + 1024;
    int lw = w, lh = h;
    for (int l = 0; l < lv; l++) {
      int row = t4 ? (lw / 2 < 16 ? 16 : lw / 2) : (pre && lw < 16 ? 16 : lw);
      p += (size_t)row * (pre ? (lh + 7) & ~7 : lh); p = (p + 15) & ~15u; lw >>= 1; lh = lh > 1 ? lh >> 1 : 1;
    }
  }
  return n;
}
static float hue(float r, float g, float b) {
  float mx = fmaxf(r, fmaxf(g, b)), mn = fminf(r, fminf(g, b)), c = mx - mn, h;
  if (c < 1e-3f) return -1.f;
  if (mx == r) h = fmodf((g - b) / c + 6.f, 6.f); else if (mx == g) h = (b - r) / c + 2.f; else h = (r - g) / c + 4.f;
  return h * 60.f;
}
// прежняя кривая (main.c palTone до 01.10): гамма 1.10, контраст 1.12, насыщенность 1.28, жёсткий кламп
static void oldTone(unsigned char *c) {
  for (int i = 0; i < 256; i++, c += 4) {
    float q[3];
    for (int j = 0; j < 3; j++) { float v = 255.f * powf(c[j] / 255.f, 1.10f); v = (v - 128.f) * 1.12f + 128.f; q[j] = (float)(unsigned char)fminf(255.f, fmaxf(0.f, v + .5f)); }
    float y = .299f * q[0] + .587f * q[1] + .114f * q[2];
    for (int j = 0; j < 3; j++) c[j] = (unsigned char)fminf(255.f, fmaxf(0.f, y + (q[j] - y) * 1.28f + .5f));
  }
}

int main(int argc, char **argv) {
  const char *fn = argc > 1 ? argv[1] : "build/level.shr";
  lvf = fopen(fn, "rb"); if (!lvf) { printf("FAIL: нет %s\n", fn); return 1; }
  unsigned char hdr[104]; if (fread(hdr, 1, 104, lvf) != 104 || memcmp(hdr, "SHR7", 4)) { printf("FAIL: не SHR7\n"); return 1; }
  unsigned res = u32(hdr + 84) + 48 * u32(hdr + 80);
  unsigned char *d = malloc(res), *raw = malloc(res);
  fseek(lvf, 0, SEEK_SET); if (fread(d, 1, res, lvf) != res) { printf("FAIL: чтение\n"); return 1; }
  memcpy(raw, d, res);
  static unsigned pals[4096]; int np = walk(d, pals, 4096);
  toneBlkAdd(d, res, 0, 0);
  for (int i = 0; i < np; i++) tonePal(d + pals[i]);   // загрузка уровня при насыщенности по умолчанию
  unsigned char *fresh = malloc(res); memcpy(fresh, d, res);
  int fails = 0;
  // 1) обратимость
  int steps[3] = {160, 100, TONE_SAT_DEF}, bad = 0;
  for (int s = 0; s < 3; s++) { toneSetSat(steps[s]); for (int i = 0; i < np; i++) if (toneRedo(d + pals[i], rd, 0)) bad++; }
  int diff = 0; for (int i = 0; i < np; i++) diff += memcmp(d + pals[i], fresh + pals[i], 1024) != 0;
  printf("%s обратимость: 1.36 -> 1.60 -> 1.00 -> 1.36, палитр %d, отличаются %d, ошибок чтения %d\n", diff || bad ? "КРАСНОЕ" : "OK", np, diff, bad);
  fails += diff || bad;
  // 2) насыщенность выше прежней; 3) оттенок ярких
  double chNew = 0, chOld = 0, uNew = 0, uOld = 0; long cnt = 0, ucnt = 0; float worst = 0.f;
  for (int i = 0; i < np; i++) {
    unsigned char o[1024]; memcpy(o, raw + pals[i], 1024); oldTone(o);
    const unsigned char *nw = fresh + pals[i], *src = raw + pals[i];
    for (int k = 0; k < 256; k++) {
      const unsigned char *a = src + 4 * k; if (!a[3]) continue;
      int mxo = o[4 * k] > o[4 * k + 1] ? o[4 * k] : o[4 * k + 1]; mxo = mxo > o[4 * k + 2] ? mxo : o[4 * k + 2];
      int mno = o[4 * k] < o[4 * k + 1] ? o[4 * k] : o[4 * k + 1]; mno = mno < o[4 * k + 2] ? mno : o[4 * k + 2];
      const unsigned char *b = nw + 4 * k;
      int mxn = b[0] > b[1] ? b[0] : b[1]; mxn = mxn > b[2] ? mxn : b[2]; int mnn = b[0] < b[1] ? b[0] : b[1]; mnn = mnn < b[2] ? mnn : b[2];
      chOld += mxo - mno; chNew += mxn - mnn; cnt++;
      if (mxo < 255 && mno > 0 && mxn < 255 && mnn > 0) { uOld += mxo - mno; uNew += mxn - mnn; ucnt++; }   // не упёрлись в край ни там, ни тут
      // оттенок до насыщения (после гаммы/контраста) против итога; только явно цветные (хрома источника >= 40)
      int mxs = a[0] > a[1] ? a[0] : a[1]; mxs = mxs > a[2] ? mxs : a[2]; int mns = a[0] < a[1] ? a[0] : a[1]; mns = mns < a[2] ? mns : a[2];
      if (mxs - mns >= 40 && mxn - mnn >= 40) {
        float q[3]; for (int j = 0; j < 3; j++) { float v = 255.f * powf(a[j] / 255.f, 1.10f); v = (v - 128.f) * 1.12f + 128.f; q[j] = (float)(unsigned char)fminf(255.f, fmaxf(0.f, v + .5f)); }
        float h0 = hue(q[0], q[1], q[2]), h1 = hue(b[0], b[1], b[2]), dh = fabsf(h0 - h1); if (dh > 180.f) dh = 360.f - dh;
        if (h0 >= 0.f && h1 >= 0.f && dh > worst) worst = dh;
      }
    }
  }
  // критерий — цвета, не упёршиеся в край (там множитель виден честно, ожидание 1.36/1.28 = x1.0625); общая хрома — для сводки
  double ratio = chOld > 0 ? chNew / chOld : 0, uratio = uOld > 0 ? uNew / uOld : 0;
  printf("%s насыщенность: хрома цветов без края x%.3f (порог x1.04, цветов %ld); все цвета %.1f против прежних %.1f (x%.3f, %ld)\n",
         uratio >= 1.04 ? "OK" : "КРАСНОЕ", uratio, ucnt, chNew / (cnt ? cnt : 1), chOld / (cnt ? cnt : 1), ratio, cnt);
  fails += uratio < 1.04;
  printf("%s оттенок: наибольший сдвиг тона цветных %.1f° (порог 3°; эталон — цвет до насыщения)\n", worst <= 3.f ? "OK" : "КРАСНОЕ", worst);
  fails += worst > 3.f;
  // 4) палитра вне блоков
  unsigned char ui[1024], ui0[1024]; for (int k = 0; k < 1024; k++) ui[k] = ui0[k] = (unsigned char)(k * 37);
  int r = toneRedo(ui, rd, 0);
  printf("%s HUD: палитра вне блоков не тронута (toneRedo=%d)\n", r == -1 && !memcmp(ui, ui0, 1024) ? "OK" : "КРАСНОЕ", r);
  fails += !(r == -1 && !memcmp(ui, ui0, 1024));
  printf("%s\n", fails ? "FAIL" : "PASS");
  return fails ? 1 : 0;
}
