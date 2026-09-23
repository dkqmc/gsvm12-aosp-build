import io, os, struct, json

D = r"D:\Android\SDK\system-images\android-31\default\arm64-v8a"
NAMES = {0x00: 'SPARSE_UNSPECIFIED?', }

def classify(p):
    size = os.path.getsize(p)
    with io.open(p, 'rb') as f:
        head = f.read(512)
        f.seek(1024); sb = f.read(256)
    if head[:4] == bytes.fromhex('7928ff3a'):
        maj, minr, sz_hdr, blk_sz, nblk, magic2 = struct.unpack('<HHHHII', head[:16])
        return size, 'android-sparse', {'hdr': sz_hdr, 'block_size': blk_sz,
                                        'total_blocks': nblk, 'magic2': hex(magic2)}
    if head[:2] == b'\x1f\x8b':
        return size, 'gzip', None
    if head[:6] in (b'070701', b'070702'):
        return size, 'cpio-newc', None
    if head[:8] == b'ANDROID!':
        return size, 'android-boot', None
    if sb[0:4] == b'\xe2\xf5\xe1\x1e' or sb[0:4] == b'\xe2\xe1\xf5\xe0':
        return size, 'erofs', None
    if len(sb) >= 58 and sb[56:58] == b'\x53\xef':
        blk = 1024 << struct.unpack('<I', sb[24:28])[0]
        inc, rocc = struct.unpack('<II', sb[96+4:96+12])
        return size, 'ext4', {
            'block_size': blk,
            'blocks_count(lo32)': struct.unpack('<I', sb[4:8])[0],
            'inode_count': struct.unpack('<I', sb[0:4])[0],
            'incompat_features': hex(inc), 'ro_compat': hex(rocc),
            'first_log_block': sb[24], 'uuid': sb[8:24].hex(),
            'volume_name': sb[76:92].rstrip(b'\0').decode('utf8','replace')}
    return size, 'unknown', {'head': head[:16].hex(), 'at1024': sb[:16].hex()}

for fn in sorted(os.listdir(D)):
    p = os.path.join(D, fn)
    if not os.path.isfile(p) or not fn.endswith(('.img', '.rc', '.gz', '.img0')):
        continue
    size, kind, extra = classify(p)
    print('%-18s %13d  %-14s %s' % (fn, size, kind, json.dumps(extra or {})))
