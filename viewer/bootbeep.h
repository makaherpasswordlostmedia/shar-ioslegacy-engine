// Звук включения на заставке GONE Makers (правка Роба 128, 01.10: «звук не пищащий, а как будто нажали кнопку, включился
// кулер и пикнул старый компьютер 90-х с системным блоком»; было — один писк, Роб 28.09). Своей заставки у оригинала нет —
// вся партитура здесь правило порта, синтез без чужих записей:
//   1) щелчок кнопки питания в 0 мс: всплеск шума (разность соседних сэмплов — «клац» пластика, τ ≈ 1,5 мс) и глухой удар
//      корпуса 140 Гц (τ ≈ 12 мс); через 35 мс тихий щелчок реле блока питания (−12 дБ);
//   2) кулер с 40 мс: белый шум через два однополюсных НЧ, срез растёт 300 Гц -> 2,5 кГц вместе с громкостью
//      1 − exp(−t/τ) — раскрутка; тон лопастей 290·(1 − exp(−t/0,5 с)) Гц (80 мм кулер ~2500 об/мин × 7 лопастей) и его
//      2-я гармоника — на динамиках PSP низ почти не слышен, вытягивают гармоники и шум;
//   3) бип PC-спикера POST: таймер 8253 (1 193 182 Гц) с делителем 1193 = 1000 Гц меандр 120 мс, края 4 мс, двухполюсный НЧ
//      ~2,2 кГц (мягче прежнего писка: меньше верхних гармоник), пик ≈ 3300 (−20 дБ); по времени — как у настоящего POST,
//      после счёта памяти (кадр BSQ_MEM1 = 64 -> 1024 мс) или в конце проверок (вариант C, кадр BSQ_RULE = 104);
//   4) кулер держится и уходит в ноль за последние 600 мс; всего BOOT_SND_MS ≤ длины хода заставки (270 кадров = 4320 мс).
// Поток: всё состояние синтеза в BootSnd (номер сэмпла, фазы, фильтры, генератор шума), bootSndFill отдаёт следующий
// кусок любой длины — кусками по 1024 побайтно то же, что одним куском (без швов). Два буфера по 1024 сэмпла в
// viewer/bootscreen.h вместо прежних 2 × 16 КБ. Остановка (START) — затухание за один кусок. Три варианта (Роб выберет на
// слух, build/bootsnd_A/B/C.wav из tests/bootsnd): A — громкий кулер башни, B — тихий, C — бип в конце проверок.
// Чистый C без PSP: общий для viewer/bootscreen.h и проверки на Маке (tests/bootsnd).
#ifndef BOOTBEEP_H
#define BOOTBEEP_H
#include <math.h>

#define BOOT_BEEP_RATE 44100
#define BOOT_BEEP_PIT 1193182             // тактовая таймера 8253 в ПК
#ifndef BOOT_BEEP_HZ
#define BOOT_BEEP_HZ (BOOT_BEEP_PIT / 1193)   // 1000 Гц
#endif
#ifndef BOOT_BEEP_MS
#define BOOT_BEEP_MS 120
#endif
#ifndef BOOT_BEEP_AMP
#define BOOT_BEEP_AMP 3300                // из 32767 (−20 дБ; прежний писк 5800)
#endif
#define BOOT_BEEP_EDGE (BOOT_BEEP_RATE * 4 / 1000)   // края 4 мс
#ifndef BOOT_BEEP_LP
#define BOOT_BEEP_LP 0.269f               // коэффициент каждого из двух полюсов НЧ: 1 − exp(−2π·2200/44100); tests: 0.55 (прежний) -> FAIL
#endif
#ifndef BOOT_SND_MS
#define BOOT_SND_MS 4000                  // вся партитура; ход заставки 4320 мс
#endif
#define BOOT_SND_N (BOOT_BEEP_RATE / 1000 * BOOT_SND_MS)
#ifndef BOOT_SND_CHUNK
#define BOOT_SND_CHUNK 1024               // кусок вывода, сэмплов (кратно 64 — требование sceAudioChReserve); tests: 1000 -> FAIL
#endif
#ifndef BOOT_SND_CLICK
#define BOOT_SND_CLICK 7000.f             // пик щелчка кнопки; tests: 0 -> FAIL
#endif
#define BOOT_SND_RELAY_MS 35
#define BOOT_SND_FAN_MS 40
#ifndef BOOT_SND_FAN_TAU
#define BOOT_SND_FAN_TAU 0.45f            // с, раскрутка кулера; tests: 0 (сразу на полную) -> FAIL
#endif
#define BOOT_SND_FADE_MS 600
#define BOOT_SND_BLADE_HZ 290.f
#ifndef BOOT_SND_VARIANT
#define BOOT_SND_VARIANT 0                // по умолчанию в игре: A (громкий кулер); Роб выбирает на слух
#endif
// маска голосов (для замеров по отдельности в tests/bootsnd)
enum { BOOT_SND_M_CLICK = 1, BOOT_SND_M_FAN = 2, BOOT_SND_M_BLADE = 4, BOOT_SND_M_BEEP = 8, BOOT_SND_M_ALL = 15 };

typedef struct {
  int i, n, mask, beepAt, stopAt;     // номер сэмпла, длина, голоса, начало бипа, остановка (-1 — нет)
  float fanGain, bladeGain;           // громкость шума кулера и тона лопастей
  float phBlade, phBeep, lp1, lp2, b1, b2, prevNoise;
  unsigned rng;
} BootSnd;
static const char bootSndName[3] = {'A', 'B', 'C'};
static int bootSndBeepMs(int variant) { return variant == 2 ? 1664 : 1024; }   // кадр 104 (конец проверок) / 64 (MEMORY OK)
static void bootSndInit(BootSnd *s, int variant) {
  static const float fan[3] = {2200.f, 900.f, 1500.f}, blade[3] = {600.f, 280.f, 450.f};   // A громкий / B тихий / C средний
  if (variant < 0 || variant > 2) variant = 0;
  s->i = 0; s->n = BOOT_SND_N; s->mask = BOOT_SND_M_ALL; s->stopAt = -1;
  s->beepAt = BOOT_BEEP_RATE / 1000 * bootSndBeepMs(variant);
  s->fanGain = fan[variant]; s->bladeGain = blade[variant];
  s->phBlade = s->phBeep = s->lp1 = s->lp2 = s->b1 = s->b2 = s->prevNoise = 0.f; s->rng = 0x2545F491u;
}
static void bootSndStop(BootSnd *s) { if (s->stopAt < 0) s->stopAt = s->i; }   // затухание за один кусок
static float bootSndNoise(BootSnd *s) {   // xorshift32 -> [-1, 1)
  unsigned x = s->rng; x ^= x << 13; x ^= x >> 17; x ^= x << 5; s->rng = x;
  return (float)(int)x * (1.f / 2147483648.f);
}
static float bootSndSin(float ph) {   // ph в [0, 1): быстрый синус (парабола с уточнением), без sinf на каждый сэмпл
  float x = ph < .5f ? ph * 4.f - 1.f : 3.f - ph * 4.f;    // треугольник -1..1
  x = x * (1.5f - .5f * x * x);                             // сглаживание к синусу
  return x;
}
// следующий кусок out[0..n): вернуть число сэмплов партитуры в нём (0 — звук кончился); хвост куска дополняется тишиной
static int bootSndFill(BootSnd *s, short *out, int n) {
  int made = 0;
  for (int j = 0; j < n; j++, s->i++) {
    int i = s->i; float v = 0.f;
    if (i >= s->n || (s->stopAt >= 0 && i >= s->stopAt + BOOT_SND_CHUNK)) { out[j] = 0; continue; }
    made++;
    float t = (float)i / BOOT_BEEP_RATE, nz = bootSndNoise(s);
    // 1) щелчок кнопки, удар корпуса и реле
    if (i < BOOT_BEEP_RATE / 20 && (s->mask & BOOT_SND_M_CLICK)) {
      float d = nz - s->prevNoise, tr = t - BOOT_SND_RELAY_MS * .001f;
      v += BOOT_SND_CLICK * .5f * d * expf(-t / .0015f);
      if (tr >= 0.f) v += BOOT_SND_CLICK * .125f * d * expf(-tr / .001f);
      v += BOOT_SND_CLICK * .35f * bootSndSin(fmodf(140.f * t, 1.f)) * expf(-t / .012f) * (t < .002f ? t / .002f : 1.f);
    }
    s->prevNoise = nz;
    // 2) кулер: раскрутка, держится, уходит в ноль за BOOT_SND_FADE_MS
    float tf = t - BOOT_SND_FAN_MS * .001f;
    if (tf >= 0.f) {
      float e = BOOT_SND_FAN_TAU > 0.f ? 1.f - expf(-tf / BOOT_SND_FAN_TAU) : 1.f;
      int left = s->n - i, fade = BOOT_BEEP_RATE / 1000 * BOOT_SND_FADE_MS;
      float g = left < fade ? (float)left / fade : 1.f; g *= g;
      float w = 6.2831853f * (300.f + 2200.f * e) / BOOT_BEEP_RATE, k = w / (1.f + w);
      s->lp1 += (nz - s->lp1) * k; s->lp2 += (s->lp1 - s->lp2) * k;
      if (s->mask & BOOT_SND_M_FAN) v += s->fanGain * 2.2f * e * g * s->lp2;
      float fb = BOOT_SND_BLADE_HZ * (1.f - expf(-tf / .5f));
      s->phBlade += fb / BOOT_BEEP_RATE; if (s->phBlade >= 1.f) s->phBlade -= 1.f;
      float ph2 = s->phBlade * 2.f; if (ph2 >= 1.f) ph2 -= 1.f;
      if (s->mask & BOOT_SND_M_BLADE) v += s->bladeGain * e * g * (bootSndSin(s->phBlade) + .5f * bootSndSin(ph2));
    }
    // 3) бип POST: меандр 1000 Гц, края 4 мс, два полюса НЧ
    float sq = 0.f; int ib = i - s->beepAt, tone = BOOT_BEEP_RATE * BOOT_BEEP_MS / 1000;
    if (ib >= 0 && ib < tone) {
      s->phBeep += (float)BOOT_BEEP_HZ / BOOT_BEEP_RATE; if (s->phBeep >= 1.f) s->phBeep -= 1.f;
      float env = ib < BOOT_BEEP_EDGE ? (float)ib / BOOT_BEEP_EDGE : tone - ib < BOOT_BEEP_EDGE ? (float)(tone - ib) / BOOT_BEEP_EDGE : 1.f;
      sq = (s->phBeep < .5f ? 1.f : -1.f) * env;
    }
    s->b1 += (sq - s->b1) * BOOT_BEEP_LP; s->b2 += (s->b1 - s->b2) * BOOT_BEEP_LP;
    if (s->mask & BOOT_SND_M_BEEP) v += s->b2 * BOOT_BEEP_AMP * 1.05f;
    // остановка: линейное затухание за один кусок
    if (s->stopAt >= 0) v *= 1.f - (float)(i - s->stopAt) / BOOT_SND_CHUNK;
    int q = (int)v; if (q > 32767) q = 32767; if (q < -32768) q = -32768;
    out[j] = (short)q;
  }
  return made;
}
#endif
