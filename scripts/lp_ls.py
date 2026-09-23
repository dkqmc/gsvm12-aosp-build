import io, struct, sys

IMG, SUPER_OFF = sys.argv[1], int(sys.argv[2], 0)
f = io.open(IMG, 'rb')

def rd(off, n):
    f.seek(off); return f.read(n)

geo = None
for cand in (SUPER_OFF + 4096, SUPER_OFF + 0x1000):
    b = rd(cand, 64)
    if b[:4] == b'alDg':
        geo = (cand, b); break
if not geo:
    # 暴力找
    blob = rd(SUPER_OFF, 1 << 20)
    i = blob.find(b'alDg')
    if i < 0: sys.exit('找不到 geometry magic alDg')
    geo = (SUPER_OFF + i, blob[i:i+64])
goff, gb = geo
magic2, = struct.unpack('<I', gb[36:40])
geo_size, first_meta_blk, blk_size, max_parts, slots = struct.unpack('<QIIII', gb[40:64])
print('geometry @0x%x: magic2=%s geometric_size=%d first_meta_blk=%d blk_size=%d max_partitions=%d slots=%d'
      % (goff, hex(magic2), geo_size, first_meta_blk, blk_size, max_parts, slots))

hdr = rd(SUPER_OFF + first_meta_blk * blk_size, 256)
if hdr[:4] != b'SPLA':
    sys.exit('header magic 不是 SPLA: %r' % hdr[:4])
major, minor, hdr_size = struct.unpack('<HHI', hdr[4:12])
tables_size, = struct.unpack('<I', hdr[72:76])
print('LpMetadataHeader SPLA v%d.%d header_size=%d tables_size=%d' % (major, minor, hdr_size, tables_size))
base = SUPER_OFF + first_meta_blk * blk_size

def table(off):
    o, s, es = struct.unpack('<III', hdr[80 + off*12: 92 + off*12])
    return (base + hdr_size + o) if False else (base + s and (o, s, es))

# 表描述符顺序: partitions, extents, groups, block_devices —— 每个 {offset,size,entry_size}
names = ['partitions', 'extents', 'groups', 'block_devices']
desc = {}
for i, n in enumerate(names):
    o, s, es = struct.unpack('<III', hdr[80 + 12*i: 92 + 12*i])
    desc[n] = (o, s, es)
    print('  table %-13s offset=0x%x size=%d entry_size=%d' % (n, o, s, es))

raw = rd(base, hdr_size + tables_size + 4096)
def rows(n):
    o, s, es = desc[n]
    blob = raw[o - hdr_size + hdr_size: o - hdr_size + hdr_size + s]
    blob = raw[o:o+s]
    return [blob[i*es:(i+1)*es] for i in range(s // es)]

bds = rows('block_devices')
for b in bds:
    nm = b[0:32].split(b'\x00')[0].decode('utf8', 'replace')
    first_data, size = struct.unpack('<QQ', b[40:56])
    print('  block_device %-10s first_data_block=%d size=%d (%.2f GiB)' % (nm, first_data, size, size/2**30))

exts = rows('extents')
parts = rows('partitions')
print('  %-16s %10s %14s %14s %s' % ('partition', 'nr_ext', 'start_sector', 'sectors', 'group'))
for i, p in enumerate(parts):
    nm = p[0:36].split(b'\x00')[0].decode('utf8', 'replace')
    attrs, fei, ne, gi = struct.unpack('<IIII', p[36:52])
    grp = p[52:88].split(b'\x00')[0].decode('utf8', 'replace')
    tot = 0
    start = 0
    for e in exts[fei:fei+ne]:
        nsec, st, pi, bi = struct.unpack('<IIII', e[0:16])
        tot += nsec; start = st
    print('  %-16s %10d %14d %14d %s   bytes=%d (%.2f GiB)' %
          (nm, ne, start, tot, grp, tot*512, tot*512/2**30))
