// Проверка писка заставки (Роб 28.09 вечер: «звук как на старых компах — твитер пищал, именно писк»): тот же
// viewer/bootbeep.h, что на PSP, синтез в память на Маке, замер по самим сэмплам.
//   1) частота по переходам через ноль в пределах 1–2 кГц (писк, не гул и не свист) и совпадает с BOOT_BEEP_HZ ±2%
//   2) форма — прямоугольник, как у пищалки ПК: доля положительных сэмплов 45–55%, «плато» (|v| > 80% пика) >= 60% тона
//   3) длительность звучания (огибающая > 10% пика) 60–300 мс — короткий писк, а не гудок; дальше тишина до конца буфера
//   4) громкость умеренная: пик 2000..9000 из 32767 (не шёпот и не в уши), без обрезки
//   5) буфер кратен 64 (требование sceAudioChReserve), писк целиком в буфере
// Красное: -DBOOT_BEEP_HZ=440 (гул) | -DBOOT_BEEP_AMP=30000 (громко) | -DBOOT_BEEP_MS=900 (гудок) -> FAIL.
// Пишет build/bootbeep.wav — послушать.
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "bootbeep.h"
static short buf[BOOT_BEEP_N];
static void wav(const char *fn) {
  FILE *f = fopen(fn, "wb"); if (!f) return;
  unsigned n = sizeof buf, r = BOOT_BEEP_RATE, br = r * 2, v; unsigned short s;
  fwrite("RIFF", 1, 4, f); v = 36 + n; fwrite(&v, 4, 1, f); fwrite("WAVEfmt ", 1, 8, f); v = 16; fwrite(&v, 4, 1, f);
  s = 1; fwrite(&s, 2, 1, f); fwrite(&s, 2, 1, f); fwrite(&r, 4, 1, f); fwrite(&br, 4, 1, f); s = 2; fwrite(&s, 2, 1, f); s = 16; fwrite(&s, 2, 1, f);
  fwrite("data", 1, 4, f); fwrite(&n, 4, 1, f); fwrite(buf, 1, n, f); fclose(f);
}
int main(void) {
  int tone = bootBeepSynth(buf, BOOT_BEEP_N), peak = 0, clip = 0;
  for (int i = 0; i < BOOT_BEEP_N; i++) { int a = abs(buf[i]); if (a > peak) peak = a; clip += a >= 32767; }
  int first = -1, last = -1; for (int i = 0; i < BOOT_BEEP_N; i++) if (abs(buf[i]) > peak / 10) { if (first < 0) first = i; last = i; }
  float ms = (last - first + 1) * 1000.f / BOOT_BEEP_RATE;
  int up = 0, pos = 0, plat = 0, n = 0, c0 = -1, c1 = -1;
  for (int i = first + 1; i <= last; i++) {
    n++; pos += buf[i] > 0; plat += abs(buf[i]) > peak * 8 / 10;
    if (buf[i - 1] <= 0 && buf[i] > 0) { if (c0 < 0) c0 = i; c1 = i; up++; }
  }
  float hz = up > 1 ? (up - 1) * (float)BOOT_BEEP_RATE / (c1 - c0) : 0.f, duty = n ? (float)pos / n : 0.f, flat = n ? (float)plat / n : 0.f;
  int tail = 0; for (int i = last + BOOT_BEEP_RATE / 500; i < BOOT_BEEP_N; i++) tail += abs(buf[i]) > 16;   // через 2 мс после писка
  int okHz = hz >= 1000.f * .98f && hz <= 2000.f * 1.02f && fabsf(hz - BOOT_BEEP_HZ) <= BOOT_BEEP_HZ * .02f;
  int okForm = duty >= .45f && duty <= .55f && flat >= .6f;
  int okLen = ms >= 60.f && ms <= 300.f && tail == 0 && tone < BOOT_BEEP_N;
  int okAmp = peak >= 2000 && peak <= 9000 && clip == 0;
  int okBuf = BOOT_BEEP_N % 64 == 0 && BOOT_BEEP_N <= 65472;
  wav("build/bootbeep.wav");
  printf("частота %.1f Гц (задано %d, окно 1000–2000): %s\n", hz, BOOT_BEEP_HZ, okHz ? "да" : "нет");
  printf("прямоугольник: положительных %.1f%%, плато %.1f%%: %s\n", duty * 100, flat * 100, okForm ? "да" : "нет");
  printf("звучит %.1f мс (60–300), после — тишина (%d громких сэмплов в хвосте): %s\n", ms, tail, okLen ? "да" : "нет");
  printf("пик %d из 32767 (%.1f дБ), обрезано %d: %s\n", peak, 20 * log10f(peak / 32767.f), clip, okAmp ? "да" : "нет");
  printf("буфер %d сэмплов (кратно 64): %s; файл build/bootbeep.wav\n", BOOT_BEEP_N, okBuf ? "да" : "нет");
  int fails = !okHz + !okForm + !okLen + !okAmp + !okBuf;
  printf("RESULT: %s (%d failures)\n", fails ? "FAIL" : "OK", fails);
  return fails != 0;
}
