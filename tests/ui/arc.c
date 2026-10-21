// Дуга кольца Hit & Run (tests/ui/anim.py, правка 241): угол конца заливки, как его рисует viewer/ui_radial.h uiRadialFan,
// для шкал близнецов b3_chase 1400/1200/1000/820 и tw_v8_stand 400. Строки: ARC шкала угол_градусы (по часовой от 12 часов).
// argv[1] = "pre241" — прежняя дуга (полный круг от 12 часов, отрицательный контроль)
#include <stdio.h>
#include <string.h>
#include "ui_radial.h"
int main(int argc, char **argv) {
  int pre = argc > 1 && !strcmp(argv[1], "pre241");
  const float h[] = {19.25f, 43.29f, 67.32f, 70.56f, 88.85f};
  for (unsigned k = 0; k < sizeof h / sizeof h[0]; k++) {
    UiRadialPoint p[UI_RADIAL_MAX]; int n = uiRadialFan((int)(h[k] * 10.f + .5f), p);
    float a = pre ? h[k] * 3.6f : atan2f(p[n - 1].v - .5f, p[n - 1].u - .5f) * 57.29578f + 90.f;
    while (a < 0.f) a += 360.f; while (a >= 360.f) a -= 360.f;
    printf("ARC %.2f %.2f\n", h[k], a);
  }
  return 0;
}
