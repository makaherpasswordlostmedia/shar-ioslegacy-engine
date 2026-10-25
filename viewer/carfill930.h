// №930 (Роб 24.10: «NPC-машины по городу сделать мультяшнее», «текстуры машин сильно грузят движок»): куски машин NPC (трафик, стоящие, машины миссий) в мультике (Textures Off): треугольники с ровной областью
// текстуры (краска из образца 64×64, дверные панели, борта, остов huskA) рисуются БЕЗ текстуры цветом треугольника (боковые файлы carflat930.bin у трафика и carflatm930.bin у пакета машин миссий,
// tools/car_flat.py --sidecar; цвет прошёл ту же цветокоррекцию мультика toneColorRGB и умножен на запечённую светотень вершин), треугольники с рисунком (фары, решётки, номер, швы, ступицы колёс)
// остаются текстурой. Ступень 2: цвет кладётся В ВЕРШИНЫ НА МЕСТЕ, без копий, и треугольники куска переставляются в самом куске (заливка вперёд, рисунок в хвост): кусок рисуется двумя вызовами
// (первые K треугольников без текстуры, остальные с родной). Оригинал при смене тона, при Textures On и для машины игрока читается из файла (traffic.shr / msncars-lN.shr) по требованию; боковой файл
// читается по требованию (у машин миссий только блок своей модели) и в памяти не держится. Постоянно в памяти — таблица кусков (≈ 0,2 КБ на набор). Машина игрока (в том числе после пересадки) рисуется оригиналом с текстурой всегда.
// CARFILL930_OLD=1 / файл carfill930old рядом с EBOOT / «flag carfill930 0» — как до правки
#ifndef CARFILL930_OLD
#define CARFILL930_OLD 0
#endif
#define CF_COLD __attribute__((noinline, optimize("Os")))   // редкие пути (перекраска при загрузке, смене тона, пересадке): размер важнее скорости — кучу считаем по КБ
#define CF_SETS 8      // 0 — трафик, 1…6 — слоты моделей машин миссий
#define CF_PCMAX 80    // кусков в наборе трафика не больше (до 70)
#define CF_PMMAX 40    // кусков в модели машины миссии не больше (до 36)
#define CF_TRIMAX 1600 // треугольников в куске не больше (перестановка на месте, битовая карта на стеке)
typedef struct { const TrPiece *pc; unsigned np; unsigned char *vt; unsigned fileV; int mis, mem, nbits; unsigned key; char name[16]; unsigned char bits[CF_PCMAX / 8]; unsigned short *kt; unsigned char **orig; } CfSet;   // mem: 0 — вершины как в файле, 1 — цвет и порядок положены в вершины; kt[кусок] — число треугольников заливки (первые в куске), таблица из пула cfKt; orig[кусок] — копия оригинала для машины игрока (по требованию)
static unsigned short cfKt0[CF_PCMAX], cfKtM[CF_SETS - 1][CF_PMMAX];   // пул таблиц K: у трафика до 80 кусков, у моделей миссий до 40
static CfSet cfSet[CF_SETS]; static const char *cfMisPack;   // cfMisPack — путь пакета машин миссий (mcrPath), пути остальных файлов собираются levelFile при чтении, в памяти не держатся
static void cfPath(char *o, int k, int side) { if (side) levelFile(o, k ? "carflatm930.bin" : "carflat930.bin"); else if (k) snprintf(o, 256, "%s", cfMisPack ? cfMisPack : ""); else levelFile(o, "traffic.shr"); }
static int carFillOn = !CARFILL930_OLD, carFillPlayer;   // carFillPlayer > 0 — рисуется машина игрока (пересадка): с текстурой
static unsigned cfDraws, cfBakes, cfRestores, cfVerts, cfChanged, cfOrigBytes, cfTris, cfTexTris;   // служебно (строка CARFILL, гейт): cfTris — треугольников заливки в нарисованных кусках, cfTexTris — оставшихся с текстурой
static unsigned cfSig(const TrPiece *p, unsigned n) { unsigned s = 2166136261u; for (unsigned i = 0; i < n; i++) { s = (s ^ (unsigned)p[i].tex) * 16777619u; s = (s ^ p[i].ni) * 16777619u; s = (s ^ (unsigned)p[i].flags) * 16777619u; } return s; }
static inline int cfBit(const CfSet *s, unsigned i) { return i < CF_PCMAX && (s->bits[i >> 3] >> (i & 7)) & 1; }   // у модели миссии пометки только ниже CF_PMMAX (cfApply)
static inline unsigned cfRd32(const unsigned char *p) { unsigned v; memcpy(&v, p, 4); return v; }   // файл читается без невыровненных слов (на PSP lw по нечётному адресу — исключение; эмулятор прощает)
static SceUID cfMisFd = -1; static unsigned cfMisFsz;   // боковой файл машин миссий открыт один раз на уровень (открытие карты памяти дороже чтения), закрывается вместе с уровнем (carFillFree)
static void carFillSetFree(int k) {
  CfSet *s = &cfSet[k]; if (s->orig) { for (unsigned i = 0; i < s->np; i++) free(s->orig[i]); free(s->orig); } memset(s, 0, sizeof *s);
}
static void carFillFree(void) { for (int k = 0; k < CF_SETS; k++) carFillSetFree(k); if (cfMisFd >= 0) { sceIoClose(cfMisFd); cfMisFd = -1; cfMisFsz = 0; } }
// боковой файл набора читается потоком через буфер 6 КБ на стеке, без выделения кучи (прежние выделения целого блока 20–30 КБ поднимали высоту кучи на время загрузки, а чтение мелкими кусками по 12–576 Б
// стоило на каждое обращение к карте памяти отдельного вызова). У трафика файл целиком, у машин миссий — блок своей модели. Запись (кратна 4 Б): [кусок u32][треугольников u32][K u32][3 байта RGB на каждую из 3K вершин
// треугольников заливки][перестановка u16 × треугольников, если K меньше числа треугольников: новое место j берёт старый треугольник perm[j]]
#define CF_IOB 6144
typedef struct { SceUID f; unsigned nFill, pos, end, fsz, base, len; int keep; unsigned char b[CF_IOB] __attribute__((aligned(64))); } CfRd;   // b — окно файла [base, base+len)
static const unsigned char *cfGet(CfRd *r, unsigned off, unsigned n) {   // n ≤ CF_IOB; указатель на байты файла [off, off+n) в окне до следующего вызова; 0 — не прочиталось
  if (n > CF_IOB || off + n > r->fsz) return 0;
  if (!(r->len && off >= r->base && off + n <= r->base + r->len)) { unsigned want = r->fsz - off < CF_IOB ? r->fsz - off : CF_IOB; r->len = 0;
    if (sceIoLseek32(r->f, (int)off, PSP_SEEK_SET) != (int)off || sceIoRead(r->f, r->b, (int)want) != (int)want) return 0; r->base = off; r->len = want; }
  return r->b + (off - r->base);
}
CF_COLD static int cfSideOpen(int k, CfRd *r) {
  const CfSet *s = &cfSet[k]; char pth[256]; int sz, ok = 0; r->keep = 0;
  if (s->mis && cfMisFd >= 0) { r->f = cfMisFd; sz = (int)cfMisFsz; r->keep = 1; }
  else { cfPath(pth, s->mis, 1); r->f = sceIoOpen(pth, PSP_O_RDONLY, 0); if (r->f < 0) return 0; sz = sceIoLseek32(r->f, 0, PSP_SEEK_END); if (s->mis && sz > 16) { cfMisFd = r->f; cfMisFsz = (unsigned)sz; r->keep = 1; } }
  r->nFill = r->pos = r->end = r->base = r->len = 0; r->fsz = sz > 0 ? (unsigned)sz : 0; const unsigned char *h;
  if (sz > 16 && sz < (8 << 20)) {
    if (!s->mis) {   // 'CFL2', число кусков, подпись, число записей
      if ((h = cfGet(r, 0, 16)) && !memcmp(h, "CFL2", 4) && cfRd32(h + 4) == s->np && cfRd32(h + 8) == cfSig(s->pc, s->np)) { r->nFill = cfRd32(h + 12); r->pos = 16; r->end = r->fsz; ok = 1; }
    } else if ((h = cfGet(r, 0, 8)) && !memcmp(h, "CFM2", 4)) {   // 'CFM2', число моделей, по модели 36 Б: имя[16], число кусков, подпись, число записей, смещение блока, размер блока
      unsigned nm = cfRd32(h + 4), sig = cfSig(s->pc, s->np);
      for (unsigned m = 0; m < nm && m < 128 && !ok; m++) { const unsigned char *e = cfGet(r, 8 + 36 * m, 36); if (!e) break;
        if (!strncmp((const char *)e, s->name, 15) && cfRd32(e + 16) == s->np && cfRd32(e + 20) == sig) { unsigned off = cfRd32(e + 28), len = cfRd32(e + 32); if (off + (unsigned long long)len <= r->fsz) { r->nFill = cfRd32(e + 24); r->pos = off; r->end = off + len; ok = 1; } break; } }
    }
  }
  if (!ok) { if (!r->keep) sceIoClose(r->f); r->f = -1; return 0; }
  return 1;
}
CF_COLD static int cfPermOk(const unsigned short *pm, unsigned ntri) {   // перестановка действительно взаимно однозначная (иначе кусок не трогаем: на месте её не применить)
  unsigned char seen[CF_TRIMAX / 8]; memset(seen, 0, (ntri + 7) / 8);
  for (unsigned i = 0; i < ntri; i++) { unsigned v = pm[i]; if (v >= ntri || (seen[v >> 3] >> (v & 7) & 1)) return 0; seen[v >> 3] |= (unsigned char)(1u << (v & 7)); }
  return 1;
}
CF_COLD static void cfPermute(unsigned char *d, unsigned vs, const unsigned short *pm, unsigned ntri) {   // по циклам, один временный треугольник на стеке: место j получает старый треугольник pm[j]
  unsigned tb = 3 * vs; unsigned char seen[CF_TRIMAX / 8], tmp[48]; memset(seen, 0, (ntri + 7) / 8);
  for (unsigned i = 0; i < ntri; i++) { if ((seen[i >> 3] >> (i & 7)) & 1) continue;
    memcpy(tmp, d + i * tb, tb); unsigned j = i;
    for (;;) { seen[j >> 3] |= (unsigned char)(1u << (j & 7)); unsigned sj = pm[j];
      if (sj == i) { memcpy(d + j * tb, tmp, tb); break; }
      memcpy(d + j * tb, d + sj * tb, tb); j = sj; } }
}
// запись набора: разметка кусков (markOnly: заполняется таблица; вместе с bake — и сразу перекраска) и перекраска: bake 1 — порядок и цвет в вершины на месте, 0 — вершины как в файле; fromFile 1 — оригинал куска сперва читается из файла
CF_COLD static void cfApply(int k, int bake, int fromFile, int markOnly) {
  CfSet *s = &cfSet[k]; CfRd rd, *r = &rd; if (!s->np || !cfSideOpen(k, r)) return;
  SceUID fd = -1; if (fromFile && !markOnly) { char pth[256]; cfPath(pth, s->mis, 0); fd = sceIoOpen(pth, PSP_O_RDONLY, 0); }
  unsigned char last[3] = {0, 0, 0}, tc[4] = {0, 0, 0, 255}; unsigned short pm[CF_TRIMAX]; int haveLast = 0; unsigned pos = r->pos; if (markOnly) s->nbits = 0;
  for (unsigned f = 0; f < r->nFill; f++) {
    const unsigned char *hp; if (pos + 12 > r->end || !(hp = cfGet(r, pos, 12))) break;
    unsigned pi = cfRd32(hp), ntri = cfRd32(hp + 4), K = cfRd32(hp + 8); if (K > ntri || ntri > 65535) break;   // порча файла: дальше не читаем
    unsigned rec = (12 + 9 * K + (K < ntri ? 2 * ntri : 0) + 3) & ~3u, rpos = pos; if (pos + rec > r->end) break; pos += rec;
    if (pi >= s->np || pi >= (s->mis ? CF_PMMAX : CF_PCMAX) || K == 0 || ntri > CF_TRIMAX) continue;   // слишком большой кусок только пропускается
    const TrPiece *p = &s->pc[pi]; if (p->ni != (int)ntri * 3 || !(p->flags & 16) || (p->flags & (1 | 2 | 4 | (1u << 24) | (1u << 26)))) continue;   // без индексов; не прозрачные, не сложение, не полосы (данные Мака тоже их не берут)
    int needPm = K < ntri && (markOnly || bake);
    if (markOnly) { if (needPm) { const unsigned char *pp = cfGet(r, rpos + 12 + 9 * K, 2 * ntri); if (!pp) continue; memcpy(pm, pp, 2 * ntri); if (!cfPermOk(pm, ntri)) continue; }
      s->bits[pi >> 3] |= (unsigned char)(1u << (pi & 7)); s->kt[pi] = (unsigned short)K; s->nbits++; if (!bake) continue; }   // разметка; bake — и сразу перекраска (вершины в памяти ещё оригинальные)
    else if (!cfBit(s, pi) || s->kt[pi] != K) continue;
    else if (needPm) { const unsigned char *pp = cfGet(r, rpos + 12 + 9 * K, 2 * ntri); if (!pp) continue; memcpy(pm, pp, 2 * ntri); }
    unsigned vs = (p->flags & 32) ? 12 : 16, v12 = vs == 12; unsigned char *d = s->vt + p->off;
    if (fd >= 0) { if (sceIoLseek32(fd, (int)(s->fileV + p->off), PSP_SEEK_SET) < 0 || sceIoRead(fd, d, (int)(p->ni * vs)) != (int)(p->ni * vs)) continue; }   // оригинал из файла
    if (bake) { if (K < ntri) cfPermute(d, vs, pm, ntri);
      for (unsigned t0 = 0; t0 < K; t0 += 640) { unsigned nt = K - t0 < 640 ? K - t0 : 640; const unsigned char *cb = cfGet(r, rpos + 12 + 9 * t0, 9 * nt); if (!cb) break;
        for (unsigned v = 0; v < 3 * nt; v++) { const unsigned char *c = cb + v * 3;
          if (!haveLast || memcmp(c, last, 3)) { memcpy(last, c, 3); tc[0] = c[0]; tc[1] = c[1]; tc[2] = c[2]; tc[3] = 255; toneColorRGB(tc); haveLast = 1; }
          unsigned char *ov = d + (size_t)(3 * t0 + v) * vs; unsigned char b0[3] = {ov[4], ov[5], ov[6]};
          if (v12) { unsigned short cc; memcpy(&cc, ov + 4, 2); unsigned rr = cc & 31, gg = (cc >> 5) & 63, bb = cc >> 11; rr = (rr * tc[0] + 127) / 255; gg = (gg * tc[1] + 127) / 255; bb = (bb * tc[2] + 127) / 255; cc = (unsigned short)(rr | gg << 5 | bb << 11); memcpy(ov + 4, &cc, 2); }
          else { ov[4] = (unsigned char)((ov[4] * tc[0] + 127) / 255); ov[5] = (unsigned char)((ov[5] * tc[1] + 127) / 255); ov[6] = (unsigned char)((ov[6] * tc[2] + 127) / 255); }
          cfVerts++; if (ov[4] != b0[0] || ov[5] != b0[1] || (!v12 && ov[6] != b0[2])) cfChanged++; } } }
    sceKernelDcacheWritebackRange(d, p->ni * vs); }
  if (fd >= 0) sceIoClose(fd); if (!r->keep) sceIoClose(r->f);
}
static inline unsigned cfKey(void) { return toneKey() ^ ((unsigned)toneToonTexPct() << 8) ^ 0x40000000u; }
static inline int cfWant(void) { return carFillOn && flatOn; }
static void carFillLoad(const Traffic *t) {   // трафик: набор 0; вершины сейчас такие же, как в файле; в мультике сразу перекрашиваются (под экраном загрузки, а не в кадре)
  carFillFree(); if (CARFILL930_OLD || t->hd->nPiece > CF_PCMAX) return;   // (уровень сменился: наборы и открытый файл прежнего уровня — прочь)
  CfSet *s = &cfSet[0]; s->kt = cfKt0; s->pc = t->piece; s->np = t->hd->nPiece; s->vt = (unsigned char *)t->vert; s->fileV = t->hd->vertOff; s->mis = 0;
  int w = cfWant(); cfApply(0, w, 0, 1); if (w && s->nbits) { s->mem = 1; s->key = cfKey(); cfBakes++; }
}
static void carFillModelLoad(int slot, const char *name, const TrPiece *pc, unsigned np, const unsigned char *vt, const char *packPath, unsigned fileV) {   // модель машины миссии прочитана в слот
  if (slot < 0 || slot >= CF_SETS - 1) return; carFillSetFree(1 + slot); if (CARFILL930_OLD || np > CF_PMMAX) return;
  cfMisPack = packPath; CfSet *s = &cfSet[1 + slot]; s->kt = cfKtM[slot]; s->pc = pc; s->np = np; s->vt = (unsigned char *)vt; s->fileV = fileV; s->mis = 1; snprintf(s->name, sizeof s->name, "%.15s", name);
  int w = cfWant(); cfApply(1 + slot, w, 0, 1); if (!s->nbits) carFillSetFree(1 + slot); else if (w) { s->mem = 1; s->key = cfKey(); cfBakes++; }
}
// приводит вершины набора k к нужному виду: want — цвет и порядок в вершинах (мультик, заливка); иначе оригинал. Вершины меняются только здесь, до рисования кусков набора в кадре (видеочип предыдущего кадра закончил: sceGuSync в конце кадра)
static void carFillSync(int k, int want) {
  CfSet *s = &cfSet[k]; unsigned key = cfKey();
  if (want) { if (s->mem && s->key == key) return; cfApply(k, 1, s->mem, 0); s->mem = 1; s->key = key; cfBakes++; }
  else if (s->mem) { cfApply(k, 0, 1, 0); s->mem = 0; cfRestores++; }
}
// оригинал куска для машины игрока, пока вершины набора перекрашены: копия из файла по требованию
CF_COLD static const unsigned char *cfOrigOf(CfSet *s, unsigned pi) {
  const TrPiece *p = &s->pc[pi]; unsigned vs = (p->flags & 32) ? 12 : 16, n = p->ni * vs;
  if (!s->orig) s->orig = calloc(s->np, sizeof *s->orig); if (!s->orig) return 0;
  if (!s->orig[pi]) { unsigned char *b = malloc(n); if (!b) return 0; char pth[256]; cfPath(pth, s->mis, 0); SceUID fd = sceIoOpen(pth, PSP_O_RDONLY, 0);
    if (fd < 0 || sceIoLseek32(fd, (int)(s->fileV + p->off), PSP_SEEK_SET) < 0 || sceIoRead(fd, b, (int)n) != (int)n) { if (fd >= 0) sceIoClose(fd); free(b); return 0; }
    sceIoClose(fd); s->orig[pi] = b; cfOrigBytes += n; }
  return s->orig[pi];
}
CF_COLD static unsigned cfHash(void) {   // служебно (гейт): FNV по цвету вершин кусков набора 0 — «как в файле» и «перекрашено» различаются
  unsigned h = 2166136261u; const CfSet *s = &cfSet[0];
  for (unsigned i = 0; i < s->np && i < CF_PCMAX; i++) if (cfBit(s, i)) { const TrPiece *p = &s->pc[i]; unsigned vs = (p->flags & 32) ? 12 : 16; for (int v = 0; v < p->ni; v++) { const unsigned char *o = s->vt + p->off + (size_t)v * vs; h = (h ^ o[4]) * 16777619u; h = (h ^ o[5]) * 16777619u; if (vs == 16) h = (h ^ o[6]) * 16777619u; } }
  return h;
}
// кусок машины NPC (в массиве куска трафика или модели миссии): -> число K первых треугольников, которые рисуются без текстуры (цвет уже в вершинах; остальные треугольники куска — родной текстурой); 0 — кусок как есть.
// *verts заменяется оригиналом для машины игрока
static inline int carFillPick(const TrPiece *p, const void **verts) {
  if (CARFILL930_OLD) return 0;
  for (int k = 0; k < CF_SETS; k++) { CfSet *s = &cfSet[k]; if (!s->nbits || p < s->pc || p >= s->pc + s->np) continue;
    unsigned pi = (unsigned)(p - s->pc); if (!cfBit(s, pi)) return 0;
    int want = cfWant(); carFillSync(k, want);   // состояние набора меняется при первом куске набора в кадре, раньше любого рисования его вершин (в том числе машины игрока)
    if (carFillPlayer) { if (s->mem) { const unsigned char *o = cfOrigOf(s, pi); if (o) *verts = o; } return 0; }   // машина игрока: оригинал и текстура
    if (!want || !s->mem) return 0;
    cfDraws++; cfTris += s->kt[pi]; cfTexTris += (unsigned)p->ni / 3 - s->kt[pi]; return s->kt[pi]; }
  return 0;
}
