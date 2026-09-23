#!/usr/bin/env bash
# 分片并发下载 GitHub artifact（免装 aria2；整段校验，绝不追加可疑数据）
set -uo pipefail
export API_URL="$1"; OUT="${2:-artifact.zip}"; N="${3:-16}"; SIZE="${4:-}"
cd "$(dirname "$0")/.."
[ -n "$SIZE" ] || { echo "需要期望字节数作为第 4 个参数"; exit 1; }
mkdir -p parts
curl -s -o /dev/null --ssl-no-revoke -L --max-time 40 -H "Authorization: Bearer $(gh auth token)" \
  -r 0-0 "$API_URL" -w '%{url_effective}' > .sasurl.tmp && [ -s .sasurl.tmp ] && mv -f .sasurl.tmp .sasurl
grep -q 'blob.core.windows.net' .sasurl || { echo 'SAS 解析失败'; exit 1; }
step=$(( (SIZE + N - 1) / N ))
for k in $(seq 0 $((N-1))); do
  s=$((k*step)); e=$((s+step-1)); [ $e -ge $SIZE ] && e=$((SIZE-1))
  [ $s -lt $SIZE ] && printf '%d %d %d\n' "$k" "$s" "$e"
done | xargs -P "$N" -n 3 bash scripts/chunk_get.sh
rc=$?
: > "$OUT"
for k in $(seq 0 $((N-1))); do
  s=$((k*step)); e=$((s+step-1)); [ $e -ge $SIZE ] && e=$((SIZE-1)); want=$((e-s+1))
  p="parts/part.$k"
  got=$(stat -c %s "$p" 2>/dev/null || echo 0)
  [ "$got" = "$want" ] || { echo "分片 $k 长度不符: $got/$want"; rc=1; }
  [ -f "$p" ] && cat "$p" >> "$OUT"
done
GOT=$(stat -c %s "$OUT" 2>/dev/null || echo 0)
echo "拼接后=$GOT 期望=$SIZE rc=$rc"
[ "$GOT" = "$SIZE" ] && [ "$rc" = 0 ] && { rm -rf parts .sasurl; echo "COMPLETE"; } || echo "INCOMPLETE，重跑本脚本可续传"
