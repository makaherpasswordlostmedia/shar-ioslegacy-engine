// Правка 410: гейт расчёта доли потока BBCPU (viewer/bbcpu.h) на Маке. Последовательности runClocks (мкс):
//   norm  — поток 5 % секунды 30 секунд подряд: доля 5 каждую секунду (старый и новый расчёт совпадают);
//   T3    — смена уровня: новый поток с тем же UID, runClocks меньше прежней базы на 2,90 с (audio_mix) и 0,60 с (audio_io), dt = 7 906 936
//           (как T3 smoke.txt:5024): прежний расчёт обязан дать ровно 815353985 и 815354014, новый — 0 и событие «новый поток»;
//   over  — доля 103 % (часы секунды и runClocks не в такт): новый — 100 и событие «срез»
// Вывод: строки «имя pct ev», сверяет tests/me/run.py (step_mac_bbcpu). cc -O2 -I viewer tests/me/bbcpu_host.c [-DBBCPU_OLD=1]
#include <stdio.h>
#include "bbcpu.h"
int main(void) {
  unsigned long long b = 0; unsigned ev = 0, bad = 0, p;
  for (int s = 0; s <= 30; s++) { ev = 0; p = bbPctStep(&b, 1000000ull + 50000ull * s, 1000000, &ev); if (s && p != 5) bad++; if (ev) bad++; }
  printf("norm %u %u\n", bad, ev);
  unsigned long long bm = 40000000ull, bi = 7000000ull;   // старые базы: audio_mix и audio_io L4
  ev = 0; p = bbPctStep(&bm, bm - 2900000ull, 7906936u, &ev); printf("T3mix %u %u\n", p, ev);
  ev = 0; p = bbPctStep(&bi, bi - 600000ull, 7906936u, &ev); printf("T3io %u %u\n", p, ev);
  ev = 0; p = bbPctStep(&bm, bm + 40000ull, 1000000u, &ev); printf("after %u %u\n", p, ev);   // следующая секунда нового потока: 4 %
  ev = 0; b = 5000000ull; p = bbPctStep(&b, b + 1030000ull, 1000000u, &ev); printf("over %u %u\n", p, ev);
  return 0;
}
