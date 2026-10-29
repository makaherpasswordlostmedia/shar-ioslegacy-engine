// Ревизия 11.10, 3.1: уход пузыря Барта считает рисование (tutDrawExit от wallDt), а не tutTick под условием; tutReset сбрасывает уходящий пузырь.
// Красный контроль: -DTUT_EXIT_OLD=1 — пузырь висит, пока tutTick не идёт (беседа / переход в первые 4 кадра), и переезжает через tutReset.
#include <stdio.h>
#include <string.h>
#include <pspctrl.h>
#include "tutorial.h"
#include "ui.h"
int audioTrack(const char *n) { (void)n; return -1; }
int sndMode(int m) { (void)m; return 0; } int sndModeCur(void) { return 0; } void sndVoice(int v) { (void)v; } int sndVoicePlaying(int v) { (void)v; return 0; }
int uiDrawTutorial(int msg, int cont) { (void)msg; (void)cont; return 1; }
void uiTutorialScale(float k) { (void)k; }
void uiPopHookFire(int ev) { (void)ev; }
void uiTutLayoutOld(int on) { (void)on; }
int uiTutorialCount(void) { return 30; }
int main(void) {
  int bad = 0, d = 0;
  tutReset(1); tutEvent(TUT_WALK); if (!tutActive()) { puts("FAIL: tutorial did not start"); return 1; }
  tutInput(0, 2.1f, &d);
  if (!tutInput(PSP_CTRL_CROSS, 1.f / 60, &d)) { puts("FAIL: X did not close"); return 1; }
  int frames = 0; while (tutDrawExit(1.f / 60) && frames < 600) frames++;   // tutTick не зовётся: беседа / переход сразу после закрытия
  printf("exit finished after %d frames without tutTick\n", frames);
  if (frames >= 20) { puts("FAIL: bubble hangs without tutTick (3.1)"); bad = 1; }
  tutReset(1); tutEvent(TUT_WALK); tutInput(0, 2.1f, &d); tutInput(PSP_CTRL_CROSS, 1.f / 60, &d);
  tutDrawExit(1.f / 60); tutReset(1);
  if (tutDrawExit(1.f / 60)) { puts("FAIL: exiting bubble survived tutReset"); bad = 1; }
  puts(bad ? "FAIL" : "PASS"); return bad;
}
