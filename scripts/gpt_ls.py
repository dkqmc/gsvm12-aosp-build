import io, os, struct, sys

SEC = 512

def fs_probe(f, off):
    """判断分区起始处的文件系统类型"""
    f.seek(off)
    h = f.read(4096)
    if len(h) < 1082:
        return 'too-small', {}
    if h[1024+56:1024+58] == b'\x53\xef':
        sb = h[1024:1024+120]
        blk = 1024 << struct.unpack('<I', sb[24:28])[0]
        nblocks = struct.unpack('<I', sb[4:8])[0] | (struct.unpack('<I', sb[68:72])[0] << 32)
        ninos = struct.unpack('<I', sb[0:4])[0]
        inc = struct.unpack('<I', sb[96:100])[0]
        names = []
        for bit, nm in [(0,'DIR_PREALLOC'),(1,'IMAGES'),(2,'EXTENTS'),(3,'RESERV'),(4,'64BIT'),
                        (5,'MIRRORED_FS'),(6,'FLEX_BG'),(7,'HASHTREE'),(8,'_metadata_csum_seed')]:
            if inc >> bit & 1: names.append(nm)
        return 'ext4', {'block_size': blk, 'blocks': nblocks, 'bytes': nblocks*blk,
                        'inodes': ninos, 'incompat': names}
    if h[1024:1028] in (b'\xe2\xf5\xe1\x1e', b'\xe2\xe1\xf5\xe0'):
        return 'erofs', {'magic': h[1024:1028].hex()}
    if h[0:4] == bytes.fromhex('7928ff3a'):
        return 'android-sparse', {}
    return 'unknown', {'head': h[:16].hex()}

def gpt(path):
    with io.open(path, 'rb') as f:
        f.seek(SEC)
        hdr = f.read(SEC)
        if hdr[:8] != b'EFI PART':
            print('%s: 非 GPT（头=%r）' % (os.path.basename(path), hdr[:8])); return
        e_lba = struct.unpack('<Q', hdr[72:80])[0]
        e_count, e_size = struct.unpack('<II', hdr[80:88])
        print('== %s  (%d bytes)  GPT: entries@LBA%d, %d x %dB' %
              (os.path.basename(path), os.path.getsize(path), e_lba, e_count, e_size))
        f.seek(e_lba * SEC)
        tbl = f.read(e_size * e_count)
        parts = []
        for i in range(e_count):
            en = tbl[i*e_size:(i+1)*e_size]
            if en[:16] == b'\x00'*16:
                continue
            tguid = '-'.join([en[0:4][::-1].hex(), en[4:6][::-1].hex(), en[6:8][::-1].hex(),
                              en[8:10].hex(), en[10:16].hex()])
            first, last = struct.unpack('<QQ', en[32:48])
            name = en[56:128].decode('utf-16-le', 'replace').split('\x00')[0]
            parts.append((name, first, last, tguid))
        for name, first, last, tguid in parts:
            off, size = first*SEC, (last-first+1)*SEC
            kind, info = fs_probe(f, off)
            extra = ' '.join('%s=%s' % (k, v) for k, v in info.items() if k != 'incompat')
            inc = info.get('incompat')
            print('  %-14s off=0x%09x size=%10d (%6.2f MiB)  %-13s %s %s' %
                  (name, off, size, size/2**20, kind, extra, ('['+','.join(inc)+']') if inc else ''))
            print('                 type_guid=%s' % tguid)

for p in sys.argv[1:]:
    gpt(p)
