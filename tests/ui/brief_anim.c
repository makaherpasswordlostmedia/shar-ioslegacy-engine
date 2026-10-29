// №512: хост-проверка позы карточки миссии (viewer/ui_anim.h uiBriefPose): вход слева за 0,40 с, левая рука едет с ней и уходит, выход вправо, правая рука.
// Красный контроль: argv[1]="still" — поза без движения (как до правки): проверка обязана упасть.
#include <stdio.h>
#include <string.h>
#include "ui_anim.h"
static int bad;
#define CK(c, m) do { if (!(c)) { printf("FAIL %s\n", m); bad = 1; } } while (0)
int main(int argc, char **argv) {
  int still = argc > 1 && !strcmp(argv[1], "still");
  const float cL = 91.f, cR = 404.f, aLR = 60.f, aRL = 420.f, W = 480.f;
  float card, al, ar, ca, ba; int sl, sr, i;
  float prev = -1e9f;
  for (i = 0; i <= 60; i++) {   // вход, 60 к/с
    float t = i / 60.f; uiBriefPose(0, t, cL, cR, aLR, aRL, W, &card, &al, &ar, &sl, &sr, &ca, &ba);
    if (still) card = al = ar = 0.f;
    if (i == 0) CK(card + cR < 0.f, "start: card fully left of the screen");
    CK(card >= prev - 1e-4f, "entry monotonic"); prev = card;
    if (t < 0.4f - 1e-4f) CK(al == card && sl, "left arm rides with the card");
    if (t > 0.86f) CK(!sl, "№612: left arm gone after it retracts (no arms at rest)");
    if (t > 0.41f && t < 0.59f) CK(sl && al == 0.f, "№612: left arm holds at the card until 0.6 s (PS2)");
    CK(!sr, "right arm absent on entry");
  }
  uiBriefPose(0, 0.4f, cL, cR, aLR, aRL, W, &card, &al, &ar, &sl, &sr, &ca, &ba); if (still) card = 0.f; CK(fabsf(card) < 1e-3f, "card at rest at 0.40 s");
  uiBriefPose(0, 0.2f, cL, cR, aLR, aRL, W, &card, &al, &ar, &sl, &sr, &ca, &ba); if (still) card = -(cR + 16.f);
  CK(fabsf(card / (cR + 16.f)) < 0.7f && fabsf(card / (cR + 16.f)) > 0.4f, "half way near 0.20 s");
  prev = -1e9f;
  for (i = 0; i <= 60; i++) {   // выход
    float t = i / 60.f; uiBriefPose(1, t, cL, cR, aLR, aRL, W, &card, &al, &ar, &sl, &sr, &ca, &ba);
    if (still) card = ar = 0.f;
    CK(card >= prev - 1e-4f, "exit monotonic"); prev = card;
    CK(sr, "№612: right arm takes the card away");
    if (t < 0.01f) CK(ar > W - aRL, "right arm starts off the right edge");
    if (t > 0.39f) CK(fabsf(ar - card) < 1e-3f, "right arm rides with the card after clamping on");
    if (t < 0.55f) CK(fabsf(card) < 1e-3f, "card stands until 0.56 s (PS2)");
    CK(!sl, "left arm absent on exit");
  }
  uiBriefPose(1, 0.95f, cL, cR, aLR, aRL, W, &card, &al, &ar, &sl, &sr, &ca, &ba); if (still) card = 0.f; CK(cL + card >= W, "card is off the screen on the right at 0.95 s");
  uiBriefPose(1, 0.96f, cL, cR, aLR, aRL, W, &card, &al, &ar, &sl, &sr, &ca, &ba); CK(ca == 0.f, "card gone by 0.96 s");
  uiBriefPose(1, 0.20f, cL, cR, aLR, aRL, W, &card, &al, &ar, &sl, &sr, &ca, &ba); CK(ca == 1.f && ba < 1.f && ba > 0.f, "backdrop fades first");
  printf(bad ? "FAIL\n" : "PASS\n"); return bad;
}
