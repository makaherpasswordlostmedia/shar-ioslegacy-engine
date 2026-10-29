// clipguard.h — слово Роба 15.10 (TEST20b: «проваливаешься в текстуры машин, это везде»): ближняя плоскость кадра после camsafe бывает 0,05–0,1 м, а в сценах без следования
// (разговор, ролик) camNearNow = 0: объект в 0,1–0,3 м от глаза рисуется целиком, и экран залит его текстурой. Общее правило списков отрисовки подвижных и пропов (машины трафика и
// миссии, пешеходы, персонажи миссий, пропы): объект не рисуется, если глаз ближе CLIP_MARGIN (0,3 м) к его коробке (внутри коробки тоже), а также прежние пороги №502/№602 (ближняя
// плоскость + запас) остаются. Машину игрока не трогает (её камера не входит: camsafe). Камеру не меняет. CAM_CLIP_GUARD_OLD=1 — прежнее (только camnear.h).
// Счётчик для проверки: clipSeen — сколько проверок за кадр видели объект ближе CLIP_MARGIN (для гейта «кадров камера в кузове»), clipHid — сколько скрыто этим правилом.
#ifndef CLIPGUARD_H
#define CLIPGUARD_H
#include "camnear.h"
#include "car.h"
#ifndef CAM_CLIP_GUARD_OLD
#define CAM_CLIP_GUARD_OLD 0
#endif
#define CLIP_MARGIN 0.3f
extern unsigned clipSeen, clipDrawnClose, clipHid;
// №658/слово Роба «сначала оригинал»: у PS2 малые предметы (ящик, гидрант, урна, знак) и прохожие у камеры не прячутся — их режет ближняя плоскость. «flag clipsmall 1» (clipSmallOn): для пропов,
// стейтпропов и персонажей-прохожих правила clip guard (0,3 м к ящику и «по взгляду 1,8 м») выключены, остаются прежние пороги №502/№602 (oldHide); машины и крупное — как было. По умолчанию 0.
extern int clipSmallOn;   // за секунду (msn_view.c): видели близко / нарисовано ближе порога (прежнее поведение) / скрыто правилом
// Идея Камеры (docs/handoff/clip_guard_draft, 15.10, взята): борт машины на луче ВПЕРЁД из глаза ближе CLIP_AHEAD (1,8 м) заполняет кадр «в лицо», хотя ближняя плоскость (после
// camsafe 0,35 м) его ещё не режет и расстояние до ящика больше 0,3 м (трафик проезжал сквозь камеру пешком, L3 H8-1, фото Роба TEST19_машина_сквозь_камеру_L3_t210). Только у следящей
// камеры (camNearNow > 0): кинокамеры разговора/ролика подобраны данными. camFwdN — нормированный взгляд кадра (main_loop.h), определён в msn_view.c.
extern float camFwdN[3];
#define CLIP_AHEAD 1.8f
static inline int clipAheadBox(float ex, float ey, float ez, const float b[6]) {
  if (camNearNow <= 0.f) return 0;
  const float o[3] = {ex, ey, ez}, *f = camFwdN; float t0 = 0.f, t1 = CLIP_AHEAD;
  for (int k = 0; k < 3; k++) {
    if (fabsf(f[k]) < 1e-5f) { if (o[k] < b[k] || o[k] > b[k + 3]) return 0; continue; }
    float a = (b[k] - o[k]) / f[k], c = (b[k + 3] - o[k]) / f[k]; if (a > c) { float s = a; a = c; c = s; }
    if (a > t0) t0 = a; if (c < t1) t1 = c; if (t0 > t1) return 0;
  }
  return 1;
}
static inline int clipAheadSphere(float ex, float ey, float ez, float x, float y, float z, float rad) {
  if (camNearNow <= 0.f) return 0;
  float dx = x - ex, dy = y - ey, dz = z - ez, t = dx * camFwdN[0] + dy * camFwdN[1] + dz * camFwdN[2];
  if (t < -rad || t > CLIP_AHEAD + rad) return 0;
  float d2 = dx * dx + dy * dy + dz * dz - t * t; return d2 < rad * rad;
}
static inline float clipThr(void) { return fmaxf(CLIP_MARGIN, camNearNow + .05f); }
static inline int clipCount(float d2, int oldHide) {   // d2 — квадрат расстояния до объекта; oldHide — решение прежних правил
  int close = d2 < CLIP_MARGIN * CLIP_MARGIN;
  if (close) { clipSeen++; if (!oldHide) { if (CAM_CLIP_GUARD_OLD) clipDrawnClose++; else clipHid++; } }
  return close;
}
static inline int clipAheadCount(int ahead, int oldHide) {   // объект на луче вперёд ближе CLIP_AHEAD: счётчики как у clipCount
  if (ahead) { clipSeen++; if (!oldHide) { if (CAM_CLIP_GUARD_OLD) clipDrawnClose++; else clipHid++; } }
  return ahead;
}
static inline int clipGuardBox(float ex, float ey, float ez, const float b[6]) {   // машины, пешеходы трафика: ящик b = xmin ymin zmin xmax ymax zmax
  float d2 = camPointBoxD2(ex, ey, ez, b); int old = camNearBox(ex, ey, ez, b, CAM_HIDE_BOX);
  int close = clipCount(d2, old) | clipAheadCount(clipAheadBox(ex, ey, ez, b), old); return old || (!CAM_CLIP_GUARD_OLD && close);
}
static inline int clipGuardBody(float ex, float ey, float ez, float x, float y0, float y1, float z, float r, float oldThr) {   // персонаж: ось тела x,z от y0 до y1, радиус r
  float cy = ey < y0 ? y0 : ey > y1 ? y1 : ey, dx = x - ex, dy = cy - ey, dz = z - ez, d = sqrtf(dx * dx + dy * dy + dz * dz);
  int old = camNearBody(ex, ey, ez, x, y0, y1, z, oldThr); if (clipSmallOn) return old; int close = clipCount(fmaxf(0.f, d - r) * fmaxf(0.f, d - r), old) | clipAheadCount(clipAheadSphere(ex, ey, ez, x, cy, z, r + .15f), old);
  return old || (!CAM_CLIP_GUARD_OLD && close);
}
static inline int clipGuardProp(float ex, float ey, float ez, float x, float y, float z, float radius, float halfH, int oldHide) {   // проп: основание x,y,z, круг radius, высота 2*halfH
  { float dx_ = ex - x, dz_ = ez - z, far_ = radius + CLIP_AHEAD + 1.f; if (!oldHide && dx_ * dx_ + dz_ * dz_ > far_ * far_) return 0; }   // аудит 16.10: дальше всех порогов (0,3 м, взгляд 1,8 м) sqrtf не нужен — проп считается на каждый видимый кадр
  float hd = sqrtf((ex - x) * (ex - x) + (ez - z) * (ez - z)), h = hd > radius ? hd - radius : 0.f;
  float vy = ey < y ? y - ey : ey > y + 2.f * halfH ? ey - (y + 2.f * halfH) : 0.f;
  if (clipSmallOn) return oldHide;
  int close = clipCount(h * h + vy * vy, oldHide) | clipAheadCount(clipAheadSphere(ex, ey, ez, x, ey < y ? y : ey > y + 2.f * halfH ? y + 2.f * halfH : ey, z, radius + .15f), oldHide); return oldHide || (!CAM_CLIP_GUARD_OLD && close);
}
static inline int clipGuardSphere(float ex, float ey, float ez, float x, float y, float z, float rad, int oldHide) {   // стейтпроп: центр и радиус
  if (clipSmallOn) return oldHide;
  float dx = x - ex, dy = y - ey, dz = z - ez, t = rad + CLIP_MARGIN; int close = dx * dx + dy * dy + dz * dz < t * t;
  if (close) { clipSeen++; if (!oldHide) { if (CAM_CLIP_GUARD_OLD) clipDrawnClose++; else clipHid++; } }
  return oldHide || (!CAM_CLIP_GUARD_OLD && close);
}
// Правка «по настоящему кузову» (дирижёр 15.10 00:00): ящик списка отрисовки у машин — сфера R ≈ 2,8 м по каждой оси (−1…+4 м по высоте): машина гасла за 3–4 м от камеры (видимый pop).
// Для трафика и машин миссии порог и правило «по взгляду» — по ориентированному ящику кузова (полуширина/полудлина/смещение центра из параметров машины, высота bodyLo…bodyHi);
// ящик списка остаётся только для отсечения по пирамиде кадра. TR_CARBOX_OLD=1 — прежнее (по грубому ящику)
#ifndef TR_CARBOX_OLD
#define TR_CARBOX_OLD 0
#endif
extern const Car *trVisCar;   // машина, чей ящик сейчас проверяет trVis (ставят списки отрисовки; traffic.c), NULL — не машина
static inline int clipAheadObb(const float o[3], const float f[3], const float lo[3], const float hi[3]) {   // луч вперёд CLIP_AHEAD против ящика в осях машины
  float t0 = 0.f, t1 = CLIP_AHEAD;
  for (int k = 0; k < 3; k++) {
    if (fabsf(f[k]) < 1e-5f) { if (o[k] < lo[k] || o[k] > hi[k]) return 0; continue; }
    float a = (lo[k] - o[k]) / f[k], c = (hi[k] - o[k]) / f[k]; if (a > c) { float s = a; a = c; c = s; }
    if (a > t0) t0 = a; if (c < t1) t1 = c; if (t0 > t1) return 0;
  }
  return 1;
}
static inline int clipGuardCar(float ex, float ey, float ez, const Car *k, const float bb[6]) {   // oldHide — прежний порог по грубому ящику bb
  CarBox b; carBox(k, &b);
  float ylo = k->y + k->p.bodyLo, yhi = k->y + (k->p.bodyHi > k->p.bodyLo ? k->p.bodyHi : k->p.bodyLo + 1.5f);
  float dx = ex - b.x, dz = ez - b.z, a = dx * b.fx + dz * b.fz, l = -dx * b.fz + dz * b.fx;   // вдоль и поперёк кузова
  float ga = fabsf(a) > b.hl ? fabsf(a) - b.hl : 0.f, gl = fabsf(l) > b.hw ? fabsf(l) - b.hw : 0.f, gy = ey < ylo ? ylo - ey : ey > yhi ? ey - yhi : 0.f;
  float d2 = ga * ga + gl * gl + gy * gy, t = camNearNow + .05f;
  int old = !CAM_NEARHIDE_OLD && d2 < t * t;
  int close = clipCount(d2, old);
  float o[3] = {l, ey, a}, f[3] = {camFwdN[0] * -b.fz + camFwdN[2] * b.fx, camFwdN[1], camFwdN[0] * b.fx + camFwdN[2] * b.fz};   // глаз и взгляд в осях (поперёк, вверх, вдоль)
  float lo[3] = {-b.hw, ylo, -b.hl}, hi[3] = {b.hw, yhi, b.hl};
  int ahead = camNearNow > 0.f && clipAheadObb(o, f, lo, hi); close |= clipAheadCount(ahead, old);
  (void)bb; return old || (!CAM_CLIP_GUARD_OLD && close);
}
#endif
