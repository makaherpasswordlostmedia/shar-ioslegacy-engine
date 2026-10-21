// №800 (Роб 18.10: «не то чтобы бумага — ощущение старого телевизора: виньетка и очень размытый внутренний свет, светлее заливки,
// как выгоревшая плёнка»): строка Old TV на странице CARTOON (действует в режиме мультика). Поверх мира, под интерфейсом, три
// полноэкранных квада без копий кадра (на GE ~0,2 мс, на процессоре — ничего):
//   1) плёнка — кадр чуть к тёплому кремовому (OT_FADE): чёрное приподнято, контраст мягче — «выгоревшая»;
//   2) свечение — кремовое сложением, к центру ярче, к краю в ноль (картинка 64×64, линейная выборка — очень мягко);
//   3) виньетка — тёмная тёплая к углам (тон туши мультика), по форме кадра 16:9.
// Картинки считаются один раз (оперативная память, 64×64 8888). Служебно: «flag oldtv 0/1». OLDTV_OLD=1 — прохода нет
#ifndef OLDTV_OLD
#define OLDTV_OLD 0
#endif
#define OT_N 64
#define OT_FADE .07f                 // доля кремового в кадре (плёнка)
#define OT_FADE_ABGR 0x00CCE6F4u     // кремовый #F4E6CC
#define OT_GLOW_A .12f               // свечение в центре (доля сложения; .16 на снимке 18.10 — молочно)
#define OT_GLOW_ABGR 0x00D8EEFFu     // светлый тёплый #FFEED8
#define OT_VIG_A .70f                // виньетка в углах (.58 на снимке 18.10 — едва видна)
#define OT_VIG_ABGR 0x00241A20u      // тёплый тёмный #201A24 (тон туши) — до №828
// №828 (Роб 18.10: «виньетка через чур серая — в выгоревший фиолетовый, к краям чёрный; комплементарный к асфальту приятный фиолетовый»): цвет
// виньетки по радиусу — от выгоревшего фиолетового #6B4E86 к чернильно-фиолетовому #160A22 у самых краёв. OT_VIG828_OLD=1 — серо-тёплая, как TEST35
#ifndef OT_VIG828_OLD
#define OT_VIG828_OLD 0
#endif
#define OT_VIG_MID_ABGR 0x00864E6Bu  // #6B4E86
#define OT_VIG_EDGE_ABGR 0x00220A16u // #160A22
static unsigned otGlow[OT_N * OT_N] __attribute__((aligned(16))), otVig[OT_N * OT_N] __attribute__((aligned(16)));
static int otReady, otForce = -1;   // otForce: служебный флаг сценария (-1 — по настройке)
static float otSmooth(float a, float b, float x) { float t = (x - a) / (b - a); t = t < 0.f ? 0.f : t > 1.f ? 1.f : t; return t * t * (3.f - 2.f * t); }
static void otInit(void) {
  for (int y = 0; y < OT_N; y++) for (int x = 0; x < OT_N; x++) {
    float u = (x + .5f) / OT_N * 2.f - 1.f, v = (y + .5f) / OT_N * 2.f - 1.f, r = sqrtf(u * u + v * v);   // эллипс по кадру (картинка растянута на экран)
    float g = 1.f - otSmooth(0.f, 1.05f, r); g = g * g;
    float w = otSmooth(.5f, 1.25f, r);
    otGlow[y * OT_N + x] = ((unsigned)(g * OT_GLOW_A * 255.f + .5f) << 24) | OT_GLOW_ABGR;
    unsigned vc = OT_VIG_ABGR;
    if (!OT_VIG828_OLD) { float e = otSmooth(.85f, 1.35f, r); vc = 0;   // к краю — чернильный
      for (int c = 0; c < 24; c += 8) { float a0 = (float)((OT_VIG_MID_ABGR >> c) & 255u), a1 = (float)((OT_VIG_EDGE_ABGR >> c) & 255u); vc |= (unsigned)(a0 + (a1 - a0) * e + .5f) << c; } }
    otVig[y * OT_N + x] = ((unsigned)(w * OT_VIG_A * 255.f + .5f) << 24) | vc;
  }
  sceKernelDcacheWritebackRange(otGlow, sizeof otGlow); sceKernelDcacheWritebackRange(otVig, sizeof otVig); otReady = 1;
}
static void otQuad(const unsigned *tex, unsigned col) {
  typedef struct { float u, v; unsigned c; short x, y, z, pad; } OtV;
  OtV *q = (OtV *)sceGuGetMemory(2 * sizeof(OtV));
  q[0].u = 0.f; q[0].v = 0.f; q[1].u = OT_N; q[1].v = OT_N; q[0].c = q[1].c = col;
  q[0].x = 0; q[0].y = 0; q[1].x = SCR_W; q[1].y = SCR_H; q[0].z = q[1].z = 0; q[0].pad = q[1].pad = 0;
  if (tex) { sceGuEnable(GU_TEXTURE_2D); sceGuTexMode(GU_PSM_8888, 0, 0, 0); sceGuTexImage(0, OT_N, OT_N, OT_N, tex);
             sceGuTexFunc(GU_TFX_MODULATE, GU_TCC_RGBA); sceGuTexFilter(GU_LINEAR, GU_LINEAR); sceGuTexWrap(GU_CLAMP, GU_CLAMP); sceGuTexScale(1.f, 1.f); sceGuTexOffset(0.f, 0.f); }
  else sceGuDisable(GU_TEXTURE_2D);
  sceGuDrawArray(GU_SPRITES, GU_TEXTURE_32BITF | GU_COLOR_8888 | GU_VERTEX_16BIT | GU_TRANSFORM_2D, 2, 0, q);
}
// №830: сила эффекта — настройка Old TV 1..10 (10 %..100 %), все три слоя пропорционально; служебный flag oldtv N — сила N (1 — 100 %, как раньше)
// №838 (тур TEST36 на PSP: gesync +0,5–0,8 мс): плёнка и виньетка — один полноэкранный проход (два смешивания подряд = одно с общей альфой
// A = 1 − (1 − a_плёнки)(1 − a_виньетки) и цветом (c_пл·a_пл·(1 − a_в) + c_в·a_в)/A); картинка пересчитывается при смене силы. OT_ONEPASS_OLD=1 — два прохода
#ifndef OT_ONEPASS_OLD
#define OT_ONEPASS_OLD 0
#endif
static unsigned otMix[OT_N * OT_N] __attribute__((aligned(16))); static float otMixK = -1.f;
static void otMixBuild(float k) {
  float af = OT_FADE * k;
  for (int i = 0; i < OT_N * OT_N; i++) { unsigned v = otVig[i]; float av = (float)(v >> 24) / 255.f * k, A = 1.f - (1.f - af) * (1.f - av); unsigned c = 0;
    for (int ch = 0; ch < 24; ch += 8) { float cf = (float)((OT_FADE_ABGR >> ch) & 255u), cv = (float)((v >> ch) & 255u);
      float x = A > 1e-4f ? (cf * af * (1.f - av) + cv * av) / A : 0.f; c |= (unsigned)(x > 255.f ? 255.f : x + .5f) << ch; }
    otMix[i] = ((unsigned)(A * 255.f + .5f) << 24) | c; }
  sceKernelDcacheWritebackRange(otMix, sizeof otMix); otMixK = k;
}
static float oldTvK(void) { int v = otForce >= 0 ? (otForce > 0 ? (otForce == 1 ? 10 : otForce) : 0) : cfg.oldTv; return v <= 0 ? 0.f : (v > 10 ? 10 : v) * .1f; }
static int oldTvOn(void) { return !OLDTV_OLD && oldTvK() > 0.f && skinToonEnabled(); }
static void oldTvDraw(void) {
  if (!oldTvOn()) return;
  if (!otReady) otInit();
  sceGuDisable(GU_DEPTH_TEST); sceGuDepthMask(GU_TRUE); sceGuDisable(GU_ALPHA_TEST); sceGuDisable(GU_FOG); sceGuEnable(GU_BLEND);
  sceGuBlendFunc(GU_ADD, GU_SRC_ALPHA, GU_ONE_MINUS_SRC_ALPHA, 0, 0);
  float k = oldTvK(); unsigned ka = (unsigned)(k * 255.f + .5f) << 24;   // №830: сила — альфа вершин (картинки умножаются на неё)
  if (!OT_ONEPASS_OLD) {   // №838: свечение, потом плёнка с виньеткой одним проходом
    if (otMixK != k) otMixBuild(k);
    sceGuBlendFunc(GU_ADD, GU_SRC_ALPHA, GU_FIX, 0, 0xffffffff);
    otQuad(otGlow, ka | 0xffffffu);
    sceGuBlendFunc(GU_ADD, GU_SRC_ALPHA, GU_ONE_MINUS_SRC_ALPHA, 0, 0);
    otQuad(otMix, 0xffffffffu);
  } else {
  otQuad(0, ((unsigned)(OT_FADE * k * 255.f + .5f) << 24) | OT_FADE_ABGR);   // 1) плёнка
  sceGuBlendFunc(GU_ADD, GU_SRC_ALPHA, GU_FIX, 0, 0xffffffff);
  otQuad(otGlow, ka | 0xffffffu);                                        // 2) свечение
  sceGuBlendFunc(GU_ADD, GU_SRC_ALPHA, GU_ONE_MINUS_SRC_ALPHA, 0, 0);
  otQuad(otVig, ka | 0xffffffu);                                         // 3) виньетка
  }
  sceGuEnable(GU_TEXTURE_2D); resetState();
}
