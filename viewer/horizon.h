// Горизонт: плоский однотонный силуэт дальнего города (слово Роба 16.10: «фасады как в вестернах, силуэт дома, маяк виден издалека»).
// Файл horizon.shr уровня (tools/horizon_export.py, HOR1): для клеток сетки заранее посчитан контур верхней кромки всего, что дальше дальности города (вектор: азимут + tan угла места).
// Рисуется лентой треугольников по цилиндру вокруг камеры (радиус HZ_R чуть дальше дальности города), без текстуры, без записи и проверки глубины, ДО подложки и города:
// ближний настоящий 3D проявляется поверх. Цвет — тон горизонта уровня (fogCol), притемнённый; вершины пересобираются только при смене клетки или fogCol.
// Цена: до ~300 вершин, один вызов GE. Выключено по умолчанию: «flag horizon 1/0» в сценарии или файл horizon рядом с EBOOT. HORIZON_OLD=1 — функция не рисует вовсе (прежнее)
#pragma once
#ifndef HORIZON_OLD
#define HORIZON_OLD 0
#endif
#define HZ_MAXV 1400
#define HZ_FADE 0.14f   // градиент: высота перехода в дымку под верхним краем контура, доля радиуса
#define HZ_MAXLM 16
#define HZ_SLICE 24   // столбцов контура за кадр при пересборке (≈ 4–8 кадров на клетку)
#define HZ_LM_HIDE 10.f   // карточка ориентира гаснет, когда до него ближе drawDist−10 м (настоящая башня к этому моменту уже в дымке дальнего края); перекрытие 10 м — без пустого кадра
#define HZ_LMV 64
#define HZ_INK 0.45f   // доля тёмного тона в цвете силуэта (0 — ровно fogCol, 1 — чёрный)
typedef struct { float cx, cz, ey; unsigned nv, off, p0, p1, p2; } HzCell;
typedef struct { unsigned c; float x, y, z; } HzVtx;
typedef struct { float cx, cz, y0, h; unsigned np, off, p0, p1; } HzLm;
static int horizonOn;
static unsigned char *hzData; static unsigned hzN, hzSize; static int hzLevel = -99; static float hzR = 260.f; static const HzCell *hzC; static const HzLm *hzL; static unsigned hzNL;
static unsigned hzUsAcc, hzUsN, hzUsMax;   // цена рисования (процессор), мкс: сумма, число кадров, максимум; строка HORIZON cost в журнале смоука раз в 30 кадров
static int hzCur = -1; static unsigned hzCol, hzFogB; static unsigned hzVerts, hzCalls, hzNv;   // последний кадр: вершин, вызовов
static HzVtx hzVb[2][HZ_MAXV] __attribute__((aligned(64)));   // два буфера ленты: рисуется активный, в другой порциями собирается новая (смена клетки без скачка кадра)
static int hzAct; static int hzBldCell = -1; static unsigned hzBldK, hzBldCol, hzBldFog;
static void horizonFree(void) { free(hzData); hzData = 0; hzN = 0; hzC = 0; hzL = 0; hzNL = 0; hzCur = -1; hzBldCell = -1; hzLevel = -99; }
static void horizonLoad(int level) {
  horizonFree(); hzLevel = level;   // одна попытка на уровень: нет файла — молча без горизонта
  char fn[256]; levelFile(fn, "horizon.shr");
  SceUID f = sceIoOpen(fn, PSP_O_RDONLY, 0); if (f < 0) return;
  int sz = (int)sceIoLseek(f, 0, PSP_SEEK_END); sceIoLseek(f, 0, PSP_SEEK_SET);
  if (sz < 32 || sz > (1 << 20)) { sceIoClose(f); return; }
  unsigned char *m = (unsigned char *)memalign(64, (size_t)sz);
  if (!m || sceIoRead(f, m, (SceSize)sz) != sz || memcmp(m, "HOR1", 4)) { sceIoClose(f); free(m); return; }
  sceIoClose(f);
  unsigned n = *(unsigned *)(m + 4); float r = *(float *)(m + 8);
  if (32 + 32ull * n > (unsigned)sz) { free(m); return; }
  for (unsigned i = 0; i < n; i++) { const HzCell *c = (const HzCell *)(m + 32) + i; if (c->nv < 2 || c->nv > HZ_MAXV / 4 || c->off + 4ull * c->nv > (unsigned)sz) { free(m); return; } }
  unsigned nl = *(unsigned *)(m + 12), lo = *(unsigned *)(m + 16);
  if (nl > HZ_MAXLM || (nl && lo + 32ull * nl > (unsigned)sz)) nl = 0;
  for (unsigned i = 0; i < nl; i++) { const HzLm *l = (const HzLm *)(m + lo) + i; if (l->np < 2 || l->np > HZ_LMV / 2 || l->off + 4ull * l->np > (unsigned)sz) { nl = 0; break; } }
  hzData = m; hzSize = (unsigned)sz; hzN = n; hzC = (const HzCell *)(m + 32); hzNL = nl; hzL = nl ? (const HzLm *)(m + lo) : 0; if (r > 50.f && r < 1000.f) hzR = r;
  if (smkOn) { char s[96]; snprintf(s, sizeof s, "HORIZON loaded level=%d cells=%u lm=%u bytes=%u\n", level, n, hzNL, (unsigned)sz); smkWrite(s); }
}
// лента по контуру клетки i: вершины в осях камеры (x, z на радиусе hzR; y — угол места × радиус), высота привязана к миру матрицей
// цвет дымки, в которую уходит дальний город: ровно тот, что идёт в sceGuFog города (cityFogColor, main_stream.h; при fogsky = fogCol, иначе groundCover.rgb)
static unsigned hzFogCol(void) { return cityFogColor(); }
static int hzMode(void) { return horizonOn == 6 ? 1 : horizonOn == 7 ? 4 : horizonOn == 8 ? 5 : horizonOn; }   // базовый цвет без учёта градиента
static int hzGrad(void) { return horizonOn >= 6 && horizonOn <= 8; }
#ifdef HORIZON_CONTRAST_OLD
#define HORIZON_CONTRAST_OLD_V 1
#else
#define HORIZON_CONTRAST_OLD_V 0
#endif
#ifndef HORIZON_GROUND_OLD
#define HORIZON_GROUND_OLD 0
#endif
#define HZ_GROUND_K 42u     // % яркости средней земли (текстуры в игре под тоном уровня темнее сырых палитр)
#define HZ_GROUND_FOG 12u   // % дымки в цвете земли ленты: даль чуть светлее ближней земли
// цвет низа ленты (дальняя земля): средняя земля 120-450 м из горизонта клетки (p0 = 0x00BBGGRR), смешанная с дымкой; нет данных — цвет дымки, как раньше
static unsigned hzGroundCol(const HzCell *c, unsigned fog) {
  if (HORIZON_GROUND_OLD || !c->p0) return 0xff000000u | (fog & 0xffffffu);
  unsigned g = c->p0, o = 0xff000000u;
  for (int sh = 0; sh <= 16; sh += 8) { unsigned gv = ((g >> sh) & 255u) * HZ_GROUND_K / 100u, fv = (fog >> sh) & 255u; o |= (((gv * (100u - HZ_GROUND_FOG) + fv * HZ_GROUND_FOG) / 100u) & 255u) << sh; }
  return o;
}
static unsigned horizonColor(void) {
  int m = hzMode();
  if (m != 1 && m != 4 && m != 5) return 0xffff00ffu;
  unsigned fc = hzFogCol(), fr = fc & 255u, fg = (fc >> 8) & 255u, fb = (fc >> 16) & 255u, r, g, b;
  if (m == 5) { unsigned sc = skyHorizonColor(), sr = sc & 255u, sg = (sc >> 8) & 255u, sb = (sc >> 16) & 255u; r = (fr * 6u + sr * 4u) / 10u; g = (fg * 6u + sg * 4u) / 10u; b = (fb * 6u + sb * 4u) / 10u;
#ifndef HORIZON_CONTRAST_OLD
    r = r * 38u / 100u + 8u; g = g * 40u / 100u + 12u; b = b * 45u / 100u + 40u;   // темнее и холоднее неба: на закате силуэт не тонет в небе (Роб, причал L3)
#else
    r = r * 9u / 10u; g = g * 9u / 10u; b = b * 9u / 10u;
#endif
  }
  else if (m == 4) { r = fr * 85u / 100u; g = fg * 85u / 100u; b = fb * 85u / 100u; }
  else { unsigned ink = 255u - (unsigned)(HZ_INK * 255.f); r = fr * ink / 255u; g = fg * ink / 255u; b = fb * ink / 255u; }
  return 0xff000000u | (b << 16) | (g << 8) | r;
}
// лента: две полосы по три ряда вершин (верх контура / переход / низ под землёй). Без градиента все ряды одного цвета. Полоса A: хранится в hzV[0..hzNv), полоса B — следом
// пересборка ленты клетки i в неактивный буфер порциями по HZ_SLICE столбцов (k0..k1); true — готово
static int horizonBuildSlice(int i, unsigned col, unsigned k0, unsigned k1) {
  const HzCell *c = &hzC[i]; const unsigned char *p = hzData + c->off; unsigned nv = c->nv; HzVtx *V = hzVb[hzAct ^ 1];
  unsigned colB = hzGrad() ? hzGroundCol(c, hzFogCol()) : col;
  if (k1 > nv) k1 = nv;
  for (unsigned k = k0; k < k1; k++) {
    unsigned short az = *(const unsigned short *)(p + 4 * k); short t = *(const short *)(p + 4 * k + 2);
    float a = (float)az * (6.2831853f / 65536.f), x = hzR * sinf(a), z = -hzR * cosf(a);
    float yt = horizonOn == 3 ? hzR * 0.2f : hzR * (float)t * (1.f / 16384.f), ym = yt - hzR * HZ_FADE, yb = -hzR * 0.5f;
    if (ym < yb || !hzGrad()) ym = yb;   // без градиента полоса A тянется от верха до низа
    unsigned colT = col; if (hzGrad() && !HORIZON_CONTRAST_OLD_V) { float tt = (float)t * (1.f / 16384.f), f = tt * (1.f / 0.05f); f = f < 0.f ? 0.f : f > 1.f ? 1.f : f; unsigned c0 = colB & 255u, c1 = (colB >> 8) & 255u, c2 = (colB >> 16) & 255u, d0 = col & 255u, d1 = (col >> 8) & 255u, d2 = (col >> 16) & 255u; unsigned q = (unsigned)(f * 256.f); colT = 0xff000000u | (((c2 * (256u - q) + d2 * q) >> 8) << 16) | (((c1 * (256u - q) + d1 * q) >> 8) << 8) | ((c0 * (256u - q) + d0 * q) >> 8); }   // выше линии горизонта глаза (дома, холмы) — тёмный силуэт, ниже (дальняя земля) — цвет дымки, без шва с землёй
    V[2 * k] = (HzVtx){colT, x, yt, z};       V[2 * k + 1] = (HzVtx){colB, x, ym, z};   // полоса A
    V[2 * nv + 2 * k] = (HzVtx){colB, x, ym, z}; V[2 * nv + 2 * k + 1] = (HzVtx){colB, x, yb, z};   // полоса B
  }
  return k1 >= nv;
}
// один шаг: если цель (клетка, цвет) не совпадает с рисуемой — начать/продолжить пересборку; первая лента уровня собирается за раз. Когда готова — смена буферов за кадр
static void horizonUpdate(int best, unsigned col) {
  unsigned fog = hzFogCol();
  if (hzCur == best && hzCol == col && hzFogB == fog) { hzBldCell = -1; return; }
  if (hzBldCell != best || hzBldCol != col || hzBldFog != fog) { hzBldCell = best; hzBldCol = col; hzBldFog = fog; hzBldK = 0; }
  unsigned nv = hzC[best].nv, step = hzCur < 0 ? nv : HZ_SLICE;
  if (horizonBuildSlice(best, col, hzBldK, hzBldK + step)) {
    hzAct ^= 1; hzNv = nv; hzCur = best; hzCol = col; hzFogB = fog; hzBldCell = -1;
    if (smkOn) { char s[128]; snprintf(s, sizeof s, "HORIZON cell=%d at=%.0f,%.0f ey=%.1f nv=%u col=%08x grad=%d\n", best, hzC[best].cx, hzC[best].cz, hzC[best].ey, nv, col, hzGrad()); smkWrite(s); }
  } else hzBldK += step;
}
// ориентиры: профиль вращения (радиус, высота) -> лента L,R вдоль высоты, лицом к камере на расстоянии не дальше drawDist+4 (дальше дальней плоскости вида не нарисовать), с тем же угловым размером (равномерный масштаб от глаза).
// Ближе drawDist−HZ_LM_HIDE не рисуем: там настоящая геометрия (карточка симметрична по оси, у настоящей башни пристройка с одной стороны: поверх неё карточка торчала бы до ~7 м)
static void horizonLmDraw(float ex, float ey, float ez, unsigned col) {
  for (unsigned q = 0; q < hzNL; q++) {
    const HzLm *l = &hzL[q]; float dx = l->cx - ex, dz = l->cz - ez, D = sqrtf(dx * dx + dz * dz);
    if (D < drawDist - HZ_LM_HIDE || D > 1500.f || D < 1.f) continue;
    float Dp = D < drawDist + 4.f ? D : drawDist + 4.f, s = Dp / D, ux = dx / D, uz = dz / D, rx = -uz, rz = ux;
    float bx = ux * Dp, bz = uz * Dp, by = (l->y0 - ey) * s;
    const unsigned char *pp = hzData + l->off; unsigned n = l->np;
    HzVtx *v = (HzVtx *)sceGuGetMemory(2 * n * sizeof(HzVtx));
    for (unsigned k = 0; k < n; k++) {
      float r = (float)*(const unsigned short *)(pp + 4 * k) * 0.01f * s, h = (float)*(const unsigned short *)(pp + 4 * k + 2) * 0.01f * s;
      v[2 * k] = (HzVtx){col, bx - rx * r, by + h, bz - rz * r}; v[2 * k + 1] = (HzVtx){col, bx + rx * r, by + h, bz + rz * r};
    }
    sceGuDrawArray(GU_TRIANGLE_STRIP, GU_COLOR_8888 | GU_VERTEX_32BITF | GU_TRANSFORM_3D, (int)(2 * n), 0, v); hzVerts += 2 * n; hzCalls++;
  }
}
static void horizonDraw(float ex, float ey, float ez) {
  unsigned t0_ = sceKernelGetSystemTimeLow();
  hzVerts = hzCalls = 0;   // счётчики кадра; hzNv — число вершин собранной ленты, живёт между кадрами
  if (HORIZON_OLD || !horizonOn || inRoom() || clearChk) return;
  if (hzLevel != gameLevel) horizonLoad(gameLevel);
  if (!hzN || geOver(GE_SOFT)) return;
  int best = 0; float bd = 1e30f;
  for (unsigned i = 0; i < hzN; i++) { float dx = hzC[i].cx - ex, dz = hzC[i].cz - ez, d = dx * dx + dz * dz; if (d < bd) { bd = d; best = (int)i; } }
  unsigned col = horizonColor();
  horizonUpdate(best, col);
  ScePspFMatrix4 m; memset(&m, 0, sizeof m); float k = (drawDist + 4.f) / hzR;   // дальняя плоскость вида = drawDist + 10: лента внутри неё, равномерный масштаб сохраняет углы контура
  m.x.x = m.z.z = m.y.y = k; m.w.w = 1.f; m.w.y = hzC[hzCur].ey - ey;   // мировая высота клетки относительно глаза (рисуется ещё прежняя клетка, пока новая собирается)
  sceGuDisable(GU_TEXTURE_2D); sceGuDisable(GU_BLEND); sceGuDisable(GU_ALPHA_TEST); sceGuDisable(GU_CULL_FACE); sceGuDisable(GU_FOG);
  sceGuEnable(GU_DEPTH_TEST); sceGuDepthMask(GU_FALSE);   // глубину пишем: небо рисуется последним (O_SKYLAST) только там, где глубины нет; лента на дальнем крае, город перекрывает её
  sceGuSetMatrix(GU_MODEL, &m);
  unsigned nv4 = 4 * hzNv; HzVtx *v = (HzVtx *)sceGuGetMemory(nv4 * sizeof(HzVtx)); memcpy(v, hzVb[hzAct], nv4 * sizeof(HzVtx));   // вершины в списке команд, как у подложки клеток (cellUnderlayDraw)
  sceGuDrawArray(GU_TRIANGLE_STRIP, GU_COLOR_8888 | GU_VERTEX_32BITF | GU_TRANSFORM_3D, (int)(2 * hzNv), 0, v);
  if (hzGrad()) sceGuDrawArray(GU_TRIANGLE_STRIP, GU_COLOR_8888 | GU_VERTEX_32BITF | GU_TRANSFORM_3D, (int)(2 * hzNv), 0, v + 2 * hzNv);   // без градиента вторая полоса целиком под землёй, не рисуем
  hzVerts = hzGrad() ? nv4 : 2 * hzNv; hzCalls = hzGrad() ? 2 : 1;
  if (hzNL) { ScePspFMatrix4 id; memset(&id, 0, sizeof id); id.x.x = id.y.y = id.z.z = id.w.w = 1.f; sceGuSetMatrix(GU_MODEL, &id); horizonLmDraw(ex, ey, ez, col); }
  resetState();
  unsigned us_ = sceKernelGetSystemTimeLow() - t0_; hzUsAcc += us_; if (us_ > hzUsMax) hzUsMax = us_;
  if (++hzUsN >= 30) { if (smkOn) { char s[128]; snprintf(s, sizeof s, "HORIZON cost level=%d avg_us=%u max_us=%u frames=%u verts=%u calls=%u drawDist=%.0f\n", gameLevel, hzUsAcc / hzUsN, hzUsMax, hzUsN, hzVerts, hzCalls, drawDist); smkWrite(s); } hzUsAcc = hzUsN = hzUsMax = 0; }
}
