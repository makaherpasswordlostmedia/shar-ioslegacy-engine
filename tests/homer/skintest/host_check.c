// Host (Mac) check of viewer/skin.c against the Python mirror in tools/char_export.py:
//   cc -O2 -DSKIN_HOST -I viewer tests/homer/host_check.c viewer/skin.c -lm -o /tmp/host_check
//   /tmp/host_check build/chars/homer.chr > pal.txt ; python tests/homer/check_host.py pal.txt
// Prints, for a set of (clip, t) and one crossfade, every bone palette matrix (12 floats) and the root motion.
#include <stdio.h>
#include <stdlib.h>
#include "skin.h"

static void dump(const SkinModel *m, const char *tag, const ScePspFMatrix4 *pal) {
  for (unsigned j = 0; j < m->h->nJoints; j++) {
    const float *f = (const float *)&pal[j];
    printf("%s %u", tag, j);
    for (int c = 0; c < 4; c++) printf(" %.6f %.6f %.6f", f[4 * c], f[4 * c + 1], f[4 * c + 2]);
    printf("\n");
  }
}

int main(int argc, char **argv) {
  SkinModel *m = skinLoad(argc > 1 ? argv[1] : "build/chars/homer.chr");
  if (!m) { fprintf(stderr, "load failed\n"); return 1; }
  static SkinXf xf[SKIN_MAXJ], xb[SKIN_MAXJ]; static ScePspFMatrix4 pal[SKIN_MAXJ];
  const char *names[] = {"loco_idle_rest", "loco_walk", "loco_run", "jump_kick", "get_into_car", "idle_dancing", "idle_fat"};
  float times[] = {0.f, 0.137f, 0.333f, 0.5f, 0.71f, 2.9f};
  for (int i = 0; i < 7; i++) {
    int c = skinFindClip(m, names[i]);
    if (c < 0) { fprintf(stderr, "no clip %s\n", names[i]); return 1; }
    for (int k = 0; k < 6; k++) {
      char tag[96]; snprintf(tag, sizeof tag, "P %s %.3f", skinClipName(m, c), times[k]);
      skinSample(m, c, times[k], xf); skinPalette(m, xf, pal, 0); dump(m, tag, pal);
      float r[3]; skinRootMotion(m, c, times[k], r); printf("R %s %.3f %.6f %.6f %.6f\n", skinClipName(m, c), times[k], r[0], r[1], r[2]);
    }
  }
  // blend walk/run 30 %
  int a = skinFindClip(m, "loco_walk"), b = skinFindClip(m, "loco_run");
  skinSample(m, a, .4f, xf); skinSample(m, b, .2f, xb); skinBlend(xf, xb, .3f, (int)m->h->nJoints); skinPalette(m, xf, pal, 0);
  dump(m, "B hom_loco_walk 0.400 hom_loco_run 0.200 0.300", pal);
  // player: blink timing + crossfade
  static SkinPlayer p; skinInit(&p, m); skinPlay(&p, a, 1, 0.f); int blinks = 0, prevEye = -1;
  for (int f = 0; f < 60 * 20; f++) { skinUpdate(&p, 1.f / 60.f); if (p.eyeTex >= 0 && prevEye < 0) blinks++; prevEye = p.eyeTex; }
  printf("I blinks_in_20s %d t %.4f\n", blinks, p.t);
  printf("I clip speed m/s: walk %.3f run %.3f dash %.3f idle %.3f\n", skinClipSpeed(m, a), skinClipSpeed(m, b),
         skinClipSpeed(m, skinFindClip(m, "loco_dash")), skinClipSpeed(m, skinFindClip(m, "loco_idle_rest")));
  printf("I clips %u joints %u batches %u verts %u keys %u\n", m->h->nClips, m->h->nJoints, m->h->nBatches, m->h->totalVerts, m->h->totalKeys);
  skinFree(m); return 0;
}
