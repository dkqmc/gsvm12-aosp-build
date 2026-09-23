import io, sys
f = io.open(sys.argv[1], 'rb'); base = int(sys.argv[2], 0); off = int(sys.argv[3], 0)
f.seek(base + off)
b = f.read(int(sys.argv[4]))
for i in range(0, len(b), 32):
    print('%08x | %-64s |%s' % (off + i, b[i:i+32].hex(), ''.join(chr(c) if 32 <= c < 127 else '.' for c in b[i:i+32])))
