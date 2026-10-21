#ifndef SHAR_RACE_ONROAD_H
#define SHAR_RACE_ONROAD_H
#include <math.h>
#include "traffic.h"

/* PS2 recording: sidewalks/grass => ?, shortcuts count as roads.
   Port classification uses authored road widths and junction spheres from TRA1,
   including shortcuts and roads with no traffic. Boundary precision is not a
   measured PS2 algorithm; no invented distance threshold or material override. */
static inline int raceOnRoad(const Traffic *t, float x, float y, float z) {
#ifdef C3_RACE_OFFROAD_OLD
  (void)t; (void)x; (void)y; (void)z; return 1;
#else
  if (!t || !t->hd || !t->road || !t->pt) return 1; /* no geometry: retain number */
  for (unsigned ri = 0; ri < t->hd->nRoad; ri++) {
    const TrRoad *r = &t->road[ri];
    if (!r->lanes || r->nPt < 2 || r->width <= 0.f) continue;
    const TrPt *left = t->pt + r->firstPt;
    const TrPt *right = left + (r->lanes - 1) * r->nPt;
    /* TRF1 width is one lane, exported from RoadSegment span / lane count. */
    float hw = r->width * r->lanes * .5f;
    for (unsigned k = 1; k < r->nPt; k++) {
      float ax = .5f * (left[k-1].x + right[k-1].x), ay = .5f * (left[k-1].y + right[k-1].y);
      float az = .5f * (left[k-1].z + right[k-1].z);
      float bx = .5f * (left[k].x + right[k].x), by = .5f * (left[k].y + right[k].y);
      float bz = .5f * (left[k].z + right[k].z);
      if (x < fminf(ax,bx)-hw || x > fmaxf(ax,bx)+hw || z < fminf(az,bz)-hw || z > fmaxf(az,bz)+hw) continue;
      float dx=bx-ax, dy=by-ay, dz=bz-az, ll=dx*dx+dy*dy+dz*dz;
      float u=ll > 0.f ? ((x-ax)*dx+(y-ay)*dy+(z-az)*dz)/ll : 0.f;
      u=fmaxf(0.f,fminf(1.f,u)); dx=x-ax-u*dx; dy=y-ay-u*dy; dz=z-az-u*dz;
      if (dx*dx+dy*dy+dz*dz <= hw*hw) return 1;
    }
  }
  for (unsigned j=0; t->junc && j<t->hd->nJunc; j++) {
    const TrJunc *q=&t->junc[j]; float dx=x-q->x,dy=y-q->y,dz=z-q->z;
    if (q->r > 0.f && dx*dx+dy*dy+dz*dz <= q->r*q->r) return 1;
  }
  return 0;
#endif
}
#endif
