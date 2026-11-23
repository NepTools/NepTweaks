#!/usr/bin/env python3
import os, struct, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, 'fonts', 'texgyreheroscn-bolditalic.otf')

def top(d):
    n = struct.unpack_from('<I', d, 4)[0]
    return list(zip(struct.unpack_from('<%dI' % n, d, 12),
                    struct.unpack_from('<%dI' % n, d, 12 + 4 * n)))

def sub(d, o):
    _, n, t, ho = struct.unpack_from('<4I', d, o)
    offs = struct.unpack_from('<%dI' % n, d, o + ho + 4)
    szs = struct.unpack_from('<%dI' % n, d, o + ho + 4 + 4 * n)
    return t, [(o + a, s) for a, s in zip(offs, szs)]

def gxt_textures(d, o):
    n = struct.unpack_from('<I', d, o + 8)[0]
    out = []
    for k in range(n):
        f = struct.unpack_from('<IIiIIIHH', d, o + 0x20 + 32 * k)
        out.append(dict(off=o + f[0], size=f[1], type=f[4], fmt=f[5], w=f[6], h=f[7]))
    return out

def morton(x, y, w, h):
    m, k, mn = 0, 0, min(w, h)
    while (1 << k) < mn:
        m |= ((y >> k) & 1) << (2 * k) | ((x >> k) & 1) << (2 * k + 1)
        k += 1
    if w > h: m |= (x >> k) << (2 * k)
    elif h > w: m |= (y >> k) << (2 * k)
    return m

def c565(c):
    return np.array([((c >> 11) & 31) * 255 // 31, ((c >> 5) & 63) * 255 // 63,
                     (c & 31) * 255 // 31], dtype=np.int32)

def e565(c):
    r, g, b = (int(v) for v in c)
    return ((r * 31 + 127) // 255) << 11 | ((g * 63 + 127) // 255) << 5 | ((b * 31 + 127) // 255)

def enc_color(px):
    rgb = px[:, :3].astype(np.int32); a = px[:, 3]
    w = rgb[a > 0] if (a > 0).any() else rgb
    c0, c1 = e565(w.max(0)), e565(w.min(0))
    if c0 < c1: c0, c1 = c1, c0
    if c0 == c1: return struct.pack('<HHI', c0, c1, 0)
    p0, p1 = c565(c0), c565(c1)
    pal = np.array([p0, p1, (2 * p0 + p1) // 3, (p0 + 2 * p1) // 3])
    idx = ((rgb[:, None, :] - pal[None]) ** 2).sum(2).argmin(1)
    return struct.pack('<HHI', c0, c1, sum(int(v) << (2 * i) for i, v in enumerate(idx)))

def enc_alpha(a):
    a = a.astype(np.int32); a0, a1 = int(a.max()), int(a.min())
    if a0 == a1: return bytes([a0, a1]) + bytes(6)
    pal = np.array([a0, a1] + [((6 - i) * a0 + (i + 1) * a1) // 7 for i in range(6)])
    idx = np.abs(a[:, None] - pal[None]).argmin(1)
    return bytes([a0, a1]) + sum(int(v) << (3 * i) for i, v in enumerate(idx)).to_bytes(6, 'little')

def encode_dxt5(img, swizzled):
    a = np.array(img.convert('RGBA')); h, w = a.shape[:2]; bw, bh = w // 4, h // 4
    out = bytearray(bw * bh * 16)
    for by in range(bh):
        for bx in range(bw):
            px = a[by * 4:by * 4 + 4, bx * 4:bx * 4 + 4].reshape(16, 4)
            i = morton(bx, by, bw, bh) if swizzled else by * bw + bx
            out[i * 16:i * 16 + 16] = enc_alpha(px[:, 3]) + enc_color(px)
    return bytes(out)

def label(text, fs, size, fill, outline, baseline, left=None, center=None):
    f = ImageFont.truetype(FONT, fs)
    im = Image.new('RGBA', size, (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
    if center is not None:
        left = int(round(center - dr.textlength(text, font=f) / 2))
    dr.text((left, baseline), text, font=f, fill=fill, stroke_width=2,
            stroke_fill=outline, anchor='ls')
    return im

JOBS = [
    (1, 7, lambda: label('NepTweaks', 28, (256, 64), (240, 240, 240, 255),
                         (32, 8, 32, 255), baseline=45, left=34)),
    (9, 0, lambda: label('Costume Break', 27, (256, 32), (244, 244, 244, 255),
                         (160, 80, 240, 255), baseline=24, center=131)),
    (9, 1, lambda: label('60 FPS', 27, (256, 32), (244, 244, 244, 255),
                         (160, 80, 240, 255), baseline=24, center=131)),
    (9, 2, lambda: label('Retire Anytime', 27, (256, 32), (244, 244, 244, 255),
                         (160, 80, 240, 255), baseline=24, center=131)),
]
ORIG_SIZE = 1453504

def main(src, dst):
    d = bytearray(open(src, 'rb').read())
    if len(d) != ORIG_SIZE:
        sys.exit(f'unexpected config_2d.cat size {len(d)} (expected {ORIG_SIZE})')
    _, sheets = sub(d, top(d)[1][0])
    for sheet, tex, make in JOBS:
        t = gxt_textures(d, sheets[sheet][0])[tex]
        img = make()
        assert t['fmt'] == 0x87000000 and (t['w'], t['h']) == img.size, 'texture layout mismatch'
        enc = encode_dxt5(img, t['type'] == 0)
        assert len(enc) == t['size']
        d[t['off']:t['off'] + t['size']] = enc
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    open(dst, 'wb').write(d)
    print('wrote', dst)

if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit('usage: build_assets.py <original config_2d.cat> <output config_2d.cat>')
    main(sys.argv[1], sys.argv[2])
