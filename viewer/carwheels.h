// ЗАТРАВКА (--seed, без диска): только машины правила SLES, запас up не замерен (0.3 — без ограничения). Пересобрать:
//   .venv/bin/python tools/wheel_clear.py --header viewer/carwheels.h
// Колёса машин (правка Роба 354, 05.10): какие колёса не рисуются и на сколько колесу можно подняться над покоем, не выйдя
// сквозь кузов. СГЕНЕРИРОВАНО tools/wheel_clear.py --header — руками не править (источники и способ замера — в его шапке).
//   hide  — бит k: колесо w<k> не рисуется [PS2 код SLES_518.97: frink_v honor_v hbike_v witchcar ship mono_v — все четыре,
//           rocke_v — передние w2 w3]
//   up[k] — подъём колеса w<k> над покоем по оси Y модели, м, до которого оно не видно сквозь кузов (снимки модели сверху);
//           0.3 — не выходит до 0.3 м. Движок: viewer/carvis.c jointXf (ход подвески вверх не больше up[k])
// Прежнее поведение (колёса-заглушки рисуются, ход вверх до lim − eq): -DCARWHEELS_OLD=1
#ifndef SHAR_CARWHEELS_H
#define SHAR_CARWHEELS_H

#ifndef CARWHEELS_OLD
#define CARWHEELS_OLD 0
#endif

typedef struct { const char *name; unsigned char hide; float up[4]; } CarWheelCon;

static const CarWheelCon carWheelCons[] = {
  {"frink_v", 0xF, {0.0f, 0.0f, 0.0f, 0.0f}},
  {"hbike_v", 0xF, {0.0f, 0.0f, 0.0f, 0.0f}},
  {"honor_v", 0xF, {0.0f, 0.0f, 0.0f, 0.0f}},
  {"mono_v", 0xF, {0.0f, 0.0f, 0.0f, 0.0f}},
  {"rocke_v", 0xC, {0.3f, 0.3f, 0.0f, 0.0f}},
  {"ship", 0xF, {0.0f, 0.0f, 0.0f, 0.0f}},
  {"witchcar", 0xF, {0.0f, 0.0f, 0.0f, 0.0f}},
};
#define CAR_WHEEL_CONS ((int)(sizeof carWheelCons / sizeof carWheelCons[0]))

// имя машины без учёта регистра (в TrModel трафика — как в скриптах: cPolice, compactA; в CAR1 — имя .con)
static inline int carWheelNameEq(const char *a, const char *b) {
  for (;; a++, b++) { char x = *a, y = *b; if (x >= 'A' && x <= 'Z') x += 32; if (y >= 'A' && y <= 'Z') y += 32;
    if (x != y) return 0;
    if (!x) return 1; }
}
static inline const CarWheelCon *carWheelsFor(const char *name) {
  if (!name || !*name) return 0;
  for (int i = 0; i < CAR_WHEEL_CONS; i++) if (carWheelNameEq(carWheelCons[i].name, name)) return &carWheelCons[i];
  return 0;
}
// маска колёс, которые не рисуются (0 — все рисуются; при CARWHEELS_OLD — всегда 0)
static inline unsigned carWheelHide(const char *name) {
  if (CARWHEELS_OLD) return 0;
  const CarWheelCon *w = carWheelsFor(name); return w ? w->hide : 0;
}
// запас хода колеса w<k> вверх над покоем, м (нет машины в таблице или CARWHEELS_OLD — dflt: без ограничения)
static inline float carWheelUp(const char *name, int k, float dflt) {
  if (CARWHEELS_OLD || k < 0 || k > 3) return dflt;
  const CarWheelCon *w = carWheelsFor(name); return w ? w->up[k] : dflt;
}

// №878 (Роб 23.10 после TEST50: «машина Гомера розовая — там диски хромированные, перелив есть; если это единственная машина, где диски
// не должны крутиться, — значит единственная; проверь все остальные на градиент света и тени внутри самой накладки диска»): с №867 боковины
// (картинка диска) не крутились у всех. Бот tools/wheelspin878.py + вид накладки tools/wheelcap_view878.py по всем 89 машинам диска:
// однобокий свет/тень внутри накладки (гармоники 1–2 по кругу) — famil_v (хром, 0,163) и smith_v (золото с секторами блика, 0,137); дальше
// плавный ряд ≤ 0,118 — свечение ровно в центре и рисунок спиц/болтов, при вращении свет не «крутится». honor_v и hbike_v — не диски
// (заглушки и полосы), как были. Остальные машины: колесо крутится целиком, как до №867. WHEELSPIN878_OLD=1 — неподвижные у всех (№867)
#ifndef WHEELSPIN878_OLD
#define WHEELSPIN878_OLD 0
#endif
static inline int carWheelCapStill(const char *name) {
  static const char *const still[] = {"famil_v", "smith_v", "honor_v", "hbike_v"};
  if (WHEELSPIN878_OLD) return 1;
  for (unsigned i = 0; i < sizeof still / sizeof still[0]; i++) if (carWheelNameEq(still[i], name)) return 1;
  return 0;
}

#endif
