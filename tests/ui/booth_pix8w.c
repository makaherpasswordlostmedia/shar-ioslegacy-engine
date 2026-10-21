// Второй свидетель гейта правки 141: шаги знаков pix8 по самому заголовку движка (viewer/ui_layout.h pix8Adv) — раскладка
// будки на Маке (tools/ui_export.py pix8_adv) обязана совпасть знак в знак. Вывод: «код шаг» по строке для ASCII 32..126 и знаков кнопок
#include <stdio.h>
#include "ui_layout.h"
#include "bootmsx.h"
int main(void) {
  for (int c = 32; c < 256; c++) { int k = pix8Cell((unsigned char)c); if (k >= 0) printf("%d %d\n", c, pix8Adv(bootMsx, k)); }
  return 0;
}
