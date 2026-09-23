import io, struct, sys
path, start, end = sys.argv[1], int(sys.argv[2], 0), int(sys.argv[3], 0)
f = io.open(path, 'rb'); f.seek(start)
CH = 64 << 20
pos = start
found = []
erofs_magic = bytes.fromhex('e2e1f5e0')
while pos < end:
    buf = f.read(min(CH, end - pos))
    if not buf: break
    i = 0
    while True:
        i = buf.find(b'\x53\xef', i)
        if i < 0: break
        abs_off = pos + i
        if (abs_off - start - 1080) % 4096 == 0:
            # 需要读超级块起点 = abs_off-56
            s = buf[max(0, i-56):i-56+120]
            if len(s) >= 120:
                inos = struct.unpack('<I', s[0:4])[0]
                blk = 1024 << struct.unpack('<I', s[24:28])[0]
                nblk_lo = struct.unpack('<I', s[4:8])[0]
                nblk_hi = struct.unpack('<I', s[68:72])[0]
                nblk = nblk_lo | (nblk_hi << 32)
                label = s[76:92].split(b'\x00')[0].decode('utf8', 'replace')
                inc = struct.unpack('<I', s[96:100])[0]
                found.append((abs_off - start - 1024, 'ext4', label, inos, nblk, blk, inc))
        i += 1
    j = 0
    while True:
        j = buf.find(erofs_magic, j)
        if j < 0: break
        if (pos + j - start) % 4096 == 0:
            found.append((pos + j - start, 'erofs', '', 0, 0, 0, 0))
        j += 1
    pos += len(buf)
print('扫描 %d MiB' % ((end - start) >> 20))
for off, kind, label, inos, nblk, blk, inc in found:
    if kind == 'ext4':
        flags = [n for b, n in [(0,'DIR_PREALLOC'),(1,'IMAGES'),(2,'EXTENTS'),(3,'RESERVED'),(4,'64BIT'),
                                (5,'MIRRORED'),(6,'FLEX_BG'),(7,'HASHTREE'),(8,'CSUM_SEED'),(22,'ORPHAN_PIN')
                       ] if inc >> b & 1]
        print('  @super+0x%09x  %-6s label=%-12s size=%6.2f GiB inodes=%-8d bs=%d  incompat=%s'
              % (off, kind, repr(label), nblk*blk/2**30, inos, blk, ','.join(flags) or '-'))
    else:
        print('  @super+0x%09x  erofs' % off)
