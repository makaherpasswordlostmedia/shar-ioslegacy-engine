// №538: логика очереди фонового чтения моделей машин миссии (viewer/mcrpre.h) с имитацией задержки чтения. cc -I viewer tests/mcr/pre_queue.c -o /tmp/pre_queue && /tmp/pre_queue
// Красный контроль: -DPRE_BREAK=1 (машина игрока не ждёт остаток -> тест падает).
#include <stdio.h>
#include "mcrpre.h"
static int fails;
#define CHECK(c, ...) do { if (!(c)) { fails++; printf("FAIL: "); printf(__VA_ARGS__); printf("\n"); } } while (0)
int main(void) {
  // 1. блок готов: берём, при любом возрасте; машина игрока тоже
  CHECK(mcrPreDecide(1, 0, 0) == MCRPRE_TAKE, "готов, возраст 0");
  CHECK(mcrPreDecide(1, 99, 1) == MCRPRE_TAKE, "готов, игрок");
  // 2. не готов: машина миссии откладывается до MAX_AGE, потом ждём остаток (синхронный откат)
  for (int age = 0; age < MCRPRE_MAX_AGE; age++) CHECK(mcrPreDecide(0, age, 0) == MCRPRE_DEFER, "не готов, возраст %d должен откладываться", age);
  CHECK(mcrPreDecide(0, MCRPRE_MAX_AGE, 0) == MCRPRE_WAIT, "после MAX_AGE дождаться остатка");
  // 3. машина игрока не откладывается
  CHECK(mcrPreDecide(0, 0, 1) == MCRPRE_WAIT, "игрок не откладывается");
  // 4. имитация: чтение занимает R кадров (2 вызова mcrGet на кадр); модель появится не позже R кадров, при R > MAX_AGE/2 — через откат на MAX_AGE/2 кадров
  for (int R = 0; R <= 20; R += 4) {
    int age = 0, frame = 0, got = -1;
    for (frame = 0; frame < 40 && got < 0; frame++) for (int call = 0; call < 2 && got < 0; call++) {
      int act = mcrPreDecide(frame >= R, age, 0);
      if (act == MCRPRE_DEFER) age++; else got = frame;
    }
    int bound = R > MCRPRE_MAX_AGE / 2 ? MCRPRE_MAX_AGE / 2 : R;
    CHECK(got == bound, "чтение %d кадров: модель на кадре %d, ожидалось %d", R, got, bound);
  }
  // 5. старт чтения: только при месте в очереди и под модель, запасе кучи, и если модели нет и чтение не идёт
  CHECK(mcrPreMayStart(1, 1, 1, 0, 0), "обычный старт");
  CHECK(!mcrPreMayStart(0, 1, 1, 0, 0), "очередь занята");
  CHECK(!mcrPreMayStart(1, 0, 1, 0, 0), "нет места под модель");
  CHECK(!mcrPreMayStart(1, 1, 0, 0, 0), "куча без запаса");
  CHECK(!mcrPreMayStart(1, 1, 1, 1, 0), "модель уже в памяти");
  CHECK(!mcrPreMayStart(1, 1, 1, 0, 1), "уже читается");
  printf(fails ? "FAIL (%d)\n" : "PASS\n", fails);
  return fails != 0;
}
