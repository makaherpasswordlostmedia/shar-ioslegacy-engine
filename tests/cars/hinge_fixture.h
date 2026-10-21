// Read only CAR1 from an existing local level; no game resources in this test.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "carvis.h"
static int hingeFixture(CarVis *v, const char *path) {
  FILE *f = fopen(path, "rb");
  if (!f) return 0;
  unsigned char head[108], fixed[80]; unsigned offset;
  if (fread(head, 1, sizeof head, f) != sizeof head) { fclose(f); return 0; }
  memcpy(&offset, head + 100, 4);
  if (fseek(f, offset, SEEK_SET) || fread(fixed, 1, sizeof fixed, f) != sizeof fixed || memcmp(fixed, "CAR1", 4)) { fclose(f); return 0; }
  unsigned count[4]; memcpy(count, fixed + 8, sizeof count);
  if (count[0] > CARVIS_MAXJ || count[1] > CARVIS_MAXH || count[2] > CARVIS_MAXD || count[3] > CARVIS_MAXF) { fclose(f); return 0; }
  unsigned size = 80 + 28 * count[0] + 24 * count[1] + 8 * count[2] + 36 * count[3];
  unsigned char *data = malloc(size);
  if (!data) { fclose(f); return 0; }
  int ok = !fseek(f, offset, SEEK_SET) && fread(data, 1, size, f) == size && !carVisInit(v, data, size);
  free(data); fclose(f); return ok;
}
