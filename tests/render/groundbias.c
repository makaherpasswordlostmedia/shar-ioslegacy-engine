// Множитель наклона мипа земли: разбор файла groundbias и применение только к помеченным текстурам; красный контроль -DGROUNDBIAS_BREAK=1
#include <stdio.h>
#include <math.h>
#include "groundbias.h"
static int bad;
#define CK(c, m) do { if (!(c)) { printf("FAIL %s\n", m); bad++; } } while (0)
int main(void) {
  CK(fabsf(groundBiasParse("1.5") - 1.5f) < 1e-6f, "1.5");
  CK(fabsf(groundBiasParse("2.0\n") - 2.f) < 1e-6f, "2.0 с переводом строки");
  CK(fabsf(groundBiasParse("0.25") - .25f) < 1e-6f && fabsf(groundBiasParse("4") - 4.f) < 1e-6f, "границы 0,25 и 4");
  CK(groundBiasParse("0.1") == 1.f && groundBiasParse("5") == 1.f, "вне предела: 1");
  CK(groundBiasParse("") == 1.f && groundBiasParse(0) == 1.f && groundBiasParse("abc") == 1.f && groundBiasParse("-2") == 1.f, "пусто, мусор, минус: 1");
  float s = 0.8f;
#ifdef GROUNDBIAS_BREAK
  CK(groundSlope(s, 0, 2.f, 0) == s, "не земля не меняется");
#else
  CK(groundSlope(s, 1, 2.f, 0) == 1.6f, "земля x2");
  CK(groundSlope(s, 0, 2.f, 0) == s, "не земля не меняется");
  CK(groundSlope(s, 1, 2.f, 1) == s, "GROUNDBIAS_RT_OLD=1: земля не меняется");
  CK(groundSlope(s, 1, 1.f, 0) == s, "множитель 1: как есть");
#endif
#ifdef GROUNDBIAS_BREAK
  CK(groundSlope(s, 1, 2.f, 0) == 1.6f && 0, "красный контроль: проверка обязана упасть");
#endif
  puts(bad ? "FAIL" : "PASS"); return bad ? 1 : 0;
}
