// №770 (Роб 18.10 и 23.10: «там, где сверху из труб капает кислота — сделать просто векторный свет: цилиндр, как будто сверху вниз светит, сквозь
// него проезжаем, как конус; лагающие полупрозрачные капли убрать — они сильно бьют текстуры»). Капли — квады-билборды объектов Anim в зонах уровня
// (L1: три струи «deathgoop» по 15 м у проезда D5-8, две трубы «goop» АЭС со всплеском, струйка внутри АЭС). Места — из диска (tools/drip770.py ->
// drip770.bin в папке уровня). Квады капель (и свечения сложением: с №839 — мигающая звезда-блик 15 м) в DRIP_R м от этих мест не рисуются; на месте каждой струи — столб света ровного цвета
// (прямоугольник лицом к камере вокруг вертикали, сверху ярче, к полу слабее) и эллипс на полу — один вызов без текстуры, как векторный конус фонаря.
// Без коллизии (проезд сквозь). DRIP770_OLD=1 / «flag drip 0» — как было
#ifndef DRIP770_OLD
#define DRIP770_OLD 0
#endif
#define DRIP_R 1.5f        // м: квады капель вокруг места струи (струя и всплеск у её подножия)
#define DRIP_MAX 32
#define DRIP_A 70.f        // альфа столба у трубы (из 255)
#define DRIP_A_LOW 22.f    // у пола
#define DRIP_POOL_A 50.f
#define DRIP_W_K .28f      // радиус столба — доля ширины квада данных (струя 7,9 м -> 1,1 м)
#define DRIP_D 90.f        // дальность
static int dripOn = !DRIP770_OLD;
static struct { float x, z, top, r, gy; uint32_t rgb; } dripC[DRIP_MAX]; static unsigned dripN; static int dripGround;
static float dripPt[DRIP_MAX * 4][2]; static unsigned dripPtN;
static void dripFree(void) { dripN = dripPtN = 0; dripGround = 0; }
static void dripLoad(void) {
  dripFree(); if (DRIP770_OLD) return;
  char fn[256]; levelFile(fn, "drip770.bin"); SceUID f = sceIoOpen(fn, PSP_O_RDONLY, 0); if (f < 0) return;
  uint32_t h[2]; struct { float x, y, z; uint32_t col; float w, h; } r;
  if (sceIoRead(f, h, 8) == 8 && h[0] == 0x31505244u && h[1] < 256u)   // 'DRP1'
    for (unsigned i = 0; i < h[1] && sceIoRead(f, &r, sizeof r) == (int)sizeof r; i++) {
      if (dripPtN < DRIP_MAX * 4) { dripPt[dripPtN][0] = r.x; dripPt[dripPtN][1] = r.z; dripPtN++; }
      unsigned k = 0; while (k < dripN && (dripC[k].x - r.x) * (dripC[k].x - r.x) + (dripC[k].z - r.z) * (dripC[k].z - r.z) > DRIP_R * DRIP_R) k++;
      float top = r.y + r.h * .5f, rad = r.w * DRIP_W_K; if (rad > 2.f) rad = 2.f; if (rad < .5f) rad = .5f;
      if (k == dripN) { if (dripN >= DRIP_MAX) continue; dripN++; dripC[k].x = r.x; dripC[k].z = r.z; dripC[k].top = top; dripC[k].r = rad; dripC[k].rgb = 0x50FF6Eu; dripC[k].gy = -1e30f; }   // ABGR: кислотно-зелёный (110, 255, 80)
      else { if (top > dripC[k].top) dripC[k].top = top; if (rad > dripC[k].r) dripC[k].r = rad; }
    }
  sceIoClose(f);
  if (smkOn) { char s_[96]; snprintf(s_, sizeof s_, "DRIP770 level=%d quads=%u columns=%u\n", gameLevel, dripPtN, dripN); smkWrite(s_); }
}
static int dripSkipBill(const float *v, uint32_t bfl) {   // квад капли рядом с местом струи — и картинка, и свечение сложением (с №839 оно рисовалось звездой-бликом 15 м)
  (void)bfl; if (!dripOn || !dripPtN) return 0;
  float cx = (v[0] + v[3] + v[6] + v[9]) * .25f, cz = (v[2] + v[5] + v[8] + v[11]) * .25f;
  for (unsigned i = 0; i < dripPtN; i++) { float dx = cx - dripPt[i][0], dz = cz - dripPt[i][1]; if (dx * dx + dz * dz < DRIP_R * DRIP_R) return 1; }
  return 0;
}
static void dripDraw(float ex, float ey, float ez, int inR) {
  if (!dripOn || !dripN || inR) return;
  if (!dripGround && haveCol) { dripGround = 1; for (unsigned k = 0; k < dripN; k++) { float y_, n_[3]; dripC[k].gy = colGround(&world, dripC[k].x, dripC[k].z, dripC[k].top - .2f, dripC[k].top - 40.f, &y_, n_) ? y_ : dripC[k].top - 15.f; } }
  typedef struct { unsigned c; float x, y, z; } DV;
  unsigned b0 = ggVbUsed, nv = 0; DV *q = (DV *)ggVbAlloc(dripN * (6 + 16 * 3) * sizeof(DV)); if (!q) return;
  for (unsigned k = 0; k < dripN; k++) {
    float dx = dripC[k].x - ex, dz = dripC[k].z - ez, d = sqrtf(dx * dx + dz * dz); if (d > DRIP_D) continue;
    float fade = d > DRIP_D - 15.f ? (DRIP_D - d) / 15.f : 1.f, r = dripC[k].r, rx = d > .01f ? -dz / d * r : r, rz = d > .01f ? dx / d * r : 0.f;   // поперёк взгляда
    if (d < r + .5f) fade *= (d - r * .5f) / (r * .5f + .5f) > 0.f ? (d - r * .5f) / (r * .5f + .5f) : 0.f;   // камера внутри столба — гаснет (как конус у глаза)
    if (fade <= 0.f) continue;
    unsigned cT = ((unsigned)(DRIP_A * fade + .5f) << 24) | dripC[k].rgb, cB = ((unsigned)(DRIP_A_LOW * fade + .5f) << 24) | dripC[k].rgb;
    float T = dripC[k].top, B = dripC[k].gy + .02f, X = dripC[k].x, Z = dripC[k].z;
    float P[4][3] = {{X - rx, T, Z - rz}, {X + rx, T, Z + rz}, {X - rx, B, Z - rz}, {X + rx, B, Z + rz}};
    static const unsigned char tri[6] = {0, 1, 2, 2, 1, 3};
    for (int m = 0; m < 6; m++) { DV *o = &q[nv++]; int c_ = tri[m]; o->c = c_ < 2 ? cT : cB; o->x = P[c_][0]; o->y = P[c_][1]; o->z = P[c_][2]; }
    unsigned cp = ((unsigned)(DRIP_POOL_A * fade + .5f) << 24) | dripC[k].rgb; float pr = r * 1.4f;
    float dxp = ex - X, dyp = ey - B, dzp = ez - Z, dd = sqrtf(dxp * dxp + dyp * dyp + dzp * dzp), kk = dd > .3f ? .15f / dd : .5f; if (kk > .5f) kk = .5f;   // пятно ближе к глазу (не тонет в полу)
    for (int j = 0; j < 16; j++) { float a0 = 6.2831853f * j / 16.f, a1 = 6.2831853f * (j + 1) / 16.f;
      float Pp[3][3] = {{X, B, Z}, {X + pr * cosf(a0), B, Z + pr * sinf(a0)}, {X + pr * cosf(a1), B, Z + pr * sinf(a1)}};
      for (int m = 0; m < 3; m++) { DV *o = &q[nv++]; o->c = cp; o->x = Pp[m][0] + (ex - Pp[m][0]) * kk; o->y = Pp[m][1] + (ey - Pp[m][1]) * kk; o->z = Pp[m][2] + (ez - Pp[m][2]) * kk; } }
  }
  if (!nv) return;
  ggVbWriteback(b0);
  ScePspFMatrix4 I; memset(&I, 0, sizeof I); I.x.x = I.y.y = I.z.z = I.w.w = 1.f; sceGuSetMatrix(GU_MODEL, &I);
  sceGuDisable(GU_TEXTURE_2D); sceGuDisable(GU_ALPHA_TEST); sceGuEnable(GU_BLEND); sceGuBlendFunc(GU_ADD, GU_SRC_ALPHA, GU_ONE_MINUS_SRC_ALPHA, 0, 0);
  sceGuDepthMask(GU_TRUE); setCull(0); sceGuEnable(GU_FOG);
  sceGuDrawArray(GU_TRIANGLES, GU_COLOR_8888 | GU_VERTEX_32BITF | GU_TRANSFORM_3D, (int)nv, 0, q);
  sceGuEnable(GU_TEXTURE_2D); resetState();
}
