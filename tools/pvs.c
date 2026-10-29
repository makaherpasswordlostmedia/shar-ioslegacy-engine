// pvs.c: offline PVS (potentially visible set) for SHR7 level files, like Crash on PS1.
//
// For every 20x20 m grid cell it lists the city pieces that can be visible from any chase-camera
// eye inside the cell. Eyes: 5x5 xz samples per cell (edges included), per sample every walkable
// heightmap layer (nearest non-empty heightmap cell within 6 m), eye heights layer + {1.2, 3.5, 6.5} m.
// Per eye a 6-face cube map is software-rasterized: opaque pieces (flags&3 == 0) write depth + piece
// id front to back (pieces whose bbox is already hidden are skipped, exact); every piece seen in the id
// buffer is visible; every other piece in range (alpha/blend pieces never occlude) is then tested
// against that depth with CONSERVATIVE rasterization: any pixel its triangles touch, nearest depth
// inside that pixel. So sub-pixel props count as visible unless their pixel is covered by a nearer
// occluder at the pixel centre; tiny near props must never pop, and the lists grow only a little.
// Conservative choices (the actual camera is between the sampled eyes):
//   range 115 + 5 m (sphere distance <= the engine's bbox distance); queries use the near index list up
//   to 50 + 5 m sphere distance (far list is a subset of it); occluders use the far list when the BBOX
//   distance (the engine's LOD metric) exceeds 50 - 5 m (fewer triangles = less occlusion); occluder geometry
//   closer than 1.0 m is ignored (engine near plane 0.7 m clips it), query near plane 0.3 m.
// Optional lossy --min-contrib N: drop a piece from a cell if from every eye it is beyond fog start
// (60 m) and never covers more than N fog-weighted cube pixels (normalized to 256 px/face).
//
// Build:  cc -O3 -o tools/pvs tools/pvs.c -lm
// Usage:  tools/pvs IN.shr [OUT.shr] [--res N] [--samples N] [--dilate] [--min-contrib N] [--threads N]
//         (OUT defaults to IN; written via temp file + rename; an existing PVS section is replaced)
//         --res 256 (cube face), --samples 5 (NxN eyes per cell), --dilate (union with 8 neighbours)
// Debug:  tools/pvs IN.shr --exact EYES.txt [--res 512]
//         EYES.txt = lines "x y z"; prints "eye piece pixels" for every piece visible from each eye
//         (center-sampled, engine LOD and draw distance, no margins) -> used by tools/pvs_check.py
//
// Section (appended 16-aligned, offset patched into header @88):
//   "PVS1", float ox, oz, cell, u32 W, H, poolCount, pad  | {u32 start, count}[W*H] | u16 pool[poolCount]
//   count 0xFFFFFFFF = no data (engine falls back to frustum-only). Lists sorted ascending.
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
#include <pthread.h>
#include <stdatomic.h>
#include <time.h>
#include <unistd.h>

typedef struct { float bb[6]; int32_t tex; uint32_t flags, nv, ni, owner; float ox, oy, oz, sc; uint32_t off, nf, cell, pad[2]; } Rec;
typedef struct { float bb[6]; uint32_t first, n, owner, off, size, pad; } CellRec;
_Static_assert(sizeof(Rec) == 80, "Rec must be 80 bytes");
_Static_assert(sizeof(CellRec) == 48, "CellRec must be 48 bytes");

typedef struct {
  float bb[6], sbb[6], c[3], rad;   // bb: stored bbox grown by the decoded vertices; sbb: stored bbox (engine uses it)
  int city, opaque, nv, ni, nf;
  float *v;                 // nv*3 world-space
  uint16_t *idx, *fidx;     // near / far triangle lists
} Piece;

// ---- configuration ----------------------------------------------------------------------------
static int RES = 256;                    // cube face resolution
static float NEARQ = 0.3f;               // near plane for visibility queries
static float NEARO = 1.0f;               // occluders closer than this don't occlude (engine near = 0.7)
static const float NEARE = 0.7f;         // engine near plane (exact mode occluders)
static float DRAW = 115.f, RMARGIN = 5.f;   // engine draw distance; + margin for camera between samples
static float LOD = 50.f, LODM = 5.f;        // engine LOD distance; queries use near list up to LOD+LODM
                                            // (sphere dist), occluders use far list beyond LOD-LODM (bbox
                                            // dist, as the engine) -> both conservative
static const float GUARD = 4.f;          // guard band (in face half-widths) before side-plane clipping
static float PCELL = 20.f, PMARGIN = 10.f, LRAD = 6.f;
static int SAMPLES = 5;
static float EYEH[8] = {1.2f, 3.5f, 6.5f}; static int NEYEH = 3;
static int LOWEST_ONLY = 0;              // experiment: only the lowest heightmap layer per sample
static float FOG0 = 60.f;                // engine fog start (fog ends at DRAW)
static float MINC = 0.f;                 // --min-contrib: drop pieces that are never nearer than FOG0 and never
                                         // cover more than MINC fog-weighted pixels (at 256 px/face); 0 = off

// ---- level ------------------------------------------------------------------------------------
static uint8_t *file; static size_t fileSize, baseSize; static int orderedNew;   // orderedNew: клетки после PVS1 (shr_order.py)
static Piece *P; static int NP;
static int *cityIdx; static int NCITY;
// правка 95 (L1 F11-2): регионы оригинала — секция REG1 (tools/regions_export.py), хвост 'REGF' прямо перед PVS1. Куски
// регионов, которых оригинал с клетки не держит («декорации издали» соседних районов), не попадают в список клетки и не
// заслоняют (движок их там не рисует: viewer/main.c regEye). Сетка REG1 по умолчанию совпадает с сеткой PVS; иначе
// клетка PVS берёт объединение масок перекрытых клеток REG1 (и для списка, и для заслона — проще, чуть менее строго)
static const uint16_t *REGM; static uint32_t REGW, REGH, REGN; static float REGOX, REGOZ, REGCELL;
static uint8_t *PREG;   // регион + 1 на кусок (0 — рисуется всегда)
static size_t regEnd;   // конец данных перед PVS1 (REGF — 16 Б перед ним); при orderedNew baseSize — весь файл, а REGF всё равно перед PVS1
static void regFind(void) {
  if (regEnd < 48 || memcmp(file + regEnd - 16, "REGF", 4)) return;
  uint32_t at; memcpy(&at, file + regEnd - 12, 4);
  if ((uint64_t)at + 32 > regEnd || memcmp(file + at, "REG1", 4)) return;
  uint32_t h[4]; float f[3]; memcpy(h, file + at + 4, 16); memcpy(f, file + at + 20, 12);
  if (h[1] == 0 || h[1] > 16 || !h[2] || !h[3] || f[2] <= 0 ||
      (uint64_t)at + 32 + 16ull * h[1] + 2ull * h[2] * h[3] > regEnd) { fprintf(stderr, "REG1: bad section, ignored\n"); return; }
  REGN = h[1]; REGW = h[2]; REGH = h[3]; REGOX = f[0]; REGOZ = f[1]; REGCELL = f[2];
  REGM = (const uint16_t *)(file + at + 32 + 16 * REGN);
}
static unsigned regAt(float x, float z) {
  if (!REGM) return 0xFFFFu;
  int gx = (int)floorf((x - REGOX) / REGCELL), gz = (int)floorf((z - REGOZ) / REGCELL);
  if (gx < 0 || gz < 0 || gx >= (int)REGW || gz >= (int)REGH) return 0xFFFFu;
  return REGM[(size_t)gz * REGW + gx];
}
static unsigned regRect(float x0, float z0, float x1, float z1) {   // объединение масок клеток REG1, перекрытых прямоугольником
  if (!REGM) return 0xFFFFu;
  unsigned m = 0; float e = 1e-3f;
  int ax = (int)floorf((x0 + e - REGOX) / REGCELL), bx = (int)floorf((x1 - e - REGOX) / REGCELL);
  int az = (int)floorf((z0 + e - REGOZ) / REGCELL), bz = (int)floorf((z1 - e - REGOZ) / REGCELL);
  for (int gz = az; gz <= bz; gz++)
    for (int gx = ax; gx <= bx; gx++) m |= regAt(REGOX + (gx + .5f) * REGCELL, REGOZ + (gz + .5f) * REGCELL);
  return m;
}
static int regOk(int k, unsigned m) { return !PREG[k] || ((m >> (PREG[k] - 1)) & 1u); }
static const int16_t *HM; static int HW, HH; static float HOX, HOZ, HCELL;
static int GW, GH; static float GOX, GOZ;
static int maxNV;

enum { M_OCC, M_QUERY, M_COUNT };
typedef struct { float x, y, z; } SV;       // screen x, y (pixels), z = 1/w
typedef struct { float u, v, w; } FV;

typedef struct {
  float *zb; uint16_t *ib; float *hz; int T;
  float *tv;
  float *bd;              // per piece: eye -> stored bbox distance (the engine's LOD/range metric, planes mode)
  uint8_t *vis;           // per piece: visible (current cell / eye)
  float *mind, *best;     // per piece: nearest distance / best contribution over the cell's eyes
  int *list; float *dist; uint8_t *mask; int16_t (*rect)[6][4]; float (*nz)[6];
  uint32_t *cnt;          // exact mode pixel counts
  struct DK *dk;
  long long tris, eyes, culled, dropped, regdrop;
} Ctx;

static const int WA[6] = {0, 0, 1, 1, 2, 2}, UA[6] = {2, 2, 0, 0, 0, 0}, VA[6] = {1, 1, 2, 2, 1, 1};

static inline FV toFace(int f, const float *p) {
  FV o; o.u = p[UA[f]]; o.v = p[VA[f]]; o.w = (f & 1) ? -p[WA[f]] : p[WA[f]]; return o;
}

// ---- rasterizer -------------------------------------------------------------------------------
// mode M_OCC: center-sampled, depth write + id; M_QUERY: conservative coverage + conservative
// (nearest-in-pixel) depth, returns 1 on first pixel not behind the depth buffer; M_COUNT: center
// sampled, returns number of pixels not behind the depth buffer.
static inline long rast(const int mode, float *restrict zb, uint16_t *restrict ib, const int R, SV a, SV b, SV c, uint16_t id) {
  double x0 = a.x, y0 = a.y, x1 = b.x, y1 = b.y, x2 = c.x, y2 = c.y;
  double minx = fmin(x0, fmin(x1, x2)), maxx = fmax(x0, fmax(x1, x2));
  double miny = fmin(y0, fmin(y1, y2)), maxy = fmax(y0, fmax(y1, y2));
  if (maxx < 0 || maxy < 0 || minx >= R || miny >= R) return 0;
  const int cons = mode == M_QUERY;
  float zmax = fmaxf(a.z, fmaxf(b.z, c.z));
  double det = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0);
  if (fabs(det) < 1e-9) {                      // degenerate (edge-on) triangle
    if (!cons) return 0;
    int px0 = (int)fmax(0, floor(minx)), px1 = (int)fmin(R - 1, floor(maxx));
    int py0 = (int)fmax(0, floor(miny)), py1 = (int)fmin(R - 1, floor(maxy));
    for (int py = py0; py <= py1; py++)
      for (int px = px0; px <= px1; px++) if (zmax >= zb[py * R + px]) return 1;
    return 0;
  }
  double zA = ((b.z - a.z) * (y2 - y0) - (c.z - a.z) * (y1 - y0)) / det;
  double zB = ((x1 - x0) * (c.z - a.z) - (x2 - x0) * (b.z - a.z)) / det;
  double s = det > 0 ? -1 : 1, A[3], B[3], C[3], off[3];
  const double ex[3][4] = {{x0, y0, x1, y1}, {x1, y1, x2, y2}, {x2, y2, x0, y0}};
  for (int e = 0; e < 3; e++) {
    A[e] = s * (ex[e][3] - ex[e][1]); B[e] = -s * (ex[e][2] - ex[e][0]);
    C[e] = -(A[e] * ex[e][0] + B[e] * ex[e][1]);
    off[e] = cons ? 0.5 * (fabs(A[e]) + fabs(B[e])) : 0;
  }
  int py0, py1, pxlo, pxhi;
  if (cons) { py0 = (int)fmax(0, floor(miny)); py1 = (int)fmin(R - 1, floor(maxy));
              pxlo = (int)fmax(0, floor(minx)); pxhi = (int)fmin(R - 1, floor(maxx)); }
  else { py0 = (int)fmax(0, ceil(miny - .5)); py1 = (int)fmin(R - 1, floor(maxy - .5)); pxlo = 0; pxhi = R - 1; }
  const float zc = cons ? (float)(0.5 * (fabs(zA) + fabs(zB))) : 0.f, fzA = (float)zA;
  long count = 0;
  for (int py = py0; py <= py1; py++) {
    double yc = py + .5, lo = pxlo - 1.0, hi = pxhi + 2.0;
    int empty = 0;
    for (int e = 0; e < 3; e++) {
      double k = B[e] * yc + C[e] + off[e];
      if (A[e] > 1e-12) { double t = -k / A[e]; if (t > lo) lo = t; }
      else if (A[e] < -1e-12) { double t = -k / A[e]; if (t < hi) hi = t; }
      else if (k < 0) { empty = 1; break; }
    }
    if (empty || lo > hi) continue;
    int px0 = (int)ceil(lo - .5), px1 = (int)floor(hi - .5);
    if (px0 < pxlo) px0 = pxlo; if (px1 > pxhi) px1 = pxhi;
    if (px0 > px1) continue;
    float zr = (float)(a.z + zA * (.5 - x0) + zB * (yc - y0));
    float *zrow = zb + py * R;
    if (mode == M_OCC) {
      uint16_t *irow = ib + py * R;
      for (int px = px0; px <= px1; px++) { float z = zr + fzA * px; if (z > zrow[px]) { zrow[px] = z; irow[px] = id; } }
    } else if (mode == M_QUERY) {
      for (int px = px0; px <= px1; px++) { float z = fminf(zr + fzA * px + zc, zmax); if (z >= zrow[px]) return 1; }
    } else {
      for (int px = px0; px <= px1; px++) { float z = zr + fzA * px; if (z >= zrow[px] * (1.f - 1e-5f)) count++; }
    }
  }
  return count;
}

static int clipPoly(FV *v, int n, float nearw) {
  FV tmp[16]; FV *src = v, *dst = tmp;
  for (int pl = 0; pl < 5; pl++) {
    int m = 0;
    for (int i = 0; i < n; i++) {
      FV A = src[i], B = src[(i + 1) % n];
      float da, db;
      switch (pl) {
        case 0: da = A.w - nearw; db = B.w - nearw; break;
        case 1: da = GUARD * A.w - A.u; db = GUARD * B.w - B.u; break;
        case 2: da = GUARD * A.w + A.u; db = GUARD * B.w + B.u; break;
        case 3: da = GUARD * A.w - A.v; db = GUARD * B.w - B.v; break;
        default: da = GUARD * A.w + A.v; db = GUARD * B.w + B.v; break;
      }
      if (da >= 0) dst[m++] = A;
      if ((da >= 0) != (db >= 0)) {
        float t = da / (da - db);
        dst[m].u = A.u + (B.u - A.u) * t; dst[m].v = A.v + (B.v - A.v) * t; dst[m].w = A.w + (B.w - A.w) * t;
        if (pl == 0) dst[m].w = nearw;
        m++;
      }
    }
    n = m; if (!n) return 0;
    FV *t = src; src = dst; dst = t;
  }
  if (src != v) memcpy(v, src, n * sizeof(FV));
  return n;
}

// one triangle on the faces in fm. Returns hit (M_QUERY) or pixel count (M_COUNT).
static long tri(Ctx *X, const int mode, const float *p0, const float *p1, const float *p2, unsigned fm, float nearw, uint16_t id) {
  const int R = RES; long total = 0;
  for (int f = 0; f < 6; f++) {
    if (!(fm >> f & 1)) continue;
    FV q[16]; q[0] = toFace(f, p0); q[1] = toFace(f, p1); q[2] = toFace(f, p2);
    if (q[0].w < nearw && q[1].w < nearw && q[2].w < nearw) continue;
    if (q[0].u > q[0].w && q[1].u > q[1].w && q[2].u > q[2].w) continue;
    if (-q[0].u > q[0].w && -q[1].u > q[1].w && -q[2].u > q[2].w) continue;
    if (q[0].v > q[0].w && q[1].v > q[1].w && q[2].v > q[2].w) continue;
    if (-q[0].v > q[0].w && -q[1].v > q[1].w && -q[2].v > q[2].w) continue;
    int n = 3, in = 1;
    for (int k = 0; k < 3; k++)
      if (q[k].w < nearw || fabsf(q[k].u) > GUARD * q[k].w || fabsf(q[k].v) > GUARD * q[k].w) in = 0;
    if (!in && (n = clipPoly(q, 3, nearw)) < 3) continue;
    SV s[16];
    for (int k = 0; k < n; k++) {
      float iw = 1.f / q[k].w;
      s[k].x = (q[k].u * iw * .5f + .5f) * R; s[k].y = (q[k].v * iw * .5f + .5f) * R; s[k].z = iw;
    }
    float *zb = X->zb + (size_t)f * R * R; uint16_t *ib = X->ib + (size_t)f * R * R;
    for (int k = 1; k + 1 < n; k++) {
      if (mode == M_OCC) rast(M_OCC, zb, ib, R, s[0], s[k], s[k + 1], id);
      else if (mode == M_QUERY) { if (rast(M_QUERY, zb, ib, R, s[0], s[k], s[k + 1], id)) return 1; }
      else total += rast(M_COUNT, zb, ib, R, s[0], s[k], s[k + 1], id);
    }
  }
  return total;
}

// faces touched by piece k's bbox; per face: pixel rect + nearest 1/w. Returns mask.
static unsigned faceMask(Ctx *X, int k, const float *e, float nearw) {
  const Piece *p = &P[k]; const int R = RES;
  float lo[3], hi[3]; unsigned m = 0;
  for (int i = 0; i < 3; i++) { lo[i] = p->bb[i] - e[i]; hi[i] = p->bb[3 + i] - e[i]; }
  for (int f = 0; f < 6; f++) {
    int a = WA[f]; float wmin = (f & 1) ? -hi[a] : lo[a], wmax = (f & 1) ? -lo[a] : hi[a];
    if (wmax < nearw) continue;
    float umin = lo[UA[f]], umax = hi[UA[f]], vmin = lo[VA[f]], vmax = hi[VA[f]];
    if (umin > wmax || -umax > wmax || vmin > wmax || -vmax > wmax) continue;
    int16_t *r = X->rect[k][f];
    if (wmin >= nearw) {
      float u0 = umin / (umin >= 0 ? wmax : wmin), u1 = umax / (umax >= 0 ? wmin : wmax);
      float v0 = vmin / (vmin >= 0 ? wmax : wmin), v1 = vmax / (vmax >= 0 ? wmin : wmax);
      // +-1 px: vertex projection rounds differently from this bbox projection, and conservative
      // coverage also takes a pixel whose edge only touches the triangle
      float x0 = floorf((u0 * .5f + .5f) * R) - 1, x1 = floorf((u1 * .5f + .5f) * R) + 1;
      float y0 = floorf((v0 * .5f + .5f) * R) - 1, y1 = floorf((v1 * .5f + .5f) * R) + 1;
      if (x1 < 0 || y1 < 0 || x0 > R - 1 || y0 > R - 1) continue;
      r[0] = (int16_t)fmaxf(0, x0); r[1] = (int16_t)fmaxf(0, y0); r[2] = (int16_t)fminf(R - 1, x1); r[3] = (int16_t)fminf(R - 1, y1);
      X->nz[k][f] = 1.f / wmin;
    } else { r[0] = r[1] = 0; r[2] = r[3] = R - 1; X->nz[k][f] = 1.f / nearw; }
    m |= 1u << f;
  }
  return m;
}

static void buildHZ(Ctx *X) {
  const int R = RES, T = X->T;
  for (int f = 0; f < 6; f++)
    for (int ty = 0; ty < T; ty++)
      for (int tx = 0; tx < T; tx++) {
        float mn = 1e30f; const float *zb = X->zb + (size_t)f * R * R + ty * 8 * R + tx * 8;
        for (int y = 0; y < 8; y++) for (int x = 0; x < 8; x++) if (zb[y * R + x] < mn) mn = zb[y * R + x];
        X->hz[(f * T + ty) * T + tx] = mn;
      }
}
static unsigned hzTest(Ctx *X, int k, unsigned fm) {
  const int T = X->T; unsigned out = 0;
  for (int f = 0; f < 6; f++) {
    if (!(fm >> f & 1)) continue;
    const int16_t *r = X->rect[k][f]; float nz = X->nz[k][f] * (1.f + 1e-5f);
    int hit = 0;
    for (int ty = r[1] / 8; ty <= r[3] / 8 && !hit; ty++)
      for (int tx = r[0] / 8; tx <= r[2] / 8; tx++) if (X->hz[(f * T + ty) * T + tx] <= nz) { hit = 1; break; }
    if (hit) out |= 1u << f;
  }
  return out;
}

static void xform(Ctx *X, const Piece *p, const float *e) {
  for (int i = 0; i < p->nv; i++) {
    X->tv[i * 3] = p->v[i * 3] - e[0]; X->tv[i * 3 + 1] = p->v[i * 3 + 1] - e[1]; X->tv[i * 3 + 2] = p->v[i * 3 + 2] - e[2];
  }
}

// gather candidate pieces for an eye; returns count in X->list
static int gather(Ctx *X, const float *e, const int *cand, int ncand, float range) {
  int n = 0;
  for (int j = 0; j < ncand; j++) {
    int k = cand[j]; const Piece *p = &P[k];
    float dx = p->c[0] - e[0], dy = p->c[1] - e[1], dz = p->c[2] - e[2];
    float d = sqrtf(dx * dx + dy * dy + dz * dz) - p->rad;
    if (d > range) continue;
    unsigned m = faceMask(X, k, e, NEARQ);
    if (!m) continue;
    float bx = fmaxf(0, fmaxf(p->sbb[0] - e[0], e[0] - p->sbb[3])), by = fmaxf(0, fmaxf(p->sbb[1] - e[1], e[1] - p->sbb[4]));
    float bz = fmaxf(0, fmaxf(p->sbb[2] - e[2], e[2] - p->sbb[5]));
    X->mask[k] = (uint8_t)m; X->dist[k] = d; X->bd[k] = sqrtf(bx * bx + by * by + bz * bz); X->list[n++] = k;
  }
  return n;
}

typedef struct DK { float d; int k; } DK;
static int cmpDK(const void *a, const void *b) { float x = ((const DK *)a)->d, y = ((const DK *)b)->d; return x < y ? -1 : x > y; }

// opaque pieces front to back; from time to time the tile depth pyramid is rebuilt and pieces whose
// bbox is entirely behind it are skipped (exact: none of their pixels could pass the depth test).
// LOD by bbox distance like the engine (planes mode: far list when bbox distance > 50 m): the sphere
// distance is smaller than the bbox distance, so choosing by it could occlude with near-only triangles
// that the engine does not draw at that distance.
static void renderOccluders(Ctx *X, const float *e, int n, float lodFar, float nearw) {
  const size_t N = (size_t)6 * RES * RES;
  memset(X->zb, 0, N * sizeof(float)); memset(X->ib, 0xff, N * sizeof(uint16_t));
  int m = 0;
  for (int j = 0; j < n; j++) { int k = X->list[j]; if (P[k].opaque) { X->dk[m].d = X->dist[k]; X->dk[m].k = k; m++; } }
  qsort(X->dk, m, sizeof(DK), cmpDK);
  int next = 16, hzValid = 0;
  for (int j = 0; j < m; j++) {
    if (j == next) { buildHZ(X); hzValid = 1; next *= 2; }
    int k = X->dk[j].k; const Piece *p = &P[k];
    unsigned fm = X->mask[k];
    if (hzValid && !(fm = hzTest(X, k, fm))) { X->culled++; continue; }
    int far = X->bd[k] > lodFar; const uint16_t *ix = far ? p->fidx : p->idx; int cnt = far ? p->nf : p->ni;
    if (cnt <= 0) continue;
    xform(X, p, e);
    for (int t = 0; t < cnt; t += 3)
      tri(X, M_OCC, X->tv + ix[t] * 3, X->tv + ix[t + 1] * 3, X->tv + ix[t + 2] * 3, fm, nearw, (uint16_t)k);
    X->tris += cnt / 3;
  }
}

static inline float fogW(float d) { return d <= FOG0 ? 1.f : d >= DRAW ? 0.f : (DRAW - d) / (DRAW - FOG0); }
static inline void seen(Ctx *X, int k, float contrib) {
  X->vis[k] = 1;
  if (X->dist[k] < X->mind[k]) X->mind[k] = X->dist[k];
  if (contrib > X->best[k]) X->best[k] = contrib;
}
static inline int settled(Ctx *X, int k) {   // nothing more to learn about piece k in this cell
  return X->vis[k] && (MINC <= 0 || X->mind[k] <= FOG0 || X->best[k] >= MINC);
}

// PVS mode: union visibility from eye e into X->vis (+ nearest distance and best fog-weighted
// pixel contribution, used only by --min-contrib)
static void eyePVS(Ctx *X, const float *e, const int *cand, int ncand) {
  int n = gather(X, e, cand, ncand, DRAW + RMARGIN);
  renderOccluders(X, e, n, LOD - LODM, NEARO);
  const size_t N = (size_t)6 * RES * RES;
  const float norm = (256.f / RES) * (256.f / RES);
  if (MINC > 0) {
    for (size_t i = 0; i < N; i++) if (X->ib[i] != 0xffff) X->cnt[X->ib[i]]++;
    for (int j = 0; j < n; j++) { int k = X->list[j]; if (X->cnt[k]) { seen(X, k, X->cnt[k] * norm * fogW(X->dist[k])); X->cnt[k] = 0; } }
  } else
    for (size_t i = 0; i < N; i++) if (X->ib[i] != 0xffff && !X->vis[X->ib[i]]) seen(X, X->ib[i], 0);
  buildHZ(X);
  for (int j = 0; j < n; j++) {
    int k = X->list[j]; const Piece *p = &P[k];
    if (settled(X, k)) continue;
    if (X->vis[k] && p->opaque) continue;          // opaque contribution comes from the id buffer
    unsigned qm = hzTest(X, k, X->mask[k]);
    if (!qm) continue;
    int nearl = X->dist[k] <= LOD + LODM; const uint16_t *ix = nearl ? p->idx : p->fidx; int cnt = nearl ? p->ni : p->nf;
    if (cnt <= 0) continue;
    xform(X, p, e);
    if (MINC > 0 && !p->opaque) {                  // alpha/blend piece: count its unoccluded pixels
      long c = 0;
      for (int t = 0; t < cnt; t += 3) c += tri(X, M_COUNT, X->tv + ix[t] * 3, X->tv + ix[t + 1] * 3, X->tv + ix[t + 2] * 3, qm, NEARQ, 0);
      if (c) { seen(X, k, c * norm * fogW(X->dist[k])); continue; }
      if (X->vis[k]) continue;
    }
    for (int t = 0; t < cnt; t += 3)
      if (tri(X, M_QUERY, X->tv + ix[t] * 3, X->tv + ix[t + 1] * 3, X->tv + ix[t + 2] * 3, qm, NEARQ, 0)) { seen(X, k, 0); break; }
  }
  X->eyes++;
}

// exact mode: engine LOD (bbox distance > 50 m -> far list), engine near plane for occluders, draw
// distance 115 m by sphere (a superset of the engine's bbox test), center sampling; pixel counts into X->cnt
static void eyeExact(Ctx *X, const float *e, const int *cand, int ncand) {
  int n = gather(X, e, cand, ncand, DRAW);
  renderOccluders(X, e, n, LOD, NEARE);
  buildHZ(X);
  for (int j = 0; j < n; j++) {
    int k = X->list[j]; const Piece *p = &P[k];
    X->cnt[k] = 0;
    unsigned qm = hzTest(X, k, X->mask[k]);
    if (!qm) continue;
    int far = X->bd[k] > LOD; const uint16_t *ix = far ? p->fidx : p->idx; int cnt = far ? p->nf : p->ni;
    if (cnt <= 0) continue;
    xform(X, p, e);
    long c = 0;
    for (int t = 0; t < cnt; t += 3) c += tri(X, M_COUNT, X->tv + ix[t] * 3, X->tv + ix[t + 1] * 3, X->tv + ix[t + 2] * 3, qm, NEARQ, 0);
    X->cnt[k] = (uint32_t)c;
  }
}

// ---- eyes -------------------------------------------------------------------------------------
static int layersAt(float x, float z, float *out) {
  int gx = (int)floorf((x - HOX) / HCELL), gz = (int)floorf((z - HOZ) / HCELL);
  int rr = (int)ceilf(LRAD / HCELL) + 1, bx = -1, bz = -1; float bd = 1e30f;
  for (int dz = -rr; dz <= rr; dz++)
    for (int dx = -rr; dx <= rr; dx++) {
      int cx = gx + dx, cz = gz + dz;
      if (cx < 0 || cz < 0 || cx >= HW || cz >= HH) continue;
      const int16_t *c = HM + ((size_t)cz * HW + cx) * 4;
      if (c[0] == -32768 && c[1] == -32768 && c[2] == -32768 && c[3] == -32768) continue;
      float x0 = HOX + cx * HCELL, z0 = HOZ + cz * HCELL;          // distance point -> cell rect
      float ddx = fmaxf(0, fmaxf(x0 - x, x - (x0 + HCELL))), ddz = fmaxf(0, fmaxf(z0 - z, z - (z0 + HCELL)));
      float d = sqrtf(ddx * ddx + ddz * ddz);
      if (d <= LRAD && d < bd) { bd = d; bx = cx; bz = cz; }
    }
  if (bx < 0) return 0;
  const int16_t *c = HM + ((size_t)bz * HW + bx) * 4; int n = 0;
  for (int i = 0; i < 4; i++) if (c[i] != -32768) out[n++] = c[i] * .01f;
  return n;
}

static int cellEyes(int gx, int gz, float *eyes) {   // returns number of eyes (xyz triples)
  int n = 0;
  for (int j = 0; j < SAMPLES; j++)
    for (int i = 0; i < SAMPLES; i++) {
      float x = GOX + (gx + (float)i / (SAMPLES - 1)) * PCELL, z = GOZ + (gz + (float)j / (SAMPLES - 1)) * PCELL;
      float L[4]; int nl = layersAt(x, z, L);
      int first = n;
      if (LOWEST_ONLY && nl > 1) { for (int l = 1; l < nl; l++) if (L[l] < L[0]) L[0] = L[l]; nl = 1; }
      for (int l = 0; l < nl; l++)
        for (int h = 0; h < NEYEH; h++) {
          float y = L[l] + EYEH[h]; int dup = 0;
          for (int q = first; q < n; q++) if (fabsf(eyes[q * 3 + 1] - y) < .25f) { dup = 1; break; }
          if (dup) continue;
          eyes[n * 3] = x; eyes[n * 3 + 1] = y; eyes[n * 3 + 2] = z; n++;
        }
    }
  return n;
}

// ---- threads ----------------------------------------------------------------------------------
typedef struct { uint32_t count; uint16_t *list; int eyes; } CellOut;
static CellOut *OUT;
static atomic_int nextJob, doneJobs;
static int NJOBS;
static float *EXEYES; static uint32_t **EXRES; static int *EXN;
static int exactMode;

static void ctxInit(Ctx *X) {
  memset(X, 0, sizeof *X);
  size_t N = (size_t)6 * RES * RES; X->T = RES / 8;
  X->zb = malloc(N * sizeof(float)); X->ib = malloc(N * sizeof(uint16_t));
  X->hz = malloc((size_t)6 * X->T * X->T * sizeof(float));
  X->tv = malloc((size_t)(maxNV + 1) * 3 * sizeof(float));
  X->vis = calloc(NP, 1); X->list = malloc(NP * sizeof(int)); X->dist = malloc(NP * sizeof(float));
  X->mask = calloc(NP, 1); X->rect = malloc((size_t)NP * sizeof *X->rect); X->nz = malloc((size_t)NP * sizeof *X->nz);
  X->cnt = calloc(NP, sizeof(uint32_t)); X->dk = malloc(NP * sizeof(DK));
  X->mind = malloc(NP * sizeof(float)); X->best = malloc(NP * sizeof(float)); X->bd = malloc(NP * sizeof(float));
  if (!X->zb || !X->ib || !X->hz || !X->tv || !X->vis || !X->list || !X->dist || !X->rect || !X->nz || !X->cnt || !X->dk ||
      !X->mind || !X->best || !X->bd) { fprintf(stderr, "out of memory\n"); exit(1); }
}

static void *worker(void *arg) {
  Ctx *X = arg;
  float *eyes = malloc(sizeof(float) * 3 * SAMPLES * SAMPLES * 4 * 8);  // samples x layers x heights
  int *cand = malloc(NP * sizeof(int));
  for (;;) {
    int job = atomic_fetch_add(&nextJob, 1);
    if (job >= NJOBS) break;
    if (exactMode) {
      unsigned em = regAt(EXEYES[job * 3], EXEYES[job * 3 + 2]); int nc = 0;   // правка 95: регионы, которые оригинал держит у глаза
      for (int j = 0; j < NCITY; j++) if (regOk(cityIdx[j], em)) cand[nc++] = cityIdx[j];
      eyeExact(X, EXEYES + job * 3, cand, nc);
      int m = 0; for (int k = 0; k < NP; k++) if (P[k].city && X->cnt[k]) m++;
      uint32_t *r = malloc(sizeof(uint32_t) * 2 * (m + 1)); int q = 0;
      for (int k = 0; k < NP; k++) if (P[k].city && X->cnt[k]) { r[q * 2] = k; r[q * 2 + 1] = X->cnt[k]; q++; X->cnt[k] = 0; }
      EXRES[job] = r; EXN[job] = m;
      continue;
    }
    int gx = job % GW, gz = job / GW;
    int ne = cellEyes(gx, gz, eyes);
    OUT[job].eyes = ne;
    if (!ne) { OUT[job].count = 0xFFFFFFFFu; OUT[job].list = 0; }
    else {
      // candidate pieces: horizontal distance from piece center to the cell rect - radius <= range
      float x0 = GOX + gx * PCELL, z0 = GOZ + gz * PCELL, range = DRAW + RMARGIN;
      int nc = 0; unsigned um = regRect(x0, z0, x0 + PCELL, z0 + PCELL);
      for (int j = 0; j < NCITY; j++) {
        const Piece *p = &P[cityIdx[j]];
        if (!regOk(cityIdx[j], um)) { X->regdrop++; continue; }   // правка 95: регион не загружен оригиналом — не в списке, не заслон
        float dx = fmaxf(0, fmaxf(x0 - p->c[0], p->c[0] - (x0 + PCELL))), dz = fmaxf(0, fmaxf(z0 - p->c[2], p->c[2] - (z0 + PCELL)));
        if (sqrtf(dx * dx + dz * dz) - p->rad <= range) cand[nc++] = cityIdx[j];
      }
      for (int j = 0; j < nc; j++) { int k = cand[j]; X->vis[k] = 0; X->mind[k] = 1e30f; X->best[k] = 0; }
      for (int i = 0; i < ne; i++) eyePVS(X, eyes + i * 3, cand, nc);
      int m = 0;
      for (int j = 0; j < nc; j++) {
        int k = cand[j];
        if (X->vis[k] && MINC > 0 && X->mind[k] > FOG0 && X->best[k] < MINC) { X->vis[k] = 0; X->dropped++; }
        m += X->vis[k];
      }
      OUT[job].count = m; OUT[job].list = malloc(sizeof(uint16_t) * (m ? m : 1));
      int q = 0; for (int j = 0; j < nc; j++) if (X->vis[cand[j]]) OUT[job].list[q++] = (uint16_t)cand[j];   // cand ascending
      for (int j = 0; j < nc; j++) X->vis[cand[j]] = 0;
    }
    int d = atomic_fetch_add(&doneJobs, 1) + 1;
    if (d % (NJOBS / 20 + 1) == 0) { fprintf(stderr, "\r  %3d%%", d * 100 / NJOBS); fflush(stderr); }
  }
  free(eyes); free(cand);
  return 0;
}

static void runThreads(int nth, Ctx *ctx) {
  pthread_t th[64];
  atomic_store(&nextJob, 0); atomic_store(&doneJobs, 0);
  for (int i = 0; i < nth; i++) pthread_create(&th[i], 0, worker, &ctx[i]);
  for (int i = 0; i < nth; i++) pthread_join(th[i], 0);
}

// ---- stats / output ---------------------------------------------------------------------------
static int cmpU32(const void *a, const void *b) { uint32_t x = *(const uint32_t *)a, y = *(const uint32_t *)b; return x < y ? -1 : x > y; }

static void stats(const char *name, CellOut *o) {
  int nd = 0; uint64_t pool = 0; uint32_t *c = malloc(sizeof(uint32_t) * GW * GH);
  for (int i = 0; i < GW * GH; i++) if (o[i].count != 0xFFFFFFFFu) { c[nd++] = o[i].count; pool += o[i].count; }
  qsort(c, nd, sizeof *c, cmpU32);
  if (nd) fprintf(stderr, "  %-9s cells with data %d/%d, pieces per cell: mean %.0f median %u p90 %u max %u; pool %llu entries (%.2f MB), section %.2f MB\n",
    name, nd, GW * GH, (double)pool / nd, c[nd / 2], c[(int)(nd * .9)], c[nd - 1], (unsigned long long)pool, pool * 2 / 1048576.0,
    (32 + 8.0 * GW * GH + pool * 2) / 1048576.0);
  free(c);
}

static CellOut *dilate(CellOut *in) {
  CellOut *o = calloc((size_t)GW * GH, sizeof *o);
  uint8_t *mark = calloc(NP, 1);
  for (int gz = 0; gz < GH; gz++)
    for (int gx = 0; gx < GW; gx++) {
      CellOut *c = &in[gz * GW + gx], *d = &o[gz * GW + gx];
      if (c->count == 0xFFFFFFFFu) { d->count = 0xFFFFFFFFu; continue; }
      for (int dz = -1; dz <= 1; dz++)
        for (int dx = -1; dx <= 1; dx++) {
          int x = gx + dx, z = gz + dz;
          if (x < 0 || z < 0 || x >= GW || z >= GH) continue;
          CellOut *n = &in[z * GW + x]; if (n->count == 0xFFFFFFFFu) continue;
          for (uint32_t i = 0; i < n->count; i++) mark[n->list[i]] = 1;
        }
      int m = 0; for (int k = 0; k < NP; k++) m += mark[k];
      d->count = m; d->list = malloc(sizeof(uint16_t) * (m ? m : 1)); m = 0;
      for (int k = 0; k < NP; k++) if (mark[k]) { d->list[m++] = (uint16_t)k; mark[k] = 0; }
    }
  free(mark);
  return o;
}

static int writeOut(const char *path, CellOut *o) {
  if (orderedNew) { fprintf(stderr, "%s: level.shr уже в порядке загрузки 2 (клетки после PVS1) — PVS пересчитывать до tools/shr_order.py\n", path); return 1; }
  uint64_t pool = 0;
  for (int i = 0; i < GW * GH; i++) if (o[i].count != 0xFFFFFFFFu) pool += o[i].count;
  size_t pvsOff = (baseSize + 15) & ~(size_t)15;
  size_t secSize = 32 + 8 * (size_t)GW * GH + 2 * pool, total = pvsOff + secSize; total = (total + 15) & ~(size_t)15;
  uint8_t *b = calloc(total, 1);
  memcpy(b, file, baseSize);
  uint8_t *s = b + pvsOff;
  memcpy(s, "PVS1", 4);
  float fh[3] = {GOX, GOZ, PCELL}; memcpy(s + 4, fh, 12);
  uint32_t uh[4] = {(uint32_t)GW, (uint32_t)GH, (uint32_t)pool, DRAW != 115.f ? (uint32_t)(DRAW + .5f) : 0}; memcpy(s + 16, uh, 16);   // pad: дальность списков, м (0 = 115)
  uint32_t *ent = (uint32_t *)(s + 32); uint16_t *pl = (uint16_t *)(s + 32 + 8 * (size_t)GW * GH);
  uint32_t at = 0;
  for (int i = 0; i < GW * GH; i++) {
    if (o[i].count == 0xFFFFFFFFu) { ent[i * 2] = 0; ent[i * 2 + 1] = 0xFFFFFFFFu; continue; }
    ent[i * 2] = at; ent[i * 2 + 1] = o[i].count;
    memcpy(pl + at, o[i].list, o[i].count * 2); at += o[i].count;
  }
  uint32_t off32 = (uint32_t)pvsOff; memcpy(b + 88, &off32, 4);
  char tmp[4096]; snprintf(tmp, sizeof tmp, "%s.tmp%d", path, (int)getpid());
  FILE *f = fopen(tmp, "wb");
  if (!f) { perror(tmp); return 1; }
  int bad = fwrite(b, 1, total, f) != total; bad |= fclose(f) != 0;
  if (bad) { fprintf(stderr, "write failed: %s\n", tmp); remove(tmp); return 1; }
  if (rename(tmp, path)) { perror("rename"); remove(tmp); return 1; }
  fprintf(stderr, "wrote %s: PVS section at %zu, %.2f MB (file %.2f MB)\n", path, pvsOff, secSize / 1048576.0, total / 1048576.0);
  free(b);
  return 0;
}

// ---- main -------------------------------------------------------------------------------------
static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + t.tv_nsec * 1e-9; }

int main(int argc, char **argv) {
  const char *in = 0, *out = 0, *exactPath = 0; int nth = (int)sysconf(_SC_NPROCESSORS_ONLN), dil = 0, dry = 0;
  for (int i = 1; i < argc; i++) {
    if (!strcmp(argv[i], "--res") && i + 1 < argc) RES = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--threads") && i + 1 < argc) nth = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--dilate")) dil = 1;
    else if (!strcmp(argv[i], "--occ-near") && i + 1 < argc) NEARO = (float)atof(argv[++i]);
    else if (!strcmp(argv[i], "--exact") && i + 1 < argc) exactPath = argv[++i];
    else if (!strcmp(argv[i], "--heights") && i + 1 < argc) {       // experiment: eye heights, e.g. 1.2,3.5
      NEYEH = 0; for (char *t = strtok(argv[++i], ","); t && NEYEH < 8; t = strtok(0, ",")) EYEH[NEYEH++] = (float)atof(t);
    }
    else if (!strcmp(argv[i], "--lowest")) LOWEST_ONLY = 1;
    else if (!strcmp(argv[i], "--min-contrib") && i + 1 < argc) MINC = (float)atof(argv[++i]);
    else if (!strcmp(argv[i], "--cell") && i + 1 < argc) PCELL = (float)atof(argv[++i]);
    else if (!strcmp(argv[i], "--samples") && i + 1 < argc) SAMPLES = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--range") && i + 1 < argc) { DRAW = (float)atof(argv[++i]); FOG0 = DRAW * .52f; }   // правка 497: дальность списков (по умолчанию 115)
    else if (!strcmp(argv[i], "--dry")) dry = 1;
    else if (argv[i][0] == '-') { fprintf(stderr, "unknown option %s\n", argv[i]); return 2; }
    else if (!in) in = argv[i];
    else if (!out) out = argv[i];
    else { fprintf(stderr, "too many arguments\n"); return 2; }
  }
  if (!in) {
    fprintf(stderr, "usage: pvs IN.shr [OUT.shr] [--res N] [--samples N] [--dilate] [--min-contrib N] [--threads N] [--occ-near M]\n"
                    "       experiments: [--dry] [--cell M] [--heights a,b,..] [--lowest]\n"
                    "       pvs IN.shr --exact EYES.txt [--res N]\n");
    return 2;
  }
  if (!out) out = in;
  if (SAMPLES < 2 || SAMPLES > 16 || NEYEH < 1 || PCELL < 2) { fprintf(stderr, "bad --samples/--heights\n"); return 2; }
  if (RES < 16 || RES % 8 || RES > 2048) { fprintf(stderr, "--res must be a multiple of 8 in 16..2048\n"); return 2; }
  if (nth < 1) nth = 1; if (nth > 64) nth = 64;
  double t0 = now();

  FILE *f = fopen(in, "rb");
  if (!f) { perror(in); return 1; }
  fseek(f, 0, SEEK_END); fileSize = (size_t)ftell(f); fseek(f, 0, SEEK_SET);
  file = malloc(fileSize);
  if (!file || fread(file, 1, fileSize, f) != fileSize) { fprintf(stderr, "read failed\n"); return 1; }
  fclose(f);
  if (fileSize < 104 || memcmp(file, "SHR7", 4)) { fprintf(stderr, "%s: not a SHR7 file\n", in); return 1; }
  uint32_t npc, ncell, tableOff, cellOff, oldPvs;
  memcpy(&npc, file + 8, 4); memcpy(&tableOff, file + 76, 4); memcpy(&ncell, file + 80, 4);
  memcpy(&cellOff, file + 84, 4); memcpy(&oldPvs, file + 88, 4);
  float hd[14]; memcpy(hd, file + 12, sizeof hd);
  HOX = hd[11]; HOZ = hd[12]; HCELL = hd[13];
  memcpy(&HW, file + 68, 4); memcpy(&HH, file + 72, 4);
  HM = (const int16_t *)(file + 104);   // заголовок SHR7 теперь 104 Б (@96 propOff, этап 3б; @100 carOff)
  baseSize = fileSize; regEnd = fileSize;
  if ((uint64_t)tableOff + 80ull * npc > fileSize || (uint64_t)cellOff + 48ull * ncell > fileSize ||
      104 + (uint64_t)HW * HH * 8 > fileSize || HW <= 0 || HH <= 0) { fprintf(stderr, "%s: truncated or bad header\n", in); return 1; }
  if (oldPvs) {
    if (oldPvs < 104 || (uint64_t)oldPvs + 32 > fileSize || memcmp(file + oldPvs, "PVS1", 4)) { fprintf(stderr, "header @88 points to garbage\n"); return 1; }
    baseSize = oldPvs;   // replace the existing section
    // загрузка 2, п.3 (tools/shr_order.py): блобы клеток лежат ПОСЛЕ PVS1 — для чтения (--exact, проверки) база — весь файл; перезаписать PVS на месте нельзя
    { uint32_t cmin = 0xFFFFFFFFu; for (uint32_t i = 0; i < ncell && (uint64_t)cellOff + 48ull * (i + 1) <= fileSize; i++) { uint32_t o; memcpy(&o, file + cellOff + 48 * i + 36, 4); if (o < cmin) cmin = o; }
      if (ncell && cmin > oldPvs) { baseSize = fileSize; orderedNew = 1; } }
    regEnd = oldPvs;
  }
  const Rec *recs = (const Rec *)(file + tableOff); const CellRec *cells = (const CellRec *)(file + cellOff);
  NP = (int)npc; P = calloc(NP, sizeof(Piece)); cityIdx = malloc(sizeof(int) * NP);
  regFind(); PREG = calloc(NP ? NP : 1, 1);   // правка 95: REG1 и регион каждого куска города (Rec.pad[0])
  long long ntri = 0, nftri = 0;
  for (int i = 0; i < NP; i++) {
    const Rec *r = &recs[i]; Piece *p = &P[i];
    if (r->owner != 0) continue;
    if (r->cell >= ncell) { fprintf(stderr, "piece %d: bad cell\n", i); return 1; }
    // флаг 16: без индексов (вершины подряд: ближняя версия, за ней дальняя, nv = ni + nf), флаг 32: вершина 12 Б
    const int noidx = (r->flags & 16) != 0; const size_t vs = (r->flags & 32) ? 12 : 16;
    uint64_t pend = noidx ? (uint64_t)cells[r->cell].off + r->off + (uint64_t)r->nv * vs
                          : (uint64_t)cells[r->cell].off + r->off + (((uint64_t)r->nv * 16 + 15) & ~15ull) + (((uint64_t)r->ni * 2 + 15) & ~15ull) + (uint64_t)r->nf * 2;
    if (noidx && r->nv != r->ni + r->nf) { fprintf(stderr, "piece %d: no-index piece with nv != ni + nf\n", i); return 1; }
    if (pend > baseSize || r->ni % 3 || r->nf % 3) { fprintf(stderr, "piece %d: blob out of file / bad index count\n", i); return 1; }
    const uint8_t *b = file + cells[r->cell].off + r->off;
    p->city = 1; p->opaque = (r->flags & 3) == 0; p->nv = r->nv; p->ni = r->ni; p->nf = r->nf;
    if (REGM && r->pad[0] && r->pad[0] <= REGN) PREG[i] = (uint8_t)r->pad[0];
    p->v = malloc(sizeof(float) * 3 * (p->nv ? p->nv : 1));
    float mn[3] = {1e30f, 1e30f, 1e30f}, mx[3] = {-1e30f, -1e30f, -1e30f}, o[3] = {r->ox, r->oy, r->oz};
    for (int k = 0; k < p->nv; k++) {
      const int16_t *q = (const int16_t *)(b + vs * k + (vs == 12 ? 6 : 8));
      for (int a = 0; a < 3; a++) {
        float w = o[a] + q[a] * (r->sc / 32768.f); p->v[k * 3 + a] = w;
        if (w < mn[a]) mn[a] = w; if (w > mx[a]) mx[a] = w;
      }
    }
    if (noidx) {                          // без индексов: списки 0..ni-1 и ni..ni+nf-1
      if (p->nv > 65535) { fprintf(stderr, "piece %d: too many vertices for u16 lists\n", i); return 1; }
      p->idx = malloc(sizeof(uint16_t) * (p->nv ? p->nv : 1)); p->fidx = p->idx + p->ni;
      for (int k = 0; k < p->nv; k++) p->idx[k] = (uint16_t)k;
    } else {
      p->idx = (uint16_t *)(b + (((size_t)p->nv * 16 + 15) & ~(size_t)15));
      p->fidx = (uint16_t *)((uint8_t *)p->idx + (((size_t)p->ni * 2 + 15) & ~(size_t)15));
    }
    for (int t = 0; t < p->ni; t++) if (p->idx[t] >= p->nv) { fprintf(stderr, "piece %d: bad index\n", i); return 1; }
    for (int t = 0; t < p->nf; t++) if (p->fidx[t] >= p->nv) { fprintf(stderr, "piece %d: bad far index\n", i); return 1; }
    if (r->flags & 2048) { p->fidx = p->idx; p->nf = p->ni; }   // флаг 2048 (правки 224/237/251): кусок и вдали — ближней версией, как viewer/main.c drawPiece
    for (int a = 0; a < 3; a++) { p->bb[a] = fminf(r->bb[a], mn[a]); p->bb[3 + a] = fmaxf(r->bb[3 + a], mx[a]); }
    memcpy(p->sbb, r->bb, sizeof p->sbb);
    for (int a = 0; a < 3; a++) p->c[a] = (r->bb[a] + r->bb[3 + a]) * .5f;   // engine uses the stored bbox
    float dx = r->bb[3] - r->bb[0], dy = r->bb[4] - r->bb[1], dz = r->bb[5] - r->bb[2];
    p->rad = .5f * sqrtf(dx * dx + dy * dy + dz * dz) + 0.01f;
    if (p->nv > maxNV) maxNV = p->nv;
    cityIdx[NCITY++] = i; ntri += p->ni / 3; nftri += p->nf / 3;
  }
  if (NP > 65535) { fprintf(stderr, "too many pieces for u16 lists\n"); return 1; }
  GOX = HOX - PMARGIN; GOZ = HOZ - PMARGIN;
  GW = (int)ceilf((HW * HCELL + 2 * PMARGIN) / PCELL); GH = (int)ceilf((HH * HCELL + 2 * PMARGIN) / PCELL);
  fprintf(stderr, "%s: %d pieces (%d city, %lld tris near / %lld far), heightmap %dx%d; grid %dx%d x %.0f m; res %d, %d threads\n",
          in, NP, NCITY, ntri, nftri, HW, HH, GW, GH, PCELL, RES, nth);

  Ctx *ctx = malloc(sizeof(Ctx) * nth);
  for (int i = 0; i < nth; i++) ctxInit(&ctx[i]);

  if (exactPath) {
    FILE *e = fopen(exactPath, "r");
    if (!e) { perror(exactPath); return 1; }
    int cap = 1024, n = 0; EXEYES = malloc(sizeof(float) * 3 * cap);
    float x, y, z;
    while (fscanf(e, "%f %f %f", &x, &y, &z) == 3) {
      if (n == cap) { cap *= 2; EXEYES = realloc(EXEYES, sizeof(float) * 3 * cap); }
      EXEYES[n * 3] = x; EXEYES[n * 3 + 1] = y; EXEYES[n * 3 + 2] = z; n++;
    }
    fclose(e);
    exactMode = 1; NJOBS = n; EXRES = calloc(n, sizeof *EXRES); EXN = calloc(n, sizeof *EXN);
    runThreads(nth, ctx);
    for (int i = 0; i < n; i++)
      for (int q = 0; q < EXN[i]; q++) printf("%d %u %u\n", i, EXRES[i][q * 2], EXRES[i][q * 2 + 1]);
    fprintf(stderr, "exact: %d eyes, res %d, %.1f s\n", n, RES, now() - t0);
    return 0;
  }

  NJOBS = GW * GH; OUT = calloc(NJOBS, sizeof *OUT);
  runThreads(nth, ctx);
  long long eyes = 0, tris = 0, culled = 0, dropped = 0, regdrop = 0;
  for (int i = 0; i < nth; i++) { eyes += ctx[i].eyes; tris += ctx[i].tris; culled += ctx[i].culled; dropped += ctx[i].dropped; regdrop += ctx[i].regdrop; }
  if (REGM) { int nr = 0; for (int i = 0; i < NP; i++) nr += PREG[i] != 0;
    fprintf(stderr, "\n  REG1 (правка 95): %u регионов, сетка %ux%u по %.0f м; кусков с регионом %d; пар (клетка, кусок) вне маски клетки — %lld\n",
            REGN, REGW, REGH, REGCELL, nr, regdrop); }
  else fprintf(stderr, "\n  REG1 нет: регионы не учитываются (старый файл)\n");
  if (MINC > 0) fprintf(stderr, "\n  --min-contrib %.1f: dropped %lld (cell, piece) pairs seen only beyond %.0f m and tiny\n", MINC, dropped, FOG0);
  double t1 = now();
  fprintf(stderr, "\r  done: %lld eyes, %.1f M occluder tris (%.1f k/eye, %.0f occluder pieces/eye skipped as hidden), %.1f s\n",
          eyes, tris / 1e6, tris / 1e3 / (eyes ? eyes : 1), (double)culled / (eyes ? eyes : 1), t1 - t0);
  stats("plain", OUT);
  CellOut *D = dilate(OUT);
  stats("dilated", D);
  if (dry) return 0;
  fprintf(stderr, "writing %s lists\n", dil ? "dilated" : "plain");
  return writeOut(out, dil ? D : OUT);
}
