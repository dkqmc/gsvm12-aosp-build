import io, sys
path, start = sys.argv[1], int(sys.argv[2], 0)
span = int(sys.argv[3], 0) if len(sys.argv) > 3 else 1 << 27
pats = {b'SPLA': 'SPLA', bytes.fromhex('534c5041'): 'SPLA-be?',
        b'gDla': 'geom-gDla', b'alDg': 'geom-alDg',
        bytes.fromhex('73676f6c'): 'log?'}
f = io.open(path, 'rb')
CH = 1 << 20; carry = b''; pos = start; hits = {}
f.seek(start)
while pos - start < span:
    buf = f.read(CH)
    if not buf: break
    blob = carry + buf
    base = pos - len(carry)
    for p, nm in pats.items():
        i = 0
        while True:
            i = blob.find(p, i)
            if i < 0: break
            hits.setdefault(nm, []).append(base + i)
            i += 1
    carry = blob[-16:]
    pos += len(buf)
for nm, offs in hits.items():
    print('%-10s %d hits, first: %s' % (nm, len(offs), ['0x%x' % o for o in offs[:6]]))
if not hits: print('窗口内 0 命中（扫描 %d MiB）' % (span >> 20))
