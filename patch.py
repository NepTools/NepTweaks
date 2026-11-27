#!/usr/bin/env python3
import struct, sys
from keystone import Ks, KS_ARCH_ARM, KS_MODE_THUMB

BASE, FOFF = 0x81000000, 0xE0
NOP = bytes.fromhex('00bf')
ks = Ks(KS_ARCH_ARM, KS_MODE_THUMB)

def asm(src, addr):
    enc, _ = ks.asm(src, addr)
    return bytes(enc)

RETIRE = 0x81094E7C
GATE = 0x81094E90
FPS_THRESHOLD = 0x81094EA4
FPS_VBLANK = 0x81094EB8
REGION_END = 0x81094ECE
ANY_CHARA = 0x8105CE58
ANY_CHARA_END = 0x8105CE9E

PATCHES = [
    ("IsCheatOwned: rows 0-3 always owned", 0x8105CE0E, "2de9f041002801db052801dd", 0x8105CE18,
     """cmp r0, #3
        ite ls
        movls r0, #1
        movhi r0, #0
        bx lr"""),

    ("Any character: option helper", ANY_CHARA, None, ANY_CHARA_END,
     """ands r1, r2
        bne yes
        movs r0, #3
        bl #0x8105cec2
        cbz r0, no
     yes:
        movs r0, #1
        pop {r4, pc}
     no:
        pop {r4, pc}"""),

    ("Any character: quest roster check", 0x81064B6A, "096e114000d0", None,
     """ldr r1, [r1, #0x60]
        b.w #%#x""" % ANY_CHARA),

    ("GetCheat: disable all cheat effects", 0x8105CEB6, "002801db", None,
     """movs r0, #0
        bx lr"""),

    ("Config page: show real row value", 0x810D90E6, "83f7e6fe", None,
     "bl #0x8105cec2"),

    ("SetBreakTable: compact copy", 0x81094E56, "0022c0f83822002935d0", GATE,
     """movs r2, #0
        str.w r2, [r0, #0x238]
        cbz r1, out
        ldr r2, [r1]
        cmp r2, #1
        ble out
        add.w r3, r0, #0x23c
        str.w r3, [r0, #0x238]
        movs r2, #16
     loop:
        ldr r12, [r1], #4
        str r12, [r3], #4
        subs r2, #1
        bne loop
     out:
        bx lr"""),

    ("Retire anytime: option helper", RETIRE, None, GATE,
     """movs r0, #2
        bl #0x8105cec2
        pop {r4, pc}"""),

    ("Retire anytime: CanRetire", 0x8106A73C, "002000e0", None,
     "b.w #%#x" % RETIRE),

    ("BreakTable gate: Costume Break option", GATE, None, FPS_THRESHOLD,
     """push {r1, r2, r3, lr}
        mov r2, r0
        movs r0, #0
        bl #0x8105cec2
        cbz r0, ret
        ldr.w r0, [r2, #0x238]
     ret:
        pop {r1, r2, r3, pc}"""),

    ("GetBreakTable: route through gate", 0x810948C4, "d0f83802", None,
     "b.w #%#x" % GATE),

    ("Model loader: read table directly", 0x81090292, "04f017fb", None,
     "ldr.w r0, [r0, #0x238]"),

    ("60 FPS: limiter threshold helper", FPS_THRESHOLD, None, FPS_VBLANK,
     """push {r0, r1, r2, lr}
        movs r0, #1
        bl #0x8105cec2
        vmov.f32 s3, #1.0
        cbz r0, done
        vmov.f32 s3, #0.5
     done:
        pop {r0, r1, r2, pc}"""),

    ("60 FPS: vblank count helper", FPS_VBLANK, None, REGION_END,
     """push {r4, lr}
        mov r4, r1
        movs r0, #1
        bl #0x8105cec2
        cbnz r0, flip
        adds r0, r4, #1
     flip:
        blx #0x81271fe8
        pop {r4, pc}"""),

    ("60 FPS: frame limiter", 0x81191B6A, "f7ee001a", None,
     "bl #%#x" % FPS_THRESHOLD),

    ("60 FPS: display flip", 0x81191BF0, "481ce0f0fae9", None,
     """bl #%#x
        nop""" % FPS_VBLANK),
]

def reloc_sites(d):
    ph = struct.unpack_from('<I', d, 0x1c)[0]
    phnum = struct.unpack_from('<H', d, 0x2c)[0]
    sites = set()
    for i in range(phnum):
        p = struct.unpack_from('<8I', d, ph + 32 * i)
        if p[0] != 0x60000000:
            continue
        b = d[p[1]:p[1] + p[4]]
        pos = 0
        while pos + 8 <= len(b):
            w0 = struct.unpack_from('<I', b, pos)[0]
            if w0 & 0xf == 0:
                offset = struct.unpack_from('<I', b, pos + 8)[0]
                if (w0 >> 16) & 0xf == 0:
                    sites.add(offset)
                    if (w0 >> 20) & 0xff:
                        sites.add(offset + ((w0 >> 28) & 0xf) * 2)
                pos += 12
            elif w0 & 0xf == 1:
                w1 = struct.unpack_from('<I', b, pos + 4)[0]
                if (w0 >> 16) & 0xf == 0:
                    sites.add((w0 >> 20) | ((w1 & 0xfffff) << 12))
                pos += 8
            else:
                sys.exit(f'unknown relocation format {w0 & 0xf}')
    return {BASE + x for x in sites}

def main(src, dst):
    d = bytearray(open(src, 'rb').read())
    relocs = reloc_sites(d)
    for name, va, expect, end, code in PATCHES:
        fo = va - BASE + FOFF
        b = asm(code, va)
        if end:
            if va + len(b) > end:
                sys.exit(f'{name}: {len(b)} bytes does not fit before {end:#x}')
            b += NOP * ((end - va - len(b)) // 2)
        if expect:
            exp = bytes.fromhex(expect)
            got = bytes(d[fo:fo + len(exp)])
            if got != exp:
                sys.exit(f'{name}: unexpected original bytes {got.hex()} (wrong eboot version?)')
        hit = sorted(r for r in relocs if va - 3 <= r < va + len(b))
        if hit:
            sys.exit(f'{name}: overlaps relocated code at ' + ', '.join(f'{r:#x}' for r in hit))
        d[fo:fo + len(b)] = b
        print(f'{name:40s} @ {va:#x}  {len(b)} bytes')
    open(dst, 'wb').write(d)
    print('wrote', dst)

if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit('usage: patch.py <original eboot.bin.elf> <patched eboot.bin.elf>')
    main(sys.argv[1], sys.argv[2])
