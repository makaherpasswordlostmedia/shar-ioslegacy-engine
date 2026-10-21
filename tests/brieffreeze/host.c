// Хост-проверка решений кадра брифинга (viewer/jitter.h bfDecide, правка «брифинг без перерисовки мира», разбор тура 12): перебор состояний и сценарий брифинга по кадрам.
//   cc -std=c99 -O2 -I viewer -DBRIEF_HOST tests/brieffreeze/host.c -o build/bf_host && build/bf_host
#include <stdio.h>
#include <math.h>
static int bfDecide(int base, int closed, int snapOk, int haveSnap, float poseDiff, int frames, int pending);
#define BF_DRAW 0
#define BF_HIDE 1
#define BF_BLIT 2
#define BF_CAPTURE 3
static int bfDecide(int base, int closed, int snapOk, int haveSnap, float poseDiff, int frames, int pending) {   // копия из viewer/jitter.h (держать равной: проверка ниже сверяет текст)
  if (!base) return BF_DRAW;
  if (closed) return BF_HIDE;
  if (!snapOk) return BF_DRAW;
  if (haveSnap && poseDiff <= .01f) return BF_BLIT;
  if (frames >= 3 && pending == 0) return BF_CAPTURE;
  return BF_DRAW;
}
int main(void) {
  int bad = 0, n = 0;
#define EXPECT(v, e, msg) do { n++; if ((v) != (e)) { bad++; printf("FAIL: %s (got %d want %d)\n", msg, (v), (e)); } } while (0)
  EXPECT(bfDecide(0, 1, 1, 1, 0, 9, 0), BF_DRAW, "вне брифинга мир рисуется всегда, даже если ирис закрыт");
  EXPECT(bfDecide(1, 1, 0, 0, 0, 0, 5), BF_HIDE, "брифинг под закрытым ирисом: мир не рисуется (и без снимка, и при подгрузке)");
  EXPECT(bfDecide(1, 0, 0, 0, 0, 9, 0), BF_DRAW, "ирис на экране, но не закрыт: рисуем как прежде");
  EXPECT(bfDecide(1, 0, 1, 0, 0, 2, 0), BF_DRAW, "первые кадры брифинга: рисуем");
  EXPECT(bfDecide(1, 0, 1, 0, 0, 3, 3), BF_DRAW, "подгрузка не кончилась: рисуем");
  EXPECT(bfDecide(1, 0, 1, 0, 0, 3, 0), BF_CAPTURE, "третий кадр, подгрузка кончилась: снимок");
  EXPECT(bfDecide(1, 0, 1, 1, 0.f, 4, 0), BF_BLIT, "есть снимок и камера на месте: показываем снимок");
  EXPECT(bfDecide(1, 0, 1, 1, 0.5f, 4, 0), BF_CAPTURE, "камера сдвинулась: мир заново и новый снимок");
  EXPECT(bfDecide(1, 0, 1, 1, 0.5f, 4, 2), BF_DRAW, "камера сдвинулась, подгрузка идёт: мир без снимка");
  EXPECT(bfDecide(1, 1, 1, 1, 0.5f, 4, 0), BF_HIDE, "закрытый ирис важнее снимка");
  // сценарий: брифинг 10 кадров при закрытом ирисе — ни одного кадра мира; затем ирис раскрывается: мир как прежде
  int drawn = 0; for (int f = 1; f <= 10; f++) drawn += bfDecide(1, 1, 0, 0, 0, 0, 0) == BF_DRAW;
  EXPECT(drawn, 0, "10 кадров брифинга под закрытым ирисом: мир не рисуется");
  drawn = 0; for (int f = 1; f <= 10; f++) drawn += bfDecide(0, 0, 0, 0, 0, 0, 0) == BF_DRAW;
  EXPECT(drawn, 10, "после брифинга мир рисуется каждый кадр");
  // сценарий со снимком: кадры 1–2 рисуют, 3 снимает, 4–10 показывают снимок
  int snap = 0, w = 0, b = 0, c = 0;
  for (int f = 1; f <= 10; f++) { int m = bfDecide(1, 0, 1, snap, 0.f, f, 0); if (m == BF_DRAW) w++; if (m == BF_CAPTURE) { c++; w++; snap = 1; } if (m == BF_BLIT) b++; }
  EXPECT(w, 3, "кадры мира за брифинг со снимком: три (два до снимка и снимаемый)"); EXPECT(c, 1, "один снимок"); EXPECT(b, 7, "семь кадров снимка");
  printf("%d проверок, ошибок %d\n%s\n", n, bad, bad ? "FAIL" : "OK"); return bad ? 1 : 0;
}
