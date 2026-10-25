#!/bin/bash
# сборки тура для приёмок №970 и №976 (viewer/build_g_new|none|oldc|red): none — блики этих правок погашены (опора кадра), oldc — как TEST66, red — по одному недоделанному правилу на предмет
cd "$(dirname "$0")/../.."; T=tests/glint970
$T/mk.sh new "" > /dev/null
$T/mk.sh none "-DWRENCH970_S=0.001f -DWRENCH970_A=0.f -DPHONE970_A=0.f -DCOIN_SAT_A=0.f -DCAR_GLINT970_K=0.001f -DCOL976_A=0.f" > /dev/null
$T/mk.sh oldc "-DGLINT970_OLD=1 -DGLINT976_OLD=1" > /dev/null
$T/mk.sh red "-DWRENCH970_A=1.f -DPHONE970_A=1.f -DPHONE970_CORE=1.f -DCOIN_SAT_N=1 -DCAR_GLINT970_K=1.f -DCOL976_A=1.f -DSPHERE976_N=18" > /dev/null
