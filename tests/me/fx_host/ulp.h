// Правка 313: красный контроль сверки частиц — expf на 1 ulp ближе к нулю (tests/me/run.py): стенд обязан это заметить
#include <math.h>
static inline float fxhExpfUlp(float x) { return nextafterf(expf(x), 0.f); }
