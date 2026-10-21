// Проверка звука включения заставки (правка Роба 128: «нажали кнопку, включился кулер и пикнул старый компьютер 90-х»;
// прежде — tests/bootbeep, один писк): тот же viewer/bootbeep.h, что на PSP, синтез кусками по BOOT_SND_CHUNK в память на
// Маке, замер по самим сэмплам (голоса по отдельности — маской BootSnd.mask, тот же генератор шума).
//   1) щелчок: пик в первые 5 мс, к 25–33 мс спад ≥ 20 дБ, широкий спектр (переходов через ноль > 1/8 сэмплов за 6 мс)
//   2) кулер: RMS окон по 100 мс в 0,1–1,0 с не убывает (допуск 5 %), прирост ≥ 12 дБ; тон лопастей на 1,0 с выше, чем на 0,3 с
//   3) бип: начало BOOT_BEEP_AT ±10 мс, 1000 Гц ±2 %, звучит 60–200 мс, пик ≤ 4000, 3-я гармоника / 1-я < 0,2 (мягче меандра)
//   4) общая длина ≤ 4320 мс (ход заставки), в конце тишина, без обрезки, пик ≤ 9000
//   5) кусок кратен 64 и ≤ 65472; кусками побайтно = одним куском (поток без швов); START — затухание за один кусок без скачка
//   6) скорость: кусок синтезируется в 50+ раз быстрее реального времени (запас на PSP 333 МГц)
// Красное: -DBOOT_SND_CLICK=0 (1) | -DBOOT_SND_FAN_TAU=0 (2) | -DBOOT_BEEP_LP=0.55f (3) | -DBOOT_SND_CHUNK=1000 (5) -> FAIL.
// Пишет build/bootsnd_A.wav, _B.wav, _C.wav (громкий кулер / тихий / бип в конце проверок) — послушать.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <time.h>
#include "bootbeep.h"
#define R BOOT_BEEP_RATE
#define NMAX (BOOT_SND_N + 2 * BOOT_SND_CHUNK)
static short all[NMAX], part[NMAX];
static int render(short *b, int variant, int mask, int chunk, int stopAt) {   // вернуть сэмплов партитуры
  BootSnd s; bootSndInit(&s, variant); s.mask = mask; int tot = 0, k, off = 0;
  memset(b, 0, sizeof all);
  while (off + chunk <= NMAX) { if (stopAt >= 0 && off >= stopAt) bootSndStop(&s);
    if ((k = bootSndFill(&s, b + off, chunk)) <= 0) break; tot += k; off += chunk; }
  return tot;
}
static void wav(const char *fn, const short *b, int n) {
  FILE *f = fopen(fn, "wb"); if (!f) return;
  unsigned bytes = n * 2, r = R, br = r * 2, v; unsigned short s;
  fwrite("RIFF", 1, 4, f); v = 36 + bytes; fwrite(&v, 4, 1, f); fwrite("WAVEfmt ", 1, 8, f); v = 16; fwrite(&v, 4, 1, f);
  s = 1; fwrite(&s, 2, 1, f); fwrite(&s, 2, 1, f); fwrite(&r, 4, 1, f); fwrite(&br, 4, 1, f); s = 2; fwrite(&s, 2, 1, f); s = 16; fwrite(&s, 2, 1, f);
  fwrite("data", 1, 4, f); fwrite(&bytes, 4, 1, f); fwrite(b, 2, n, f); fclose(f);
}
static double rms(const short *b, int a, int z) { double e = 0; for (int i = a; i < z; i++) e += (double)b[i] * b[i]; return sqrt(e / (z - a)); }
static int peakOf(const short *b, int a, int z) { int p = 0; for (int i = a; i < z; i++) if (abs(b[i]) > p) p = abs(b[i]); return p; }
static double goertzel(const short *b, int a, int z, double hz) {
  double w = 2 * M_PI * hz / R, c = 2 * cos(w), s1 = 0, s2 = 0;
  for (int i = a; i < z; i++) { double s0 = b[i] + c * s1 - s2; s2 = s1; s1 = s0; }
  return sqrt(s1 * s1 + s2 * s2 - c * s1 * s2);
}
static double zcHz(const short *b, int a, int z) {   // частота по переходам вверх через ноль
  int up = 0, c0 = -1, c1 = -1; for (int i = a + 1; i < z; i++) if (b[i - 1] <= 0 && b[i] > 0) { if (c0 < 0) c0 = i; c1 = i; up++; }
  return up > 1 ? (up - 1) * (double)R / (c1 - c0) : 0;
}
int main(void) {
  int fails = 0, ms = 1;
  // 5) поток без швов
  int okChunk = BOOT_SND_CHUNK % 64 == 0 && BOOT_SND_CHUNK <= 65472;
  int t1 = render(all, 0, BOOT_SND_M_ALL, NMAX - NMAX % 64, -1); (void)t1;
  int t2 = render(part, 0, BOOT_SND_M_ALL, BOOT_SND_CHUNK, -1);
  int seam = memcmp(all, part, BOOT_SND_N * 2) != 0;
  printf("кусок %d сэмплов (кратно 64): %s; кусками = одним куском: %s\n", BOOT_SND_CHUNK, okChunk ? "да" : "нет", seam ? "НЕТ" : "да");
  fails += !okChunk + seam;
  // 4) длина, тишина в конце, пик
  int peak = peakOf(part, 0, NMAX), clip = 0, last = -1;
  for (int i = 0; i < NMAX; i++) { clip += abs(part[i]) >= 32767; if (abs(part[i]) > 16) last = i; }
  double lenMs = (last + 1) * 1000.0 / R; int okLen = t2 <= R / 1000 * 4320 && lenMs <= 4320 && peak <= 9000 && !clip && t2 > 0;
  printf("звучит %.0f мс (≤ 4320, ход заставки), сэмплов партитуры %d, пик %d (≤ 9000), обрезано %d: %s\n", lenMs, t2, peak, clip, okLen ? "да" : "нет");
  fails += !okLen;
  // 1) щелчок
  static short c[NMAX]; render(c, 0, BOOT_SND_M_CLICK, BOOT_SND_CHUNK, -1);
  int p5 = peakOf(c, 0, R * 5 / 1000), p40 = peakOf(c, 0, R * 40 / 1000), pLate = peakOf(c, R * 25 / 1000, R * 33 / 1000), zc = 0;
  for (int i = 1; i < R * 6 / 1000; i++) zc += (c[i - 1] < 0) != (c[i] < 0);
  double dec = pLate > 0 ? 20 * log10((double)p5 / pLate) : 99; double zr = (double)zc / (R * 6 / 1000);
  int okClick = p5 > 1000 && p5 == p40 && dec >= 20 && zr > 1.0 / 8;
  printf("щелчок: пик %d в первые 5 мс, спад к 25–33 мс %.1f дБ (≥ 20), переходов через ноль %.2f на сэмпл (> 0,125): %s\n", p5, dec, zr, okClick ? "да" : "нет");
  fails += !okClick;
  // 2) кулер
  static short f[NMAX], bl[NMAX]; render(f, 0, BOOT_SND_M_FAN | BOOT_SND_M_BLADE, BOOT_SND_CHUNK, -1); render(bl, 0, BOOT_SND_M_BLADE, BOOT_SND_CHUNK, -1);
  int mono = 1; double w0 = rms(f, R / 10, R / 5), wl = w0, wk = w0;
  for (int k = 2; k < 10; k++) { wk = rms(f, R * k / 10, R * (k + 1) / 10); if (wk < wl * .95) mono = 0; wl = wk; }
  double gain = 20 * log10(wk / (w0 > 1 ? w0 : 1)), hz03 = zcHz(bl, R * 3 / 10 - R / 20, R * 3 / 10 + R / 20), hz10 = zcHz(bl, R - R / 20, R + R / 20);
  double fanDb = 20 * log10(rms(f, R * 2, R * 3) / 32767);
  int okFan = mono && gain >= 12 && hz10 > hz03 * 1.05;
  printf("кулер: RMS окон 0,1–1,0 с не убывает: %s, прирост %.1f дБ (≥ 12), на 2–3 с %.1f дБFS; лопасти %.0f Гц на 0,3 с -> %.0f Гц на 1,0 с: %s\n",
         mono ? "да" : "нет", gain, fanDb, hz03, hz10, okFan ? "да" : "нет");
  fails += !okFan;
  // 3) бип (все варианты)
  for (int v = 0; v < 3; v++) {
    static short b[NMAX]; render(b, v, BOOT_SND_M_BEEP, BOOT_SND_CHUNK, -1);
    int pk = peakOf(b, 0, NMAX), first = -1, lastb = -1; for (int i = 0; i < NMAX; i++) if (abs(b[i]) > pk / 10) { if (first < 0) first = i; lastb = i; }
    double at = first * 1000.0 / R, dur = (lastb - first + 1) * 1000.0 / R, hz = zcHz(b, first, lastb);
    int mid0 = first + R / 100, mid1 = mid0 + R / 20;   // 50 мс середины бипа
    double h3 = goertzel(b, mid0, mid1, 3 * BOOT_BEEP_HZ) / goertzel(b, mid0, mid1, BOOT_BEEP_HZ);
    int want = bootSndBeepMs(v);
    int okBeep = fabs(at - want) <= 10 && fabs(hz - 1000) <= 20 && dur >= 60 && dur <= 200 && pk <= 4000 && h3 < .2;
    printf("бип %c: начало %.0f мс (ждём %d ±10), %.1f Гц, звучит %.0f мс, пик %d (≤ 4000), 3-я/1-я гармоника %.2f (< 0,2): %s\n",
           bootSndName[v], at, want, hz, dur, pk, h3, okBeep ? "да" : "нет");
    fails += !okBeep;
  }
  // 5б) START: затухание за один кусок, после — тишина, без скачка
  { static short s[NMAX]; int stopAt = R * 2 / BOOT_SND_CHUNK * BOOT_SND_CHUNK; render(s, 0, BOOT_SND_M_ALL, BOOT_SND_CHUNK, stopAt);
    int after = peakOf(s, stopAt + BOOT_SND_CHUNK, NMAX), same = !memcmp(s, part, stopAt * 2), jump = 0, jumpN = 0;
    for (int i = stopAt; i < stopAt + BOOT_SND_CHUNK + 4; i++) { int d = abs(s[i] - s[i - 1]); if (d > jump) jump = d; }
    for (int i = R; i < 2 * R - 1; i++) { int d = abs(part[i] - part[i - 1]); if (d > jumpN) jumpN = d; }
    int okStop = after == 0 && same && jump <= jumpN;
    printf("START на 2 с: до остановки то же: %s, скачок при затухании %d (обычный %d), после куска тишина: %s -> %s\n",
           same ? "да" : "нет", jump, jumpN, after ? "нет" : "да", okStop ? "да" : "нет");
    fails += !okStop; }
  // 6) скорость
  { BootSnd s; bootSndInit(&s, 0); static short b[BOOT_SND_CHUNK]; int chunks = 0; clock_t c0 = clock();
    for (int rep = 0; rep < 20; rep++) { bootSndInit(&s, 0); while (bootSndFill(&s, b, BOOT_SND_CHUNK) > 0) chunks++; }
    double us = (double)(clock() - c0) / CLOCKS_PER_SEC * 1e6 / (chunks ? chunks : 1), real = BOOT_SND_CHUNK * 1e6 / R;
    int okSpeed = us * 50 < real;
    printf("скорость: кусок %.0f мкс при длительности %.0f мкс (в %.0f раз быстрее, нужно ≥ 50): %s\n", us, real, real / (us > 0 ? us : 1), okSpeed ? "да" : "нет");
    fails += !okSpeed; }
  // файлы для Роба
  for (int v = 0; v < 3; v++) { static short b[NMAX]; char fn[64]; render(b, v, BOOT_SND_M_ALL, BOOT_SND_CHUNK, -1);
    snprintf(fn, sizeof fn, "build/bootsnd_%c.wav", bootSndName[v]); wav(fn, b, BOOT_SND_N); }
  printf("файлы build/bootsnd_A.wav (громкий кулер), _B.wav (тихий), _C.wav (бип в конце проверок); в игре %c\n", bootSndName[BOOT_SND_VARIANT]);
  (void)ms;
  printf("RESULT: %s (%d failures)\n", fails ? "FAIL" : "OK", fails);
  return fails != 0;
}
