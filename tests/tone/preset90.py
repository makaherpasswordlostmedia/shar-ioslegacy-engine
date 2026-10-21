# Проба пресета «Мультик 90-х» по точкам кадра (как будет на палитрах): серое -> лаванда, насыщенность, плёнка (индиго..кремовый)
import sys, numpy as np
from PIL import Image
INK = np.array([0x2A, 0x24, 0x40]) / 255.; CREAM = np.array([0xF2, 0xEE, 0xDC]) / 255.
def rgb2hsv(c):
    mx = c.max(-1); mn = c.min(-1); d = mx - mn; v = mx; s = np.where(mx > 0, d / np.maximum(mx, 1e-9), 0)
    r, g, b = c[..., 0], c[..., 1], c[..., 2]; h = np.zeros_like(mx); dd = np.maximum(d, 1e-9)
    h = np.where(mx == r, ((g - b) / dd) % 6, h); h = np.where(mx == g, (b - r) / dd + 2, h); h = np.where(mx == b, (r - g) / dd + 4, h)
    return np.where(d > 0, h / 6, 0), s, v
def hsv2rgb(h, s, v):
    i = np.floor(h * 6) % 6; f = h * 6 - np.floor(h * 6); p = v * (1 - s); q = v * (1 - f * s); t = v * (1 - (1 - f) * s)
    out = np.stack([np.select([i == k for k in range(6)], [v, q, p, p, t, v]), np.select([i == k for k in range(6)], [t, v, v, q, p, p]),
                    np.select([i == k for k in range(6)], [p, p, t, v, v, q])], -1); return out
PAL = ['#3fa9e0','#2d7fd0','#6fc3e8','#3a30b8','#241c78','#5a2ea0','#aaa8e8','#b8b4f0','#7a3fc8','#e2533a','#f08a2e','#f5a04a',
       '#f06a9a','#f4a6c8','#7fd3a8','#2b7f8a','#8cc63a','#2f6b2a','#d9a32c','#c9b53a','#8e1b14','#d8b88a']
PALH = None
def hue_snap(c, k):
    global PALH
    if PALH is None:
        P = np.array([[int(x[i:i+2], 16) for i in (1, 3, 5)] for x in PAL], float) / 255; PALH = np.stack(rgb2hsv(P), -1)
    h, s, v = rgb2hsv(c); dh = np.abs(h[..., None] - PALH[:, 0]); dh = np.minimum(dh, 1 - dh)
    j = (dh * 3 + np.abs(v[..., None] - PALH[:, 2]) * 1.2 + np.abs(s[..., None] - PALH[:, 1]) * 1.0).argmin(-1); th = PALH[j, 0]
    d = ((th - h + .5) % 1) - .5; w = np.clip((s - .12) / .1, 0, 1) * k            # только цветное (не серое): оттенок к ближнему цвету палитры 90-х
    return hsv2rgb((h + d * w) % 1, s + (np.maximum(s, PALH[j, 1]) - s) * w * .5, v)
def hue_to(h, tgt, w): d = ((tgt - h + .5) % 1) - .5; return (h + d * w) % 1   # по короткой дуге (viewer/tone.c hueTo)
def band_w(hd, a, b, ramp):   # 1 внутри [a, b], к краям спад ramp° (viewer/tone.c bandW)
    x = hd
    if a > b: x = np.where(x < b + ramp, x + 360., x); b = b + 360.
    return np.clip((x - a + ramp) / ramp, 0, 1) * np.clip((b + ramp - x) / ramp, 0, 1)
def preset(c, snap=0.3, grey=0.15, lav_h=250 / 360., lav_s=0.20, lav_w=0.7, sat=None, dark=None, dark_w=None, light=0.80, light_w=0.75, old=False, new801=True, new825=True):
    # №780 (old=False, как viewer/tone.c без TONE_T90_780_OLD): анти-болото, мягче к туши, середины светлее + S-кривая, насыщенность ×1,5; old=True — пресет №754 (TEST33)
    sat = sat if sat is not None else (1.35 if old else 1.50)
    dark = dark if dark is not None else (0.30 if old else 0.22)
    dark_w = dark_w if dark_w is not None else (0.85 if old else 0.60)
    c = hue_snap(c, snap)
    if not old:   # 1б) олива 55..85° -> к жёлтому или зелёному, светлее и сочнее
        h, s, v = rgb2hsv(c); hd = h * 360.
        wo = np.clip(1 - np.abs(hd - 70.) / 25., 0, 1) * np.clip((s - .12) / .1, 0, 1)
        h2 = (h + np.where(hd < 70., -1., 1.) * wo * (18. / 360.)) % 1
        v2 = np.where(v < .80, v + (.80 - v) * .40 * wo, v); s2_ = s + (np.maximum(s, .70) - s) * .35 * wo
        c = np.where((wo > 0)[..., None], hsv2rgb(h2, s2_, v2), c)
    if not old and new801:   # 1в) №801: трава -> изумрудный 152°, тёмно-коричневое -> ржавый 18° (как viewer/tone.c без TONE_T90_801_OLD)
        h, s, v = rgb2hsv(c); hd = h * 360.; sc = np.clip((s - .20) / .15, 0, 1)
        wg = np.clip((hd - 70.) / 10., 0, 1) * np.clip((170. - hd) / 15., 0, 1) * sc * .95
        wr = np.clip((hd - 12.) / 8., 0, 1) * np.clip((42. - hd) / 8., 0, 1) * sc * np.clip((.60 - v) / .15, 0, 1) * .50
        gS, gV = (.56, .44) if new825 else (.50, .48)   # №825: трава капельку насыщеннее и темнее
        hg = h + (158. / 360. - h) * wg; sg = s + (np.minimum(s, gS) - s) * wg / .95; vg = v + (gV - v) * .40 * wg / .95
        hr = (h + (18. / 360. - h) * wr) % 1; sr = s + (np.maximum(s, .65) - s) * .6 * wr / .5; vr = np.where(v < .45, v + (.45 - v) * .35 * wr / .5, v)
        cg = hsv2rgb(hg, sg, vg); cr = hsv2rgb(hr, sr, vr)
        c = np.where((wg > 0)[..., None], cg, np.where((wr > 0)[..., None], cr, c))
    if not old and new801 and new825:   # 1г) №825: креветочный, олива, navy / голубой / бирюза (как viewer/tone.c)
        h, s, v = rgb2hsv(c); hd = h * 360.; sc = np.clip((s - .15) / .15, 0, 1)
        ww = band_w(hd, 352., 36., 12.) * sc * np.clip((v - .50) / .15, 0, 1) * .70
        wo = band_w(hd, 48., 78., 12.) * np.clip((s - .40) / .15, 0, 1) * np.clip((.62 - v) / .12, 0, 1) * .60
        wb = band_w(hd, 188., 232., 18.) * sc; wt = band_w(hd, 170., 188., 10.) * sc * .70
        h = np.where(ww > 0, hue_to(h, 13. / 360., ww), h); s = np.where(ww > 0, s + (.55 - s) * .50 * ww, s); v = np.where(ww > 0, v + (np.maximum(v, .90) - v) * .40 * ww, v)
        h = np.where(wo > 0, hue_to(h, 74. / 360., wo), h); s = np.where(wo > 0, s + (np.maximum(s, .55) - s) * .60 * wo, s); v = np.where(wo > 0, v + (.50 - v) * .40 * wo, v)
        wd = np.clip((.55 - v) / .25, 0, 1); hb = (224. * wd + 200. * (1 - wd)) / 360.
        h = np.where(wb > 0, hue_to(h, hb, wb * .70), h)
        st = .50 + (np.maximum(s, .72) - .50) * wd; vt = np.maximum(v, .86) + (.36 - np.maximum(v, .86)) * wd
        s = np.where(wb > 0, s + (st - s) * .50 * wb, s); v = np.where(wb > 0, v + (vt - v) * .35 * wb, v)
        h = np.where(wt > 0, hue_to(h, 178. / 360., wt), h); s = np.where(wt > 0, s + (np.maximum(s, .55) - s) * .50 * wt, s); v = np.where(wt > 0, v + (np.maximum(v, .62) - v) * .30 * wt, v)
        c = np.where(((ww > 0) | (wo > 0) | (wb > 0) | (wt > 0))[..., None], hsv2rgb(h, s, v), c)
    h, s, v = rgb2hsv(c)
    mid = np.clip((v - 0.12) / 0.15, 0, 1) * np.clip((0.88 - v) / 0.15, 0, 1)      # средние серые (не белое и не чёрное)
    w = (np.clip((grey - s) / grey, 0, 1) * mid)[..., None] * lav_w                  # серое -> лаванда/барвинок той же яркости
    c = c * (1 - w) + hsv2rgb(np.full_like(h, lav_h), np.full_like(s, lav_s), v) * w
    v = c.max(-1, keepdims=True); s2 = (v - c.min(-1, keepdims=True)) / np.maximum(v, 1e-6)
    if not old and new801:   # 3) №801: тёмное — глубокий тон своего оттенка, серо-чёрное — к глубокой сливе #2E2257
        DEEP = np.array([0x2E, 0x22, 0x57]) / 255.
        w3 = np.clip(1 - v / .30, 0, 1); hh, ss, vv = rgb2hsv(c); wc = np.clip((ss - .10) / .10, 0, 1)[..., None]
        if new825: hh = hue_to(hh, 235. / 360., w3[..., 0] * .35 * np.clip((ss - .10) / .15, 0, 1))   # №825: тёмное уходит в синее
        c3 = hsv2rgb(hh, ss + (np.maximum(ss, .62) - ss) * .6 * w3[..., 0], vv + (.24 - vv) * .5 * w3[..., 0])
        c = np.where(w3 > 0, c + (c3 - c) * wc, c); wn = (1 - wc) * w3 * .7; c = c + (DEEP - c) * wn
    else:
        wd = np.clip(1 - v / dark, 0, 1) * dark_w; c = c + (INK - c) * wd                 # плёнка: тёмное -> индиго
    wl = np.clip((v - light) / (1 - light), 0, 1) * light_w * np.clip(1 - s2 / .4, 0, 1); c = c + (CREAM - c) * wl   # светлое (белёсое, не цветное) -> кремовый
    if not old:   # 3б) звонче: середины светлее (степень 0,94) и мягкая S-кривая +10 %
        x = np.clip(c, 0, 1) ** (.90 if new801 else .94); c = x + (x - .5) * .10 * (1 - np.abs(2 * x - 1))   # №784: светлее
    y = (c * [.299, .587, .114]).sum(-1, keepdims=True); d = c - y                   # насыщенность с мягким потолком (после плёнки)
    lim = np.where(d > 1e-3, (1 - y) / np.maximum(d, 1e-3), np.where(d < -1e-3, -y / np.minimum(d, -1e-3), 1e9)).min(-1, keepdims=True)
    k = np.clip(np.minimum(sat, lim), 1, None); c = y + d * k
    if not old and new801 and new825:   # 5) №825: анти-неон — светлое зелёно-голубое S не больше 0,82
        c = np.clip(c, 0, 1); h, s, v = rgb2hsv(c); wn = band_w(h * 360., 55., 200., 10.) * np.clip((v - .78) / .10, 0, 1)
        m = (wn > 0) & (s > .82); c = np.where(m[..., None], hsv2rgb(h, s + (.82 - s) * wn, v), c)
    return c
if __name__ == '__main__':
    src, dst = sys.argv[1], sys.argv[2]; a = np.asarray(Image.open(src).convert('RGB')).astype(float) / 255
    b = preset(a); H, W = a.shape[:2]; b[: int(H * .27)] = a[: int(H * .27)]   # служебные строки сверху — как есть
    Image.fromarray((np.clip(np.concatenate([a, b], 1), 0, 1) * 255).astype(np.uint8)).save(dst)
