import struct,sys,zlib,hashlib
selfp,elfp,patchedp,outp=sys.argv[1:5]
s=bytearray(open(selfp,'rb').read()); e=open(elfp,'rb').read(); pe=open(patchedp,'rb').read()
po=0xe0; sio=0x180; cio=0x230
dig_off=cio+16+0x14
print('digest matches sha256(orig elf):', s[dig_off:dig_off+32]==hashlib.sha256(e).digest())
ph=lambda d,i,base: struct.unpack_from('<IIIIIIII',d,base+32*i)
ep=struct.unpack_from('<I',e,0x1c)[0]
changed=False
for i in range(5):
    p=ph(e,i,ep); off,ln,comp,enc=struct.unpack_from('<QQQQ',s,sio+32*i)
    orig=e[p[1]:p[1]+p[4]]; new=pe[p[1]:p[1]+p[4]]
    data=zlib.decompress(bytes(s[off:off+ln])) if comp==2 else bytes(s[off:off+ln])
    assert data==orig, f'seg {i}: SELF contents do not match ELF'
    if new==orig: continue
    changed=True
    for lvl in (9,):
        c=zlib.compress(new,lvl)
    print(f'seg {i}: orig {hex(ln)} new {hex(len(c))}')
    assert len(c)<=ln, 'recompressed segment does not fit in place'
    s[off:off+ln]=c+b'\0'*(ln-len(c))
    struct.pack_into('<Q',s,sio+32*i+8,len(c))
    assert zlib.decompress(bytes(s[off:off+len(c)]))==new
assert changed
s[dig_off:dig_off+32]=hashlib.sha256(pe).digest()
open(outp,'wb').write(s); print('wrote',outp)
