import io, os
D = r"D:\Android\SDK\system-images\android-31\default\arm64-v8a"
for fn in ['system.img', 'userdata.img', 'vendor.img']:
    p = os.path.join(D, fn)
    with io.open(p, 'rb') as f:
        f.seek(0); a = f.read(64)
        f.seek(1024); b = f.read(128)
        zeros64k = 0
        f.seek(0)
        for i in range(0, 1 << 20, 512):
            f.seek(i)
            if f.read(512) == b'\x00' * 512:
                zeros64k += 1
    print('###', fn, 'size=%d' % os.path.getsize(p))
    print('   0    :', a[:32].hex(), '|', a[32:64].hex())
    print('   1024 :', b[:32].hex(), '|', b[32:64].hex())
    print('   1088 :', b[64:96].hex(), '|', b[96:128].hex())
    print('   sb+56 (ext4 magic 应为 53ef):', b[56:58].hex())
    print('   前 1MiB 内全零 512B 块数:', zeros64k, '/2048')
