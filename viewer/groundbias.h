// Множитель наклона мипа «земли» в движке (см. main_render.h texSlope): чистые функции, чтобы проверять на хосте (tests/render/groundbias.c).
#ifndef SHAR_GROUNDBIAS_H
#define SHAR_GROUNDBIAS_H
#include <stdlib.h>
// файл `groundbias` рядом с EBOOT: десятичное число 0,25 до 4 (точка), иначе 1 (как без файла)
static inline float groundBiasParse(const char *s) {
  if (!s || !*s) return 1.f;
  char *e = 0; float k = (float)strtod(s, &e);
  if (e == s || !(k >= .25f && k <= 4.f)) return 1.f;
  return k;
}
// наклон текстуры для GE: помеченная землёй умножается, остальные и режим OLD не меняются
static inline float groundSlope(float slope, int ground, float mul, int old) { return (ground && !old) ? slope * mul : slope; }
#endif
