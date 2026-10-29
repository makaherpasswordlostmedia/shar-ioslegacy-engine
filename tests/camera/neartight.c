// №621: проезжающий мимо камеры объект виден до конца (исчезает, только когда ближняя плоскость вот-вот войдёт в его объём).
// Красный контроль camNearOld = 1 (пороги №502) прячет машину в 0,45 м от глаза и человека в 0,7 м; новое — нет, но прячет при реальном касании.
#include <stdio.h>
#include "camnear.h"
float camNearNow; int camNearOld;
int main(void) {
  int bad = 0; camNearNow = .3f;
  float box[6] = {-1, -1, .45f, 1, 1, 4};   // кузов, ближний край в 0,45 м от глаза (0,0,0)
  float touch[6] = {-1, -1, .2f, 1, 1, 4};   // плоскость (0,3 м) уже режет
  camNearOld = 1; int oldHide = camNearBox(0, 0, 0, box, CAM_HIDE_BOX); int oldBody = camNearBody(0, 0, 0, .7f, -1, 1, 0, CAM_HIDE_NPC);
  camNearOld = 0; int newHide = camNearBox(0, 0, 0, box, CAM_HIDE_BOX), newTouch = camNearBox(0, 0, 0, touch, CAM_HIDE_BOX), newBody = camNearBody(0, 0, 0, .7f, -1, 1, 0, CAM_HIDE_NPC);
  printf("кузов в 0,45 м: прежнее прячет %d, новое %d; кузов, который режет плоскость: новое прячет %d\n", oldHide, newHide, newTouch);
  printf("человек в 0,7 м: прежнее прячет %d, новое %d\n", oldBody, newBody);
  if (!(oldHide == 1 && newHide == 0 && newTouch == 1 && oldBody == 1 && newBody == 0)) bad = 1;
  puts(bad ? "FAIL" : "PASS"); return bad;
}
