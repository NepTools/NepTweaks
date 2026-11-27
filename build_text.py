#!/usr/bin/env python3
import struct, sys, os

TABLE = 1

TEXTS = {
    130: ("Activate some high-five-worthy game-breaking system settings...for free!",
          "Toggle the NepTweaks gameplay tweaks."),
    137: ("Gain the ability to select the HDD forms of characters during Character Select.",
          "Hard hitting attacks tear ur clothes and u might not want that :("),
    138: ("Receive no HP damage from enemies.",
          "Run the game at 60 FPS instead of 30. Game speed stays the same."),
    139: ("Negate any stagger or knock back effects from enemy attacks.",
          "You can retire in any quest now (^o^)"),
    140: ("Defeat any and all enemies with a single hit.",
          "Take whoever u want into any quest, no more forced party picks!"),
    141: ("The EXE Drive gauge will always be filled.",
          "Reserved for a future NepTweaks option <3"),
    142: ("The SP gauge will always be filled.",
          "Reserved for a future NepTweaks option <3"),
}

ORIG_SIZE = 0x1BD30

def align(x, a=16):
    return (x + a - 1) // a * a

def read_section(d, o):
    _, n, t, ho = struct.unpack_from('<4I', d, o)
    offs = struct.unpack_from('<%dI' % n, d, o + ho + 4)
    szs = struct.unpack_from('<%dI' % n, d, o + ho + 4 + 4 * n)
    return ho, [bytes(d[o + a:o + a + s]) for a, s in zip(offs, szs)], offs[0]

def rebuild_table(blob, edits):
    n = struct.unpack_from('<I', blob, 0)[0]
    ents = [struct.unpack_from('<II', blob, 4 + 8 * i) for i in range(n)]
    strs = [blob[off:blob.index(b'\0', off)] for off, _ in ents]
    for i, (old, new) in edits.items():
        if strs[i] != old.encode('cp932'):
            sys.exit(f'entry {i}: unexpected original text {strs[i]!r}')
        try:
            strs[i] = new.encode('cp932')
        except UnicodeEncodeError as e:
            sys.exit(f'entry {i}: {new[e.start:e.end]!r} cannot be shown by the game (text must be Shift-JIS)')
    head = bytearray(struct.pack('<I', n))
    body = bytearray()
    pos = 4 + 8 * n
    for (_, h), s in zip(ents, strs):
        head += struct.pack('<II', pos + len(body), h)
        body += s + b'\0'
    return bytes(head + body)

def main(src, dst):
    d = open(src, 'rb').read()
    if len(d) != ORIG_SIZE:
        sys.exit(f'unexpected text.cat size {len(d)} (expected {ORIG_SIZE})')
    n_top = struct.unpack_from('<I', d, 4)[0]
    top_offs = struct.unpack_from('<%dI' % n_top, d, 12)
    top_szs = struct.unpack_from('<%dI' % n_top, d, 12 + 4 * n_top)
    s0 = top_offs[0]
    ho, tables, first = read_section(d, s0)
    tables[TABLE] = rebuild_table(tables[TABLE], TEXTS)
    sec = bytearray(d[s0:s0 + first])
    offs, szs = [], []
    for t in tables:
        sec += bytes(align(len(sec)) - len(sec))
        offs.append(len(sec)); szs.append(len(t))
        sec += t
    sec += bytes(align(len(sec)) - len(sec))
    n = len(tables)
    struct.pack_into('<%dI' % n, sec, ho + 4, *offs)
    struct.pack_into('<%dI' % n, sec, ho + 4 + 4 * n, *szs)
    out = bytearray(d[:s0]) + sec
    new_offs, new_szs = [s0], [len(sec)]
    for i in range(1, n_top):
        out += bytes(align(len(out)) - len(out))
        new_offs.append(len(out)); new_szs.append(top_szs[i])
        out += d[top_offs[i]:top_offs[i] + top_szs[i]]
    struct.pack_into('<%dI' % n_top, out, 12, *new_offs)
    struct.pack_into('<%dI' % n_top, out, 12 + 4 * n_top, *new_szs)
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    open(dst, 'wb').write(out)
    print('wrote', dst)

if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit('usage: build_text.py <original text.cat> <output text.cat>')
    main(sys.argv[1], sys.argv[2])
