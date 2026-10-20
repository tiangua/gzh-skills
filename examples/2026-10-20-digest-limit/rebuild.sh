#!/usr/bin/env bash
# 重新生成示例的脚本产物。在仓库根目录运行：bash examples/2026-10-20-digest-limit/rebuild.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
D="$ROOT/examples/2026-10-20-digest-limit"
PY="${PY:-$ROOT/.venv/bin/python}"
cd "$D"
"$PY" "$ROOT/skills/gzh-format/scripts/wechat_html.py" 03-final.md -o 04-article.html --preview 04-preview.html
"$PY" "$ROOT/skills/gzh-cover/scripts/render.py" --spec cover.json --out 05-cover
rm -rf package
"$PY" "$ROOT/skills/gzh-precheck/scripts/check_sources.py" \
  --final 03-final.md --draft 02-draft.md --claims 02-claims.md \
  --html 04-article.html --cover-audit 05-cover-audit.json ${ONLINE:+--online} \
  --json-out 06-precheck.json --report 06-precheck.md --package package
