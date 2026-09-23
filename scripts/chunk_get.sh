#!/usr/bin/env bash
# 取一段：i s e —— 只补本地分片缺的尾巴，追加前校验长度（不追加可疑数据）
set -uo pipefail
cd "$(dirname "$0")/.."
i=$1; s=$2; e=$3; p="parts/part.$i"; want=$((e - s + 1))
for a in $(seq 1 80); do
  got=$(stat -c %s "$p" 2>/dev/null || echo 0)
  [ "$got" = "$want" ] && exit 0
  [ "$got" -gt "$want" ] && rm -f "$p" && continue          # 多余数据说明错位，整段重来
  if [ ! -s .sasurl ] || [ $(( $(date +%s) - $(stat -c %Y .sasurl) )) -gt 420 ]; then
    curl -s -o /dev/null --ssl-no-revoke -L --max-time 40 \
      -H "Authorization: Bearer $(gh auth token)" -r 0-0 "$API_URL" -w '%{url_effective}' > ".sasurl.$$" \
      && [ -s ".sasurl.$$" ] && mv -f ".sasurl.$$" .sasurl
  fi
  U=$(head -c 4000 .sasurl | tr -d '\r\n')
  case "$U" in https://*blob.core.windows.net*) : ;; *) sleep 2; continue ;; esac
  need=$((want - got))
  rm -f ".tmp.$i"
  if curl -sS --fail --ssl-no-revoke -r $((s + got))-$e --max-time 900 -o ".tmp.$i" "$U" \
     && [ "$(stat -c %s ".tmp.$i")" = "$need" ]; then
    cat ".tmp.$i" >> "$p" && rm -f ".tmp.$i"
  else
    rm -f ".tmp.$i"; sleep 1
  fi
done
exit 1
