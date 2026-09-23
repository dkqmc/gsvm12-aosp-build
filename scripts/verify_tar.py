#!/usr/bin/env python3
"""核对 tar 是否保住了 ATIT 打包需要的元数据：mode/uid/gid/符号链接/selinux xattr。"""
import io, sys, tarfile, collections

for path in sys.argv[1:]:
    t = tarfile.open(path)
    n = x = link = 0
    xa_keys = collections.Counter()
    samples = []
    owners = collections.Counter()
    for m in t:
        n += 1
        ph = m.pax_headers or {}
        k = [key for key in ph if 'security.selinux' in key]
        if k:
            x += 1
            xa_keys[ph[k[0]][:40]] += 1
            if len(samples) < 6:
                samples.append((m.name, oct(m.mode), m.uid, m.gid, ph[k[0]]))
        if m.issym():
            link += 1
        owners[(m.uid, m.gid)] += 1
    print('== %s' % path)
    print('   条目=%d  带selinux=%d  符号链接=%d  不同uid/gid组合=%d' % (n, x, link, len(owners)))
    print('   最常见 uid/gid: %s' % owners.most_common(5))
    print('   selinux 上下文样例: %s' % xa_keys.most_common(5))
    for s in samples:
        print('     %-38s mode=%-7s uid=%-4d gid=%-4d %s' % s)
