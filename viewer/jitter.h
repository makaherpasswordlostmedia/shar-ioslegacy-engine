// Правка Роба 500/416 (слово Роба 10.10: «сглаживание пикселей, рябь вдалеке, давай сильно»), приём 3 ресёрча: временное сглаживание «полпикселя».
// Проекция сдвигается на ±¼ пикселя по x и y, знак меняется каждый кадр; перед интерфейсом в кадр подмешивается прошлый кадр (он лежит в
// показываемом буфере VRAM, копия не нужна) как полноэкранный спрайт с долей jitterPct %. Статичная даль усредняет две выборки на пиксель
// (суперсэмплинг ×2), на движении дальний план получает лёгкое смазывание. ЭКСПЕРИМЕНТ: по умолчанию ВЫКЛЮЧЕН, включается файлом jitter рядом с EBOOT
// (число в файле — доля прошлого кадра, % , по умолчанию 40) или сценарием «flag jitter [%]». Кадр, где камера прыгнула (>3 м) или сменился угол, без
// подмеса (нет «призрака» через склейку). Цена: один спрайт 480x272 с текстурой из VRAM (≈0,2–0,5 мс видеочипа, процессору +0,05 мс). JITTER_OLD=1 — выкл
#include "bisect.h"
#ifndef JITTER_OLD
#define JITTER_OLD 0
#endif
// Удешевление (№503, замер TEST7: gesync 0,1–0,4 → 2,4–3,6 мс): подмес идёт ПОЛОСАМИ по 64 px (GE любит вертикальные полосы 32–64 px, кэш текстур 8 КБ,
// PPSSPP docs) и только верхней частью кадра — дальним планом: до 60 % высоты на полную долю, потом плавный спад до jitterCover % (по умолчанию 80);
// нижняя часть (ближняя дорога, машина игрока) без подмеса. Машина игрока, Гомер, люди, трафик и машины миссий рисуются с НЕсдвинутой проекцией
// (jitterUse): щель багажника и швы кузова не мигают полупикселями (№505), а мир за ними усредняется как прежде. JITTER_OLD=1 — выключает весь приём;
// JITTER_STRIPS_OLD=1 — прежний один спрайт на весь кадр (замер A/B); JITTER_CAR_OLD=1 — машины тоже со сдвигом
#ifdef SHAR_JITTER_DEFAULT
#define JITTER_DEFAULT 1
#endif
#ifndef JITTER_DEFAULT
#define JITTER_DEFAULT 0   // 1 — включён без файла (финал, после проверки цены на железе); файл nojitter выключает
#endif
#ifndef JITTER_STRIPS_OLD
#define JITTER_STRIPS_OLD 0
#endif
#ifndef JITTER_CAR_OLD
#define JITTER_CAR_OLD 0
#endif
// Шлейфы (слово Роба о TEST8: «машины и проезжающие NPC со шлейфом, всё размыто»): подмес лежал поверх готового кадра с машинами и людьми, и 40 % прошлого
// положения движущегося оставалось за ним хвостом; при движении камеры так же двоился весь мир. Теперь:
//  1) подмес идёт ДО машин, людей, трафика, пропов, стекла и частиц (сразу после неба), а «прошлый кадр» — копия мира без динамики в свободном куске VRAM
//     (JIT_HIST_*, только кадр 5650; верхние jitterCover % строк; копия делается после подмеса, значит копится как в TAA). Динамика рисуется поверх чистая.
//     JITTER_HIST_OLD=1 — прежний порядок (подмес в конце кадра из показываемого буфера), так же при файле fb32;
//  2) доля подмеса падает с движением камеры: сдвиг далёкой точки (поворот + перемещение/40 м) в пикселях за кадр, при 1,5 px и больше подмеса нет;
//     JITTER_MOTION_OLD=1 — доля не зависит от движения.
#ifndef JITTER_HIST_OLD
#define JITTER_HIST_OLD 0
#endif
#ifndef JITTER_MOTION_OLD
#define JITTER_MOTION_OLD 0
#endif
// №509 (слово Роба: швы и статичные края у камеры мигают от подмеса и сдвига): ближние JITTER_NEAR_M (35) м не трогаем. Сдвиг проекции: клетка города,
// чей бокс ближе порога, рисуется несдвинутой (jitterCell, в dlCity; шов клетка-клетка на кольце порога закрывает подложка клетки), дальние — сдвинутой.
// Подмес: спрайт идёт с тестом глубины на GE (вершинный z = глубина порога, GEQUAL: проходят только пиксели дальше порога; буфер глубины CPU не читает).
// Вместе: вблизи ни сдвига, ни подмеса, даль сглажена как в TEST7/9D. JITTER_NEAR_OLD=1 — как до правки
#ifndef JITTER_NEAR_OLD
#define JITTER_NEAR_OLD 0
#endif
#ifndef JITTER_NEAR_M
#define JITTER_NEAR_M 35.f
#endif
#define JIT_HIST_BYTES (BUF_W * SCR_H * 2)
#define JIT_HIST_OFF (0x200000u - JIT_HIST_BYTES)   // последние 272 КБ VRAM (HUD в main_levels.h занимает остальное)
static int jitterOn = JITTER_DEFAULT, jitterPct = 40, jitterCover = 80;
static ScePspFMatrix4 jitPm0, jitPmJ; static int jitActive;
static int jitCur = 1, jitNearZ; static int jitSign, jitHave, jitHist; static float jitEye[3], jitFov, jitLook[3];
// сдвиг проекции (вызывать сразу после sceGumPerspective)
static float jitW = 1.f; static int jitOk;   // jitW: доля подмеса от движения камеры (1 — неподвижна), jitOk: есть история и камера не прыгнула
// по движению камеры: сдвиг далёкой точки (поворот + перемещение/40 м) в пикселях за кадр; при 1,5 px и больше — 0. Считается один раз за кадр здесь
static void jitterMotion(const float eye[3], const float look[3], float fovDeg) {
  float ll = sqrtf(look[0] * look[0] + look[1] * look[1] + look[2] * look[2]); if (ll < 1e-4f) ll = 1.f;
  float n[3] = {look[0] / ll, look[1] / ll, look[2] / ll};
  float dx = eye[0] - jitEye[0], dy = eye[1] - jitEye[1], dz = eye[2] - jitEye[2], d2 = dx * dx + dy * dy + dz * dz;
  jitOk = jitHave && d2 < 9.f && fabsf(fovDeg - jitFov) < .02f; jitW = 1.f;
  if (jitOk && !JITTER_MOTION_OLD) {
    float ax = n[0] - jitLook[0], ay = n[1] - jitLook[1], az = n[2] - jitLook[2];
    float fpx = (SCR_H * .5f) / tanf(fovDeg * (.5f * 3.14159265f / 180.f));   // пикселей на радиан
    jitW = 1.f - (sqrtf(ax * ax + ay * ay + az * az) + sqrtf(d2) / 40.f) * fpx / 1.5f; if (jitW < 0.f) jitW = 0.f;
  }
  jitEye[0] = eye[0]; jitEye[1] = eye[1]; jitEye[2] = eye[2]; jitFov = fovDeg; jitHave = 1; jitLook[0] = n[0]; jitLook[1] = n[1]; jitLook[2] = n[2];
}
// сдвиг проекции (вызывать сразу после sceGumPerspective). Сдвиг и подмес только вместе и только когда камера почти неподвижна (jitW >= .35): в движении
// картинка ровная, без сдвига (иначе тонкие грани — бордюр, газон — мигают от ¼ px); JITTER_MOTION_OLD=1 — сдвиг всегда
static void jitterProj(const float eye[3], const float look[3], float fovDeg, float zn, float zf) {
  jitActive = 0; jitHist = !JITTER_HIST_OLD && fb16;
  if (!jitterOn || JITTER_OLD) return;
  if (jitHist) { jitterMotion(eye, look, fovDeg); if (!JITTER_MOTION_OLD && (!jitOk || jitW < .35f)) return; }
  jitSign ^= 1; float s = jitSign ? 1.f : -1.f;
  ScePspFMatrix4 pm; sceGumStoreMatrix(&pm); jitPm0 = pm;
  pm.z.x -= s * (.5f / SCR_W);   // ±¼ пикселя в NDC: ¼ * 2 / SCR_W
  pm.z.y -= s * (.5f / SCR_H);
  jitPmJ = pm; jitActive = 1; jitCur = 1;
  { float D = JITTER_NEAR_M; jitNearZ = zf > zn + 1.f && D > zn ? (int)(65535.f * zn * (zf / D - 1.f) / (zf - zn)) : 0; if (jitNearZ > 65534) jitNearZ = 65534; }   // глубина порога: DepthRange(65535,0), ближе — больше
  sceGumLoadMatrix(&pm);
}
// сдвиг проекции для динамики: j = 0 — несдвинутая (машины, люди, трафик), j = 1 — со сдвигом (мир, пропы)
static void jitterUse(int j) {
  if (!jitActive || JITTER_CAR_OLD) return;
  sceGuSetMatrix(GU_PROJECTION, j ? &jitPmJ : &jitPm0); jitCur = j;
}
// клетка города: ближе порога — несдвинутая проекция (вызывать перед каждым листом клетки), иначе сдвинутая
static int zfHold;   // №932б: идёт дальний проход города (своя проекция) — клетки проекцию не переставляют
static void jitterCell(const float bb[6], float ex, float ey, float ez) {
  if (zfHold) return;
  if (!jitActive || JITTER_NEAR_OLD || JITTER_CAR_OLD) return;
  float dx = ex < bb[0] ? bb[0] - ex : ex > bb[3] ? ex - bb[3] : 0.f, dy = ey < bb[1] ? bb[1] - ey : ey > bb[4] ? ey - bb[4] : 0.f, dz = ez < bb[2] ? bb[2] - ez : ez > bb[5] ? ez - bb[5] : 0.f;
  int sh = dx * dx + dy * dy + dz * dz >= JITTER_NEAR_M * JITTER_NEAR_M;
  if (sh != jitCur) { sceGuSetMatrix(GU_PROJECTION, sh ? &jitPmJ : &jitPm0); jitCur = sh; }
}
static void jitterEndFrame(void) { jitActive = 0; }
// Спрайты вместо полос-треугольников (замер 9A/9B на железе: резкость TEST7 50,8, TEST8 45,4, спрайт на весь кадр 51,0): GU_TRIANGLE_STRIP в режиме 2D
// сэмплирует текстуру не точно по пикселю (интерполяция u,v по треугольнику даёт смещение, которое при NEAREST уходит на целый пиксель и вместе с ±¼ px
// мылит вдвое сильнее), а GU_SPRITES копирует тексель в тексель, как было в TEST7. Полосы по 64 px остаются (кэш текстур), плавный спад по высоте — тремя
// ступенями альфы. JITTER_SPRITES_OLD=1 — прежние треугольники
#ifndef JITTER_SPRITES_OLD
#define JITTER_SPRITES_OLD 0
#endif
typedef struct { float u, v; unsigned c; float x, y, z; } JitV;
static void jitDraw(int pct, int rows, float zq) {
  int ns = (SCR_W + 63) / 64;
  if (JITTER_SPRITES_OLD) {
    unsigned a1 = ((unsigned)(pct * 255 / 100) << 24) | 0xffffffu, a0 = 0x00ffffffu;
    int fadeEnd = rows, full = fadeEnd * 3 / 4;
    JitV *q = (JitV *)sceGuGetMemory((size_t)ns * 6 * sizeof(JitV));
    for (int k = 0; k < ns; k++) {
      float x0 = (float)(k * 64), x1 = (float)((k + 1) * 64 < SCR_W ? (k + 1) * 64 : SCR_W); JitV *v = q + 6 * k;
      int ys[3] = {0, full, fadeEnd}; unsigned cs[3] = {a1, a1, a0};
      for (int r = 0; r < 3; r++) { float y = (float)ys[r];
        v[2 * r] = (JitV){x0, y, cs[r], x0, y, zq}; v[2 * r + 1] = (JitV){x1, y, cs[r], x1, y, zq}; }
      sceGuDrawArray(GU_TRIANGLE_STRIP, GU_TEXTURE_32BITF | GU_COLOR_8888 | GU_VERTEX_32BITF | GU_TRANSFORM_2D, 6, 0, v);
    }
    return;
  }
  enum { NF = 8 };   // №511: спад высоты восемью ступенями по ~1/9 доли (было три по 1/4): горизонтального шва на небе не видно
  int full = rows * 3 / 4, step = (rows - full + NF - 1) / NF; if (step < 1) step = 1;
  int ys[NF + 2], al[NF + 1]; ys[0] = 0; ys[1] = full; al[0] = pct;
  for (int b = 1; b <= NF; b++) { ys[b + 1] = full + b * step; if (ys[b + 1] > rows || b == NF) ys[b + 1] = rows; al[b] = pct * (NF + 1 - b) / (NF + 1); }
  int nb = NF + 1; JitV *q = (JitV *)sceGuGetMemory((size_t)ns * nb * 2 * sizeof(JitV)); JitV *w = q;
  for (int k = 0; k < ns; k++) {
    float x0 = (float)(k * 64), x1 = (float)((k + 1) * 64 < SCR_W ? (k + 1) * 64 : SCR_W);
    for (int b = 0; b < nb; b++) {
      if (ys[b + 1] <= ys[b]) continue;
      unsigned c = ((unsigned)(al[b] * 255 / 100) << 24) | 0xffffffu;
      *w++ = (JitV){x0, (float)ys[b], c, x0, (float)ys[b], zq}; *w++ = (JitV){x1, (float)ys[b + 1], c, x1, (float)ys[b + 1], zq};
    }
  }
  sceGuDrawArray(GU_SPRITES, GU_TEXTURE_32BITF | GU_COLOR_8888 | GU_VERTEX_32BITF | GU_TRANSFORM_2D, (int)(w - q), 0, q);
}
// подмес по истории мира (сразу после неба, до динамики) и обновление истории: drawOff — смещение рисуемого буфера в VRAM
static int jitterWorld(unsigned drawOff) {
  if (!jitterOn || JITTER_OLD || !jitHist) { jitHave = 0; return 0; }
  int ok = jitOk && jitActive;   // подмес только в кадре со сдвигом
  float w = jitW;
  int rows = SCR_H * jitterCover / 100; if (rows > SCR_H) rows = SCR_H; rows &= ~1;
  int pct = (int)(jitterPct * w);
  if (ok && pct >= 3) {
    int nearMask = !JITTER_NEAR_OLD && jitNearZ > 0;   // тест глубины на GE: только пиксели дальше порога
    if (nearMask) { sceGuEnable(GU_DEPTH_TEST); sceGuDepthFunc(GU_GEQUAL); } else sceGuDisable(GU_DEPTH_TEST);
    sceGuDepthMask(GU_TRUE); sceGuDisable(GU_ALPHA_TEST); sceGuDisable(GU_FOG); sceGuDisable(GU_LIGHTING); sceGuDisable(GU_CULL_FACE);
    sceGuEnable(GU_TEXTURE_2D); sceGuEnable(GU_BLEND); sceGuBlendFunc(GU_ADD, GU_SRC_ALPHA, GU_ONE_MINUS_SRC_ALPHA, 0, 0);
    sceGuTexMode(GU_PSM_5650, 0, 0, 0); sceGuTexFlush();
    sceGuTexImage(0, 512, 512, BUF_W, (void *)((unsigned)sceGeEdramGetAddr() + JIT_HIST_OFF));
    sceGuTexFunc(GU_TFX_MODULATE, GU_TCC_RGBA); sceGuTexFilter(GU_NEAREST, GU_NEAREST); sceGuTexScale(1.f, 1.f); sceGuTexOffset(0.f, 0.f);
    jitDraw(pct, rows, nearMask ? (float)jitNearZ : 0.f);
    sceGuTexScale(128.f, 128.f); sceGuDisable(GU_BLEND); sceGuEnable(GU_DEPTH_TEST); sceGuDepthMask(GU_FALSE);
  }
  // история: мир после подмеса (копится), без машин и людей; только верхние rows строк
  sceGuCopyImage(GU_PSM_5650, 0, 0, SCR_W, rows, BUF_W, (void *)((unsigned)sceGeEdramGetAddr() + drawOff), 0, 0, BUF_W, (void *)((unsigned)sceGeEdramGetAddr() + JIT_HIST_OFF));
  sceGuTexSync();
  return 1;
}
// подмес прошлого кадра: prevOff — смещение показываемого буфера в VRAM; eye/fov — камера этого кадра
static int jitterBlend(unsigned prevOff, int fb16_, const float eye[3], float fov) {
  if (!jitterOn || JITTER_OLD || jitHist) { if (!jitHist) jitHave = 0; return 0; }   // jitHist — подмес уже сделан в jitterWorld
  float dx = eye[0] - jitEye[0], dy = eye[1] - jitEye[1], dz = eye[2] - jitEye[2];
  int ok = jitHave && dx * dx + dy * dy + dz * dz < 9.f && fabsf(fov - jitFov) < .02f;
  jitEye[0] = eye[0]; jitEye[1] = eye[1]; jitEye[2] = eye[2]; jitFov = fov; jitHave = 1;
  if (!ok) return 0;
  int fadeEnd = JITTER_STRIPS_OLD ? SCR_H : SCR_H * jitterCover / 100; if (fadeEnd > SCR_H) fadeEnd = SCR_H; fadeEnd &= ~1;
  sceGuDisable(GU_DEPTH_TEST); sceGuDepthMask(GU_TRUE); sceGuDisable(GU_ALPHA_TEST); sceGuDisable(GU_FOG); sceGuDisable(GU_LIGHTING); sceGuDisable(GU_CULL_FACE);
  sceGuEnable(GU_TEXTURE_2D); sceGuEnable(GU_BLEND); sceGuBlendFunc(GU_ADD, GU_SRC_ALPHA, GU_ONE_MINUS_SRC_ALPHA, 0, 0);
  sceGuTexMode(fb16_ ? GU_PSM_5650 : GU_PSM_8888, 0, 0, 0);
  sceGuTexImage(0, 512, 512, BUF_W, (void *)((unsigned)sceGeEdramGetAddr() + prevOff));
  sceGuTexFunc(GU_TFX_MODULATE, GU_TCC_RGBA); sceGuTexFilter(GU_NEAREST, GU_NEAREST); sceGuTexScale(1.f, 1.f); sceGuTexOffset(0.f, 0.f);
  if (JITTER_STRIPS_OLD) {   // прежний один спрайт на весь кадр (TEST7)
    JitV *q = (JitV *)sceGuGetMemory(2 * sizeof(JitV)); unsigned col = ((unsigned)(jitterPct * 255 / 100) << 24) | 0xffffffu;
    q[0] = (JitV){0.f, 0.f, col, 0.f, 0.f, 0.f}; q[1] = (JitV){(float)SCR_W, (float)SCR_H, col, (float)SCR_W, (float)SCR_H, 0.f};
    sceGuDrawArray(GU_SPRITES, GU_TEXTURE_32BITF | GU_COLOR_8888 | GU_VERTEX_32BITF | GU_TRANSFORM_2D, 2, 0, q);
  } else jitDraw(jitterPct, fadeEnd, 0.f);
  sceGuTexScale(128.f, 128.f); sceGuDisable(GU_BLEND); sceGuEnable(GU_DEPTH_TEST); sceGuDepthMask(GU_FALSE);
  return 1;
}

// Брифинг миссии: мир стоит (dt = 0), кадр мира снимается один раз в область истории джиттера и дальше только показывается (main_loop.h, bfOk_/bfSnap), рисуется одна карточка с руками №512.
#ifndef BRIEF_FREEZE_OLD
#define BRIEF_FREEZE_OLD BIS(9)
#endif
static int bfSnap, bfFrames; static float bfPose[6]; static unsigned bfBlits, bfCaptures, bfHides, pwFrames;
static void bfCopy(unsigned srcOff, unsigned dstOff) {   // 480x272 5650 из VRAM в VRAM (команда GE, порядок списка сохраняется)
  sceGuCopyImage(GU_PSM_5650, 0, 0, SCR_W, SCR_H, BUF_W, (void *)((unsigned)sceGeEdramGetAddr() + srcOff), 0, 0, BUF_W, (void *)((unsigned)sceGeEdramGetAddr() + dstOff));
  sceGuTexSync();
}
// Решение кадра брифинга (чистая функция: tests/brieffreeze/host.c проверяет её на хосте): base — брифинг на экране без паузы, магазина/будки/гардероба/комнаты/камеры гэга/облёта;
// closed — ирис закрыт целиком; snapOk — кадр 5650, джиттер-история доступна, ирис не на экране; haveSnap — снимок есть; poseDiff — сдвиг камеры с момента снимка; frames — кадров
// брифинга подряд (с учётом этого); pending — подгрузка клеток ещё идёт. 0 рисуем мир как прежде, 1 мир не рисуем (закрыт), 2 показываем снимок, 3 рисуем мир и снимаем его
#define BF_DRAW 0
#define BF_HIDE 1
#define BF_BLIT 2
#define BF_CAPTURE 3
static int bfDecide(int base, int closed, int snapOk, int haveSnap, float poseDiff, int frames, int pending) {
  if (!base) return BF_DRAW;
  if (closed) return BF_HIDE;
  if (!snapOk) return BF_DRAW;
  if (haveSnap && poseDiff <= .01f) return BF_BLIT;
  if (frames >= 3 && pending == 0) return BF_CAPTURE;
  return BF_DRAW;
}
