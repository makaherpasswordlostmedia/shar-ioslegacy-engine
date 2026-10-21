// test_grandpa_glasses.c — проверка фильтрации розовых линз очков дедушки (№518)
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <assert.h>

#ifndef GRANDPA_GLASSES_OLD
#define GRANDPA_GLASSES_OLD 0
#endif

static int grandpaGlassesOld = GRANDPA_GLASSES_OLD;

typedef struct {
  int32_t tex, flags;
  uint32_t nv, ni;
} MockPiece;

int should_draw_piece(const MockPiece *pp) {
#if !GRANDPA_GLASSES_OLD
  // №518: у дедушки в gag_s2..s5 очки — сустав 25 (gpa_high_glasses); кусок ni=144 — линзы без текстуры,
  // получившие из Maya розовую текстуру-заглушку. Оправа (ni=84) остаётся, сквозь неё видны глаза (как у grandp_m.p3d)
  if (!grandpaGlassesOld && ((pp->flags >> 8) & 0xFF) == 25 && pp->ni == 144) return 0;
#endif
  return 1;
}

int main(void) {
  // Сустав 25 (gpa_high_glasses):
  // Кусок 0: линзы (joint 25, ni 144, nv 73)
  // Кусок 1: оправа (joint 25, ni 84, nv 55)
  // Другой объект: сустав 10, ni 144
  MockPiece lensPiece = { .tex = 0, .flags = (25 << 8), .nv = 73, .ni = 144 };
  MockPiece framePiece = { .tex = 1, .flags = (25 << 8), .nv = 55, .ni = 84 };
  MockPiece otherPiece = { .tex = 2, .flags = (10 << 8), .nv = 73, .ni = 144 };

#if !GRANDPA_GLASSES_OLD
  printf("Testing GRANDPA_GLASSES_OLD=0 (Новое поведение)...\n");
  int drawLens = should_draw_piece(&lensPiece);
  int drawFrame = should_draw_piece(&framePiece);
  int drawOther = should_draw_piece(&otherPiece);

  printf("  Отрисовка линз: %d (ожидается 0 - отфильтровано)\n", drawLens);
  printf("  Отрисовка оправы: %d (ожидается 1 - сохранено)\n", drawFrame);
  printf("  Отрисовка прочих объектов: %d (ожидается 1 - сохранено)\n", drawOther);

  if (drawLens != 0) {
    fprintf(stderr, "FAIL: Розовые линзы не отфильтрованы!\n");
    return 1;
  }
  if (drawFrame != 1) {
    fprintf(stderr, "FAIL: Оправа очков ошибочно подавлена!\n");
    return 1;
  }
  if (drawOther != 1) {
    fprintf(stderr, "FAIL: Посторонний объект ошибочно подавлен!\n");
    return 1;
  }

  // Также проверяем runtime переключатель grandpaGlassesOld
  grandpaGlassesOld = 1;
  if (should_draw_piece(&lensPiece) != 1) {
    fprintf(stderr, "FAIL: Runtime откат grandpaGlassesOld=1 не вернул отрисовку линз!\n");
    return 1;
  }
  grandpaGlassesOld = 0;

  printf("PASS: Линзы дедушки отфильтрованы, оправа и чужие меши сохранены.\n");
  return 0;
#else
  printf("Testing GRANDPA_GLASSES_OLD=1 (Красный контроль / Старое поведение)...\n");
  int drawLens = should_draw_piece(&lensPiece);
  printf("  Отрисовка линз в старом режиме: %d\n", drawLens);
  if (drawLens == 1) {
    fprintf(stderr, "RED CONTROL CONFIRMED: В старом режиме линзы рисуются (розовый артефакт присутствует)!\n");
    return 2; // Ожидаемое падение красного контроля
  }
  return 0;
#endif
}
