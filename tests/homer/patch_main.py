#!/usr/bin/env python3
"""Homer integration patch for viewer/main.c (stage 4), applied to a COPY: tests/homer/build/game.c.

The same blocks are the patch documented in docs/homer_integration.md (sections P1..P10). Test-only blocks
(scenario flags for PPSSPP screenshots) are marked T and are NOT part of the integration.
Each block is anchored on a unique line of main.c; if main.c changed and an anchor is gone, the script stops and
names the block — then docs/homer_integration.md needs the same fix.

  python tests/homer/patch_main.py [--no-test] [--out FILE]
"""
from pathlib import Path as _MainPath
import sys as _MainSys
_MainSys.path.insert(0, str(_MainPath(__file__).resolve().parents[2]/"tools"))
from main_source import read_main
import argparse, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# (id, anchor, where: 'after' | 'before' | 'replace', text)
P = [
('P1 include', '#include "carvis.h"', 'after',
 '#include "homer.h"    // этап 4: Гомер пешком (viewer/homer.c + skin.c, данные homer.shr)'),

('P2 globals', 'static CarVis cv; static int haveCarVis', 'after',
 '''static SkinModel *homerM; static Homer homer; static int haveHomer, doorHinge = -1;   // этап 4: Гомер (homer.shr рядом с EBOOT)
static void homerDoor(void *u, float open) {   // дверь водителя из анимации Гомера (шарнир CAR1, пока замок цел)
  (void)u; if (doorHinge >= 0 && cv.latched[doorHinge]) cv.th[doorHinge] = open * cv.hinge[doorHinge].max;
}
static const HomerCarCb homerCb = {homerDoor, 0, 0};
static int onFoot(void) { return haveHomer && !homerDriving(&homer); }'''),

('P3 load', '  sceIoClose(fd);\n\n  size_t p = 104;', 'before',
 '''  { char fn[256]; sibling(fn, "homer.shr"); homerM = skinLoad(fn);   // этап 4: Гомер (tools/homer_export.py)
    if (homerM && homerInit(&homer, homerM) == 0) haveHomer = 1;
    if (haveHomer && haveSP) { homer.solid = homerSolidSprops; homer.solidUser = &sprops; } }   // ящики/автоматы — твёрдые
  if (haveCarVis) for (int i = 0; i < cv.nhinge; i++)            // шарнир двери водителя (DoorDRot)
    if (cv.hinge[i].joint < cv.njoint && !strncmp(cv.joint[cv.hinge[i].joint].name, "DoorDRot", 8)) doorHinge = i;'''),

('P4 start in car', '  smokeInit(path);', 'before',
 '''  if (haveHomer && haveCol) { HomerCar hc; homerCarFrom(&hc, &car, cv.lift); homerSetInCar(&homer, &hc); }   // этап 4: старт за рулём'''),

('P5 triangle', '    if (hit & PSP_CTRL_TRIANGLE) { fly = !fly;', 'replace_line',
 '''    if ((hit & PSP_CTRL_TRIANGLE) && haveHomer && haveCol && !fly && !(pad.Buttons & PSP_CTRL_LTRIGGER)) {   // этап 4: △ — выйти / сесть
      HomerCar hc; homerCarFrom(&hc, &car, cv.lift);
      if (homerDriving(&homer)) { if (fabsf(car.v) < 5.f) homerExitCar(&homer, &hc, &homerCb); }   // выходит на малой скорости
      else if (homerCanEnter(&homer, &hc)) homerEnterCar(&homer, &hc, &homerCb);
      hit &= ~PSP_CTRL_TRIANGLE;
    }
    if (hit & PSP_CTRL_TRIANGLE) { fly = !fly; fx = camx; fy = camy; fz = camz; fyaw = atan2f(x - camx, -(z - camz)); fpitch = -.2f; }   // L+△ (или без Гомера) — полёт'''),

('P6 circle', '    if (hit & PSP_CTRL_CIRCLE) {', 'replace_line',
 '''    if ((hit & PSP_CTRL_CIRCLE) && !onFoot()) {   // этап 4: пешком ○ — стомп (тест-прогон — только из машины)'''),

('P7 car input', '      carUpdate(&car, &world, &in, dt);', 'before',
 '''      if (onFoot()) { in.throttle = in.brake = in.steer = 0.f; in.handbrake = 1.f; }   // этап 4: водителя нет — стоит на ручнике'''),

('P8 homer update', '      if (haveCarVis) carVisUpdate(&cv, &car, &in, dt);', 'after',
 '''      if (haveHomer) {   // этап 4: Гомер — после carVisUpdate (дверь поверх шарниров), до пропов/монет
        HomerCar hc; homerCarFrom(&hc, &car, cv.lift);
        HomerInput hi; memset(&hi, 0, sizeof hi); hi.camYaw = homer.camYaw;
        if (onFoot()) {
          hi.mx = ax; hi.my = -ay;
          if (pad.Buttons & PSP_CTRL_LEFT) hi.mx = -1.f; if (pad.Buttons & PSP_CTRL_RIGHT) hi.mx = 1.f;
          if (pad.Buttons & PSP_CTRL_UP) hi.my = 1.f; if (pad.Buttons & PSP_CTRL_DOWN) hi.my = -1.f;
          hi.jump = (hit & PSP_CTRL_CROSS) != 0; hi.attack = (hit & PSP_CTRL_SQUARE) != 0;   // X прыжок, □ удар (X X □ — стомп)
          hi.dash = (pad.Buttons & PSP_CTRL_CIRCLE) != 0;                       // ○ зажат — бег (ControllerPS2.pag DASH / SPRINT)
        }
        homerUpdate(&homer, &world, &hc, &hi, dt);
        HomerEvent e;
        while (homerPopEvent(&homer, &e)) {
          if (e.type == HOMER_EV_HIT || e.type == HOMER_EV_STOMP) {
            if (haveSP) for (unsigned i = 0; i < sprops.ninst; i++) {          // стейтпропы: ящик/автомат/будка/куст...
              if (!sprops.run[i].alive) continue;
              float c[3], r; spBounds(&sprops, i, c, &r);
              if (homerHitTest(&e, c[0], c[1], c[2], fminf(r, 1.f))) spEvent(&sprops, i, e.type == HOMER_EV_HIT ? SP_EV_HIT : SP_EV_STOMP);
            }
            if (haveProps) for (unsigned i = 0; i < props.ninst; i++) {        // сбиваемые пропы PRP1: пинок как лёгкий удар машиной
              PropState *st = &props.st[i]; PropType *ty = &props.types[props.def[i].type];
              if (st->hidden || ty->mass <= 0.f || !homerHitTest(&e, st->x, st->y, st->z, ty->radius)) continue;
              float dx = e.dx, dz = e.dz; if (e.type == HOMER_EV_STOMP) { dx = st->x - e.x; dz = st->z - e.z; float l = sqrtf(dx * dx + dz * dz) + 1e-3f; dx /= l; dz /= l; }
              if (onPropKick(0, i, dx, dz)) { st->hidden = 1; st->asleep = 1; continue; }   // обломок (дерево, знак, гидрант)
              float k = 6.f * 100.f / (100.f + ty->mass);                         // лёгкое летит, тяжёлое едва сдвигается
              st->vel[0] = dx * k; st->vel[2] = dz * k; st->vel[1] = fminf(k * .4f, 3.f);
              st->w[0] = dz * k; st->w[2] = -dx * k; st->asleep = 0; st->sleepT = 0.f; st->fresh = 1;
            }
          }
          else if (e.type == HOMER_EV_HURT && haveCoins) { int n = coins.collected < 10 ? coins.collected : 10;   // удар током: монеты разлетаются
            coins.collected -= n; coinsDrop(&coins, n, e.x, e.y, e.z, homer.groundY); }
          else if (e.type == HOMER_EV_LAND && e.r > 6.f) for (int k = 0; k < 4; k++)   // пыль при жёстком приземлении
            fxSpawn(FX_SMOKE, e.x, e.y + .1f, e.z, (k & 1 ? 1.f : -1.f), .4f, (k & 2 ? 1.f : -1.f));
        }
      }'''),

('P9 coins', '      if (haveCoins) coinsUpdate(&coins, car.x, car.y + 0.8f, car.z, 1, dt);', 'replace_line',
 '''      if (haveCoins) {   // этап 4: монеты подбирает Гомер пешком (inCar = 0, досягаемость ×1) или машина (×2.25)
        float cp[3] = {car.x, car.y + 0.8f, car.z}; int drv = !haveHomer || homerDriving(&homer);
        if (haveHomer) homerCoinPoint(&homer, cp);
        coins.dropAuto = drv; coinsUpdate(&coins, cp[0], cp[1], cp[2], drv, dt);
      }'''),

('P10 camera', '      { float cp[3], lk[3]; chaseCamUpdate(&car, camAng, dt, cp, lk);', 'after',
 '''        if (onFoot()) { homerCamera(&homer, &world, dt, cp, lk); chase.init = 0;   // этап 4: камера пешком
          x = homer.x; y = homer.y; z = homer.z; h = homer.h; v = homer.speed; }'''),

('P11 draw', '    if (haveCarVis && haveCol && !bpass) { resetState(); carVisDrawFlares(', 'after',
 '''    if (haveHomer && haveCol && !bpass) {   // этап 4: Гомер (и за рулём — виден в окна); GE-скиннинг, свой свет
      float dx = homer.x - ex, dz = homer.z - ez;
      if (dx * dx + dz * dz < 80.f * 80.f) { homerPose(&homer); resetState(); homerDraw(&homer); resetState(); }
    }'''),

('P12 hud', '      hudLine(2, 0xffc0c0c0, fly ?', 'before',
 '''      if (onFoot()) {   // этап 4: подсказка пешком
        static const char *hs[] = {"FOOT", "KICK", "STOMP", "HURT", "TO DOOR", "GET IN", "CAR", "GET OUT"};
        snprintf(s, sizeof s, "HOMER %s %4.1f m/s  X:jump []:kick O:run X-X-[]:stomp /\\\\:action", hs[homer.state], homer.speed);
        hudLine(3, 0xff80ff80, s);
      }'''),
]

# test-only: scenario.txt flags for PPSSPP (viewer/smoke.h) — stick, buttons, time freeze, auto-walk
T = [
('T1 globals', 'static CarVis cv; static int haveCarVis', 'after',
 'static float hStickX, hStickY, hFreeze = 1.f, hGoX, hGoZ; static int hStick, hPress, hGo;   // тест: флаги scenario.txt'),
('T2 press', '    unsigned hit = pad.Buttons & ~prev; prev = pad.Buttons;', 'after',
 '    hit |= hPress; hPress = 0;'),
('T3 flags', '        else if (!strcmp(sc.name, "view60")) longView = 0;', 'after',
 '''        else if (!strcmp(sc.name, "hstick")) { hStick = 1; hStickY = sc.a; }
        else if (!strcmp(sc.name, "hturn")) { hStick = 1; hStickX = sc.a; }
        else if (!strcmp(sc.name, "hrelease")) { hStick = 0; hStickX = hStickY = 0.f; hGo = 0; }
        else if (!strcmp(sc.name, "hjump")) hPress |= PSP_CTRL_CROSS;
        else if (!strcmp(sc.name, "hkick")) hPress |= PSP_CTRL_SQUARE;
        else if (!strcmp(sc.name, "hstomp")) hPress |= PSP_CTRL_CIRCLE;
        else if (!strcmp(sc.name, "henter")) hPress |= PSP_CTRL_TRIANGLE;
        else if (!strcmp(sc.name, "hfreeze")) hFreeze = sc.a;
        else if (!strcmp(sc.name, "hgx")) hGoX = sc.a;
        else if (!strcmp(sc.name, "hgz")) { hGoZ = sc.a; hGo = 1; }
        else if (!strcmp(sc.name, "hcam")) homer.camYaw = sc.a;'''),
('T4 freeze', '    float cfx, cfy, cfz, ex, ey, ez;\n    if (bpass) {', 'before',
 '''    dt *= hFreeze;
    if (hGo && haveHomer) {   // тест: идти к точке (hgx/hgz), стик — в осях «кадра» Гомера
      float gx = hGoX - homer.x, gz = hGoZ - homer.z, d = sqrtf(gx * gx + gz * gz), a = atan2f(gx, gz);
      homer.frame = 0.f; homer.heldX = -sinf(a); homer.heldY = cosf(a);
      if (d < .8f) { hGo = 0; hStick = 1; hStickX = hStickY = 0.f; } else { hStick = 1; hStickX = -sinf(a); hStickY = cosf(a); }
    }
    if (hStick) { ax = hStickX; ay = -hStickY; }'''),
]


def apply(src, blocks):
    for bid, anchor, where, text in blocks:
        n = src.count(anchor)
        if n != 1: sys.exit(f'{bid}: anchor found {n} times: {anchor!r}')
        i = src.index(anchor)
        if where == 'after':
            e = src.index('\n', i) + 1; src = src[:e] + text + '\n' + src[e:]
        elif where == 'before':
            s = src.rindex('\n', 0, i) + 1 if not anchor.startswith('\n') else i; src = src[:s] + text + '\n' + src[s:]
        elif where == 'replace_line':
            s = src.rindex('\n', 0, i) + 1; e = src.index('\n', i) + 1; src = src[:s] + text + '\n' + src[e:]
    return src


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--no-test', action='store_true'); ap.add_argument('--out')
    a = ap.parse_args()
    src = read_main(ROOT / 'viewer/main.c')
    src = apply(src, P + ([] if a.no_test else T))
    out = Path(a.out) if a.out else ROOT / 'tests/homer/build/game.c'
    out.parent.mkdir(parents=True, exist_ok=True); out.write_text(src)
    print(f'patched main.c -> {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out} ({len(P)} blocks{"" if a.no_test else f" + {len(T)} test"})')


if __name__ == '__main__':
    main()
