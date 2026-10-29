// №912 диагностика (только smokeOn): что лежит в вершинах города и сколько кусков/треугольников на текстуру. Не для релиза.
static unsigned fdVerts[1024], fdLow[1024], fdWhite[1024], fdPieces[1024], fdTris[1024]; static unsigned long long fdLuma[1024]; static unsigned fdFl[1024]; static int fdDumped;
static void fdPiece(const Piece *d, const unsigned char *b) {
  int t = d->r.tex; if (t < 0 || t >= 1024 || d->r.owner != 0) return;
  if (!(d->r.flags & F_NOIDX) || (d->r.flags & F_STRIP)) { fdPieces[t]++; fdTris[t] += (unsigned)d->r.ni / 3u; return; }   // полосы и индексные куски — только счёт
  int v12 = (d->r.flags & F_V12) != 0; unsigned vs = v12 ? 12 : 16, n = (unsigned)d->r.ni; if (n > 65535) return;
  for (unsigned i = 0; i < n; i++) { const unsigned char *q = b + i * vs + 4; unsigned r, g, bl;
    if (v12) { unsigned short c = *(const unsigned short *)q; r = (c & 31) * 255 / 31; g = ((c >> 5) & 63) * 255 / 63; bl = (c >> 11) * 255 / 31; }
    else { r = q[0]; g = q[1]; bl = q[2]; }
    unsigned l = (299 * r + 587 * g + 114 * bl) / 1000; fdLuma[t] += l; if (l < 200) fdLow[t]++; if (l >= 250) fdWhite[t]++; }
  fdVerts[t] += n; fdPieces[t]++; fdTris[t] += n / 3; fdFl[t] |= 1u << (d->r.flags & 7);
}
static void fdDump(void) {
  if (fdDumped || !smkOn || !flatDump) return; fdDumped = 1; smkWrite("FDIAG header id w h t4 slope ground tst4 mean(rgb) k255 pieces tris meanLuma lowfrac whitefrac flagsMask\n");
  for (unsigned t = 0; t < ntex && t < 1024; t++) { if (!fdPieces[t]) continue; const Tex *x = &tex[t]; char s[256];
    snprintf(s, sizeof s, "FDIAG %u %d %d %d %.2f %d %d %d,%d,%d %d p=%u tr=%u ml=%u lo=%.2f wh=%.2f fl=%x\n", t, x->w, x->h, x->t4, x->slope, x->ground, x->tstat[4], x->tstat[0], x->tstat[1], x->tstat[2], x->tstat[3],
             fdPieces[t], fdTris[t], (unsigned)(fdLuma[t] / (fdVerts[t] ? fdVerts[t] : 1)), (float)fdLow[t] / (fdVerts[t] ? fdVerts[t] : 1), (float)fdWhite[t] / (fdVerts[t] ? fdVerts[t] : 1), fdFl[t]); smkWrite(s); }
}
static void fdReset(void) { memset(fdVerts, 0, sizeof fdVerts); memset(fdLow, 0, sizeof fdLow); memset(fdWhite, 0, sizeof fdWhite); memset(fdPieces, 0, sizeof fdPieces); memset(fdTris, 0, sizeof fdTris); memset(fdLuma, 0, sizeof fdLuma); memset(fdFl, 0, sizeof fdFl); fdDumped = 0; }
