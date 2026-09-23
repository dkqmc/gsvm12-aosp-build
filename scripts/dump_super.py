import io, sys
IMG, OFF = sys.argv[1], int(sys.argv[2], 0)
f = io.open(IMG, 'rb'); f.seek(OFF)
for a in range(0, 0x2000, 256):
    f.seek(OFF + a); b = f.read(256)
    txt = ''.join(chr(c) if 32 <= c < 127 else '.' for c in b)
    print('%08x |%s|%s' % (a, b[:16].hex()+b[16:32].hex(), txt[:32]))
blob = f.read(1 << 20)
for m in (b'SPLA', bytes.fromhex('616c4467'), bytes.fromhex('67446c61'), b'aldg', b'gdla'):
    print('find %r -> %d' % (m, blob.find(m)))
