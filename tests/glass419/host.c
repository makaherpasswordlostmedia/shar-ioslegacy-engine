// №419 (Роб 09.10, PSP: «L5 F3-5 — вертикальная стеклянная труба при ударе должна разбиться, как в оригинале, а отлетает и летает по
// уровню, как металлическая»). Причина — строки ATC без номера обломка в tools/prp2_export.py BREAK_BY_ATC: DynaPhys без обломка —
// твёрдое летающее тело. Семейство на всех уровнях (по данным диска, BreakableObject 0x3001000):
//   eSpaceNeedleBreaking -> 18 l02z4_glasshatter (стеклянная игла l2z4 / l5z4), ePumpkin/Med/Small -> 30/31/32 (тыквы l7),
//   eCasinoJump -> 33 l3_burns_effects (l3r2)
// Мир ботов (tools/bots/world.c): те же props.c, stateprops.c, game.c, что EBOOT. Машина 15 м/с прямо в предмет:
//   break   — у предмета есть обломок своего номера, после удара предмет спрятан (не тело), обломок SPR1 играет в его точке,
//             предмет не летит (скорость 0), машина проезжает место (коллизии нет)
// Ожидание — таблица ниже (точки и номера из данных уровня, z отзеркален); красный — level.shr до правки (BREAK419_OLD=1)
//   host HOMER.shr N LEVEL.shr [N LEVEL.shr ...]
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "world.h"

static BotWorld W; static int fails;
typedef struct { int lv, brk; float p[3]; const char *what; } Want;
#include "want.h"
static int nearestProp(const float p[3]) {
  int best = -1; float bd = 1.f;
  for (unsigned i = 0; i < W.props.ninst; i++) { const PropDef *d = &W.props.def[i]; float dx = d->x - p[0], dy = d->y - p[1], dz = d->z - p[2], dd = dx * dx + dy * dy + dz * dz;
    if (dd < bd) { bd = dd; best = (int)i; } }
  return best;
}
int main(int argc, char **argv) {
  if (argc < 4 || (argc - 2) % 2) { fprintf(stderr, "host HOMER.shr N LEVEL.shr [...]\n"); return 2; }
  setvbuf(stdout, NULL, _IONBF, 0);
  for (int a = 2; a + 1 < argc; a += 2) {
    int lv = atoi(argv[a]);
    if (bwData(argv[a + 1], argv[1], NULL)) { printf("FAIL: данные %s\n", argv[a + 1]); return 1; }
    for (unsigned w = 0; w < sizeof WANT / sizeof WANT[0]; w++) {
      if (WANT[w].lv != lv) continue;
      bwNew(&W); for (int i = 0; i < 5; i++) bwStep(&W, 0, 0, 0);
      int i = nearestProp(WANT[w].p);
      if (i < 0) { printf("CHECK L%d %-10s FAIL  предмета в точке данных нет\n", lv, WANT[w].what); fails++; continue; }
      int part, brk; propsTypeFx(&W.props, W.props.def[i].type, &part, &brk);
      PropState *st = &W.props.st[i]; float x0 = st->x, z0 = st->z;
      // удар: машина 15 м/с вплотную к предмету по ходу (правило гейта: обычная езда по городу) — тот же propsHitCar, что в кадре EBOOT;
      // прямой подъезд не годится для иглы L2/L5: она внутри опор башни на постаменте 4 м над улицей. Потом машина уезжает, мир
      // шагает 1.5 с: предмет должен быть спрятан и стоять, обломок — играть в его точке
      const ColWorld *C = bwCol(); CarBox cb; carBox(&W.car, &cb);
      float R0 = W.props.types[W.props.def[i].type].radius + cb.hl - .2f;
      float cx = x0 - cb.fx * R0, cz = z0 - cb.fz * R0, cy = st->y; { float g_; if (colGround(C, cx, cz, st->y + 2.f, st->y - 40.f, &g_, 0)) cy = g_; }
      float lo = W.props.def[i].y, hi = W.props.def[i].y + 2.f * st->hy; if (cy < lo - .5f || cy > lo + .2f) cy = lo;   // кузов на опоре предмета (тыквы L7 в ямках склона)
      W.car.x = cx; W.car.y = cy; W.car.z = cz; carSetSpeed(&W.car, 15.f);
      CarBox prev; carBox(&W.car, &prev); prev.x -= cb.fx * .25f; prev.z -= cb.fz * .25f;
      if (getenv("GL_DEBUG")) printf("  dbg asleep %d hidden %d cy %.2f defy %.2f sty %.2f hy %.2f hx %.2f hz %.2f car %.2f %.2f v %.2f\n", st->asleep, st->hidden, cy, W.props.def[i].y, st->y, st->hy, st->hx, st->hz, W.car.x, W.car.z, W.car.v);
      propsHitCar(&W.props, C, &W.car, &prev);
      int hidAt = st->hidden ? 0 : -1;
      if (getenv("GL_DEBUG")) { int b = spBreakOf(&W.sp, W.props.def[i].type); for (unsigned k = 0; k < W.sp.ninst; k++) if ((int)W.sp.inst[k].type == b) printf("  deb k%u st %d at %.1f %.1f\n", k, W.sp.run[k].state, W.sp.run[k].x, W.sp.run[k].z);
        for (unsigned j = 0; j < W.props.ninst; j++) if (W.props.st[j].hidden) printf("  hidden %u at %.1f %.1f\n", j, W.props.def[j].x, W.props.def[j].z); }
      // обломок заиграл в точке предмета, разбитого этим ударом (сразу после удара: жизнь 1.25–2.5 с). Соседняя тыква L7 (30_54 / 30_55)
      // бьётся тем же ударом, пул обломка 30 по данным — 1: обломок играет у последней разбитой — засчитывается любой разбитой
      int deb = 0; { int b = spBreakOf(&W.sp, W.props.def[i].type);
        if (b >= 0) for (unsigned k = 0; k < W.sp.ninst; k++) if (W.sp.inst[k].type == (unsigned)b && W.sp.run[k].state != 0)
          for (unsigned j = 0; j < W.props.ninst; j++) if (W.props.st[j].hidden && hypotf(W.sp.run[k].x - W.props.def[j].x, W.sp.run[k].z - W.props.def[j].z) < .5f) deb = 1; }
      // повторный проезд по тому же месту: спрятанный предмет машину не трогает (коллизии нет)
      float v0[3] = {W.car.vel[0], W.car.vel[1], W.car.vel[2]}; propsHitCar(&W.props, C, &W.car, &prev);
      int noCol = st->hidden && W.car.vel[0] == v0[0] && W.car.vel[2] == v0[2];
      { float g_ = 0.f; float fx_ = x0 + 300.f, fz_ = z0; colGround(C, fx_, fz_, 200.f, -200.f, &g_, 0); bwPlace(&W, fx_, g_, fz_, 0.f); }
      float maxV = 0.f, maxMove = 0.f;
      for (int f = 0; f < 90; f++) { bwStep(&W, 0, 0, 0);
        float v = sqrtf(st->vel[0] * st->vel[0] + st->vel[1] * st->vel[1] + st->vel[2] * st->vel[2]); if (v > maxV) maxV = v;
        float mv = hypotf(st->x - x0, st->z - z0); if (mv > maxMove) maxMove = mv; }
      float past = noCol ? 1.f : 0.f, D = R0;
      int ok = brk == WANT[w].brk && hidAt >= 0 && deb && maxV < .01f && maxMove < .01f && noCol;
      printf("CHECK L%d %-10s %s  обломок %d (ждём %d), спрятан на кадре %d, обломок SPR1 в точке %d, предмет: скорость макс %.2f м/с, сдвиг %.2f м; повторный проезд без контакта %.0f (удар с %.1f м от центра)\n",
             lv, WANT[w].what, ok ? "OK  " : "FAIL", brk, WANT[w].brk, hidAt, deb, maxV, maxMove, past, D);
      fails += !ok;
    }
  }
  printf("RESULT %s %d\n", fails ? "FAIL" : "OK", fails);
  return fails ? 1 : 0;
}
