// №912: матрица оболочки контура машины M = m · A, где A — масштаб по диагонали и сдвиг в четвёртом столбце (carToonHull, main_render.h). Прежняя запись — полное умножение 4×4 (64 умножения),
// новая — по ненулевым слагаемым (12 + 16 умножений, слагаемые в том же порядке): числа равны (отличие — только знак нуля). Чистая функция, её же гоняет tests/toon/hull912.sh
#pragma once
static inline void hullMatFull(const float *m, const float *A, float *M) {   // как было: столбцы подряд, как ScePspFMatrix4
  for (int c = 0; c < 4; c++) for (int r = 0; r < 4; r++) { float v = 0.f; for (int k = 0; k < 4; k++) v += m[k * 4 + r] * A[c * 4 + k]; M[c * 4 + r] = v; }
}
static inline void hullMatDiag(const float *m, const float *sc, const float *tr, float *M) {   // sc — масштабы по осям (A[0], A[5], A[10]), tr — сдвиг (A[12..14]); A[15] = 1
  for (int c = 0; c < 3; c++) for (int r = 0; r < 4; r++) M[c * 4 + r] = m[c * 4 + r] * sc[c];
  for (int r = 0; r < 4; r++) M[12 + r] = (((0.f + m[r] * tr[0]) + m[4 + r] * tr[1]) + m[8 + r] * tr[2]) + m[12 + r];
}
