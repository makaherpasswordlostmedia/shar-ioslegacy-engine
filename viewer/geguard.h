#ifndef GEGUARD_H
#define GEGUARD_H
// Правки 259/252 (03.10): видеочип настоящей PSP встаёт целиком (вместе с ним вся приставка, HOME не отвечает, сторож молчит)
// не только на неверном адресе (geAddrOk, правка 103), но и на матрице с NaN/бесконечностью: кадр с FOV 0 и взглядом строго
// вниз (тур, старт миссии из комнаты) — эмулятор такие треугольники отбрасывает и молчит. Все матрицы, уходящие в GE из нашего
// кода, проходят проверку: число вне ±2^24 (NaN, бесконечность, мусор) — вместо матрицы «всё в точку» (кусок не виден),
// счётчик geGuardHits — в чёрный ящик (поле gg). Камера кадра (pspgum) проверяется на входе в main.c (camGuard).
// Подключается ко всем исходникам движка ключом -include (CMakeLists.txt); прототипы — из pspgu.h под новыми именами
extern volatile unsigned geGuardHits;
int geFinite(float a);                    // не NaN, не бесконечность, |a| < 2^24 — по битам (не зависит от флагов оптимизации)
int geMatOk(const float *f, int n);
#if !defined(GEGUARD_IMPL) && !defined(GEGUARD_OLD)
#define sceGuSetMatrix geSetMatrixSafe
#define sceGuBoneMatrix geBoneMatrixSafe
#endif
#endif
