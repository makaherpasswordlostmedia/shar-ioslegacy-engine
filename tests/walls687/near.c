#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "car.h"
#include "col.h"
static ColWorld w;
int main(int argc, char **argv) {
  FILE *f = fopen(argv[1], "rb"); fseek(f, 0, SEEK_END); unsigned n = ftell(f); rewind(f); unsigned char *b = malloc(n); if (fread(b,1,n,f)!=n) return 2; fclose(f);
  unsigned co = *(unsigned *)(b + 92), po = *(unsigned *)(b + 96), pv = *(unsigned *)(b + 88), end = n;
  if (po > co && po < end) end = po; if (pv > co && pv < end) end = pv;
  if (colInit(&w, b + co, end - co)) return 2;
  float x0 = atof(argv[2]), x1 = atof(argv[3]), z0 = atof(argv[4]), z1 = atof(argv[5]), y0 = atof(argv[6]), y1 = atof(argv[7]);
  for (unsigned i = 0; i < w.nbox; i++) { const ColBox *B = &w.box[i]; float r = fabsf(B->ax[0]*B->h[0])+fabsf(B->ay[0]*B->h[1])+fabsf(B->az[0]*B->h[2]), rz = fabsf(B->ax[2]*B->h[0])+fabsf(B->ay[2]*B->h[1])+fabsf(B->az[2]*B->h[2]), ry = fabsf(B->ax[1]*B->h[0])+fabsf(B->ay[1]*B->h[1])+fabsf(B->az[1]*B->h[2]);
    if (B->c[0]+r < x0 || B->c[0]-r > x1 || B->c[2]+rz < z0 || B->c[2]-rz > z1 || B->c[1]+ry < y0 || B->c[1]-ry > y1) continue;
    printf("box %u c(%.2f %.2f %.2f) h(%.2f %.2f %.2f) pad %.0f; x %.2f..%.2f z %.2f..%.2f y %.2f..%.2f\n", i, B->c[0],B->c[1],B->c[2],B->h[0],B->h[1],B->h[2],B->pad, B->c[0]-r,B->c[0]+r,B->c[2]-rz,B->c[2]+rz,B->c[1]-ry,B->c[1]+ry); }
  for (unsigned i = 0; i < w.nseg; i++) { const ColSeg *S = &w.seg[i]; float mx0 = fminf(S->a[0],S->b[0]), mx1 = fmaxf(S->a[0],S->b[0]), mz0 = fminf(S->a[1],S->b[1]), mz1 = fmaxf(S->a[1],S->b[1]);
    if (mx1 < x0 || mx0 > x1 || mz1 < z0 || mz0 > z1 || S->y1 < y0 || S->y0 > y1) continue;
    printf("seg %u a(%.2f %.2f) b(%.2f %.2f) n(%.2f %.2f) y %.1f..%.1f\n", i, S->a[0],S->a[1],S->b[0],S->b[1],S->n[0],S->n[1],S->y0,S->y1); }
  for (unsigned i = 0; i < w.ncyl; i++) { const ColCyl *C = &w.cyl[i]; if (C->c[0]+C->r < x0 || C->c[0]-C->r > x1 || C->c[2]+C->r < z0 || C->c[2]-C->r > z1) continue; printf("cyl %u c(%.2f %.2f %.2f) r %.2f hl %.2f\n", i, C->c[0],C->c[1],C->c[2],C->r,C->halfLen); }
  int nt=0; for (unsigned i = 0; i < w.ntri; i++) { const ColTri *T = &w.tri[i]; float mx0=fminf(T->a[0],fminf(T->b[0],T->c[0])),mx1=fmaxf(T->a[0],fmaxf(T->b[0],T->c[0])),mz0=fminf(T->a[2],fminf(T->b[2],T->c[2])),mz1=fmaxf(T->a[2],fmaxf(T->b[2],T->c[2])),my0=fminf(T->a[1],fminf(T->b[1],T->c[1])),my1=fmaxf(T->a[1],fmaxf(T->b[1],T->c[1]));
    if (mx1<x0||mx0>x1||mz1<z0||mz0>z1||my1<y0||my0>y1||fabsf(T->n[1])>0.7f) continue; if (nt++<12) printf("tri %u n(%.2f %.2f %.2f) x %.2f..%.2f z %.2f..%.2f y %.2f..%.2f\n", i, T->n[0],T->n[1],T->n[2],mx0,mx1,mz0,mz1,my0,my1); }
  printf("tri вертик. в области: %d\n", nt); return 0; }
