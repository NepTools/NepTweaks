#!/usr/bin/env python3
import sys
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

PATCHES = [
    ("IsCheatOwned: rows 0-2 always owned", 0x8105CE12, "002801db052801dd", None,
     """cmp r0, #2
        bls #0x8105ce84
        cmp r0, #5
        bls #0x8105ce1e"""),

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

def main(src, dst):
    d = bytearray(open(src, 'rb').read())
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
        d[fo:fo + len(b)] = b
        print(f'{name:40s} @ {va:#x}  {len(b)} bytes')
    open(dst, 'wb').write(d)
    print('wrote', dst)

if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit('usage: patch.py <original eboot.bin.elf> <patched eboot.bin.elf>')
    main(sys.argv[1], sys.argv[2])
