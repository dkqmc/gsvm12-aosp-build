#!/usr/bin/env python3
"""在磁盘镜像/分区的 4KiB 对齐位置上找文件系统超级块，并和 file/blkid 交叉验证。

用法: find_ext4.py <device-or-file> [--scan-bytes N]
输出行: DEV  FS_START_BYTES  TYPE  LABEL  EXTRA      （供 mount -o offset= 使用）
"""
import os
import re
import struct
import subprocess
import sys

SB_OFF = 1024          # ext4/erofs 超级块在文件系统内的固定字节偏移
MAGIC_EXT4 = b'\x53\xef'
MAGIC_EROFS = b'\xe2\xf5\xe0\x1e'   # erofs super_magic 小端 (0x0ef5e1e2)
MAGIC_EROFS2 = b'\xe2\xe1\xf5\xe0'


def sh(*cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=120).stdout.strip()
    except Exception as e:
        return 'ERR:%s' % e


def decode_ext4(buf):
    """buf = 超级块起始的 256 字节"""
    inodes = struct.unpack('<I', buf[0:4])[0]
    blocks_lo = struct.unpack('<I', buf[4:8])[0]
    log_bs = struct.unpack('<I', buf[24:28])[0]
    bpg = struct.unpack('<I', buf[32:36])[0]
    ipg = struct.unpack('<I', buf[36:40])[0]
    if log_bs > 2:
        return None
    blk = 1024 << log_bs
    # s_magic 的真实位置在若干文档里被写作 48 或 56，两种都判一次
    where = 56 if buf[56:58] == MAGIC_EXT4 else (48 if buf[48:50] == MAGIC_EXT4 else None)
    if where is None:
        return None
    vol_a = buf[120:136].split(b'\x00')[0].decode('utf8', 'replace')
    vol_b = buf[116:132].split(b'\x00')[0].decode('utf8', 'replace')
    inc = struct.unpack('<I', buf[96:100])[0]
    return {'magic_at': where, 'block_size': blk, 'inodes': inodes,
            'blocks_lo': blocks_lo, 'blocks_per_group': bpg, 'inodes_per_group': ipg,
            'vol@120': vol_a, 'vol@116': vol_b, 'raw_incompat': hex(inc)}


def scan(path, size):
    f = open(path, 'rb')
    pos, out = 0, []
    CHUNK = 64 << 20
    while pos < size:
        n = min(CHUNK, size - pos)
        f.seek(pos)
        buf = f.read(n)
        for a in range(0, len(buf) - (SB_OFF + 140), 4096):
            at = pos + a + SB_OFF
            tag = None
            if buf[a + SB_OFF + 56:a + SB_OFF + 58] == MAGIC_EXT4:
                tag = 'ext4(@+56)'
            elif buf[a + SB_OFF + 48:a + SB_OFF + 50] == MAGIC_EXT4:
                tag = 'ext4(@+48)'
            elif buf[a + SB_OFF:a + SB_OFF + 4] in (MAGIC_EROFS, MAGIC_EROFS2):
                tag = 'erofs'
            if not tag:
                continue
            sb = buf[a + SB_OFF:a + SB_OFF + 256]
            info = decode_ext4(sb) if tag.startswith('ext4') else None
            out.append((pos + a, tag, sb, info))
        pos += n
    f.close()
    return out


def main():
    dev = sys.argv[1]
    min_bytes = 8 << 20
    limit = 0
    if len(sys.argv) > 3 and sys.argv[2] == '--scan-bytes':
        limit = int(sys.argv[3], 0)
    if '--min-size' in sys.argv:
        min_bytes = int(sys.argv[sys.argv.index('--min-size') + 1]) << 20   # 参数按 MiB
    # 若传入的是 losetup 设备，遍历它的分区
    targets = [dev]
    parent = os.path.basename(dev)
    if os.path.exists('/sys/class/block/%s' % parent):
        kids = [k for k in os.listdir('/sys/class/block')
                if k.startswith(parent + 'p') and re.fullmatch(re.escape(parent) + r'p\d+', k)]
        if kids:
            targets = ['/dev/%s' % k for k in sorted(kids)]
    for t in targets:
        try:
            size = os.path.getsize(t) if not limit else min(limit, os.path.getsize(t))
        except OSError:
            print('%s 无法取大小' % t)
            continue
        print('# %s size=%.2f GiB' % (t, size / 2**30))
        hits = scan(t, size)
        if not hits:
            print('  未发现超级块')
        for start, tag, sb, info in hits[:200]:
            label = ''
            if info:
                label = info.get('vol@120') or info.get('vol@116') or ''
                if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,15}', label.strip()):
                    label = ''      # 不是合法卷标（apex 内嵌镜像等）就当无标签
                # 过滤：容量太小或卷标是二进制垃圾的多半是 apex/镜像内嵌片段
                if info['blocks_lo'] * info['block_size'] < min_bytes:
                    continue
                extra = 'bs=%d blocks=%d size=%.2fGiB inodes=%d' % (
                    info['block_size'], info['blocks_lo'],
                    info['blocks_lo'] * info['block_size'] / 2**30, info['inodes'])
            else:
                extra = sb[4:24].hex()
            # 交叉验证：把该起点之后 8KiB 喂给 file（若本机没有 file 则跳过）
            with open(t, 'rb') as g:
                g.seek(start)
                blob = g.read(8192)
            probe = os.path.join(__import__('tempfile').gettempdir(), '_probe.bin')
            with open(probe, 'wb') as w:
                w.write(blob)
            fk = sh('file', '-bs', probe)[:110]
            safe = lambda s: str(s).encode('ascii', 'backslashreplace').decode()
            if '--csv' in sys.argv:
                if info is None:
                    continue      # 超级块字段解码不通，丢弃
                # 只有 file 也认出 ext2/ext4 的才算真文件系统，滤掉 apex 内嵌片段
                # （本机没有 file 命令时退化为按超级块字段判断）
                if not fk.startswith('ERR') and not re.search(r'ext[234] filesystem data', fk):
                    continue
                print('FSSTART\t%d\t%s\t%s\t%s' % (
                    start, tag, label.strip() or '-',
                    '%d' % (info['blocks_lo'] * info['block_size']) if info else '-'))
            else:
                print('  FSSTART=0x%09x (%d)  %-11s label=%-12s %s' %
                      (start, start, tag, safe(label[:12]), safe(extra)))
                print('      file验证: %s' % safe(fk))
    print('# 参考: losetup 分区表 -> %s' % sh('lsblk', '-o', 'NAME,SIZE,FSTYPE,LABEL', dev))


if __name__ == '__main__':
    main()
