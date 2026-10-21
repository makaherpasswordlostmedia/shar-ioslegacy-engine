// Правка Роба 325 (гейт tests/fe_guard/gate325.sh): настоящий код среза подсветок viewer/fe_billcut.h на Маке.
// stdin: строки «cp3 cr3 cu3 cf3 tvx tvy near P(4×3) T(4×2)» (35 чисел, вершины в порядке полосы, как drawBill);
// stdout: «-1» (квад целиком в пирамиде: движок рисует полосой) или «n x y z s t …» (веер после среза).
// Сборка с -DFE_BILL_CUT_OLD — прежнее (как flag febillold 1): всегда «-1», квад как есть (красный контроль).
#include <stdio.h>
#include "fe_billcut.h"

int main(void) {
  float v[35];
  for (;;) {
    for (int i = 0; i < 35; i++) if (scanf("%f", &v[i]) != 1) return 0;
    FeCutCam k = {{v[0], v[1], v[2]}, {v[3], v[4], v[5]}, {v[6], v[7], v[8]}, {v[9], v[10], v[11]}, v[12], v[13], v[14]};
    float P[4][3], T[4][2];
    for (int i = 0; i < 4; i++) { for (int j = 0; j < 3; j++) P[i][j] = v[15 + 3 * i + j]; T[i][0] = v[27 + 2 * i]; T[i][1] = v[28 + 2 * i]; }
#ifdef FE_BILL_CUT_OLD
    int n = -1; FeCutVert o[FE_CUT_MAXV]; (void)k; (void)P; (void)T; (void)o;
#else
    FeCutVert o[FE_CUT_MAXV]; int n = feBillCut(P, T, &k, o);
#endif
    printf("%d", n);
    for (int i = 0; i < n; i++) printf(" %.7g %.7g %.7g %.7g %.7g", o[i].w[0], o[i].w[1], o[i].w[2], o[i].s, o[i].t);
    printf("\n");
  }
}
