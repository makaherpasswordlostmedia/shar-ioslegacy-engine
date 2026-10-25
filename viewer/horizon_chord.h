// №911 (Роб 23.10, L3 пирс B7-6 и пляж B8-3: «серая плоская стена вблизи, Лиза разделена»): лента горизонта соединяет вершины контура ПРЯМЫМИ хордами, а контур сохранён только в точках излома (Дуглас-Пекер по азимуту
// и углу места). Где контур ровный (море, пустой берег), между соседними вершинами до 355° — хорда шла через цилиндр почти через глаз: плоская стена в 0–100 м от камеры (у 368 клеток из 378 на L5). Теперь между вершинами с
// разрывом больше HZ_GAP_DEG ставятся промежуточные по дуге с тем же углом места (линейно по азимуту, как и считался контур): лента везде на радиусе дальности, хорда не ближе R·cos(HZ_GAP_DEG/2) ≈ 0,996 R.
// HZ_CHORD911_OLD=1 — как было (вершины контура без добавок). Чистая функция без PSP-заголовков: её же гоняет tests/horizon/chord911.sh
#pragma once
#include <math.h>
#ifndef HZ_CHORD911_OLD
#define HZ_CHORD911_OLD 0
#endif
#ifndef HZ_GAP_DEG
#define HZ_GAP_DEG 10.f   // наибольший разрыв по азимуту между соседними вершинами ленты, градусов
#endif
#ifndef HZ_CHORD_NV
#define HZ_CHORD_NV 400   // вершин контура на клетку вместе с добавленными (буфер ленты: 4 вершины на столбец)
#endif
// p: вершины контура клетки (az u16, tan s16 /16384) по возрастанию азимута; пишет az/t, возвращает число столбцов (<= HZ_CHORD_NV). Не влезло — шаг вдвое грубее
static unsigned hzChordExpand(const unsigned char *p, unsigned nv, unsigned short *az, short *t) {
  unsigned step = HZ_CHORD911_OLD ? 0xFFFFu : (unsigned)(HZ_GAP_DEG * (65536.f / 360.f) + .5f), n;
  for (;;) {
    n = 0;
    for (unsigned k = 0; k < nv; k++) {
      unsigned short a0 = *(const unsigned short *)(p + 4 * k); short t0 = *(const short *)(p + 4 * k + 2);
      if (n < HZ_CHORD_NV) { az[n] = a0; t[n] = t0; } n++;
      if (k + 1 >= nv || HZ_CHORD911_OLD) continue;
      unsigned short a1 = *(const unsigned short *)(p + 4 * (k + 1)); short t1 = *(const short *)(p + 4 * (k + 1) + 2);
      unsigned d = (unsigned)((a1 - a0) & 0xFFFFu), ins = d > step ? (d + step - 1u) / step - 1u : 0u;
      for (unsigned j = 1; j <= ins; j++) { if (n < HZ_CHORD_NV) { az[n] = (unsigned short)(a0 + d * j / (ins + 1u)); t[n] = (short)(t0 + ((int)t1 - (int)t0) * (int)j / (int)(ins + 1u)); } n++; }
    }
    if (n <= HZ_CHORD_NV || step >= 0x8000u) break;
    step *= 2u;
  }
  return n <= HZ_CHORD_NV ? n : HZ_CHORD_NV;
}
