// №419: строки tests/glass419/want.h — предметы уровня, чей обломок в семействе (18 стеклянная игла, 30–32 тыквы, 33 l3_burns)
//   want N LEVEL.shr HOMER.shr
#include <stdio.h>
#include <stdlib.h>
#include "world.h"
static BotWorld W;
int main(int c, char **v) {
  if (c < 4 || bwData(v[2], v[3], 0)) return 1;
  bwNew(&W);
  for (unsigned i = 0; i < W.props.ninst; i++) { int part, brk; propsTypeFx(&W.props, W.props.def[i].type, &part, &brk);
    if (brk == 18 || (brk >= 30 && brk <= 33)) printf("  {%s, %d, {%.1ff, %.1ff, %.1ff}, \"L%s_brk%d_%u\"},\n", v[1], brk, W.props.def[i].x, W.props.def[i].y, W.props.def[i].z, v[1], brk, i); }
  return 0;
}
