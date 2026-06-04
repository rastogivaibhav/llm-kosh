#!/usr/bin/env bash
# Smoke demo: runs the full master-plan v1.0 workflow against a throwaway cartridge.
# Pure stdlib, no internet. Exits non-zero if any step fails.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
CART="${1:-$(mktemp -d)/AI-Cartridge}"
PY="python3 $HERE/llm_kosh_cli.py --root $CART"

echo "== smoke demo =="
echo "cartridge: $CART"
echo

echo "--- init ---"
$PY init --owner "Vaibhav Rastogi"

echo "--- import (uses bundled fixture) ---"
if [ -f "$HERE/fixtures/chatgpt_export.zip" ]; then
  $PY import-chatgpt "$HERE/fixtures/chatgpt_export.zip" --project "AI Portfolio"
fi

echo "--- add a decision ---"
$PY add --kind decision --project "SelectiveOS" \
  --title "AI lessons require teacher approval" \
  --body "Generated lessons must go to a teacher queue before student visibility."

echo "--- embed (tfidf) ---"
$PY embed --backend tfidf

echo "--- pack for chatgpt ---"
$PY pack "SelectiveOS AI lessons and registration" --for chatgpt --out "$CART/selectiveos.zip" --include-private
$PY validate-pack "$CART/selectiveos.zip"
$PY explain-pack "$CART/selectiveos.zip"

echo "--- simulate an LLM MEMORY_RECEIPT, then absorb ---"
cat > "$CART/MEMORY_RECEIPT.md" <<'RCPT'
# MEMORY_RECEIPT
## New decisions
- Parents get a weekly progress digest :: opt-in email summary [project: SelectiveOS]
## Corrections
- AI lessons require teacher approval before students see them :: confirm teacher queue gate
## Open gaps
- Need a DPIA for storing student answers
RCPT
$PY absorb "$CART/MEMORY_RECEIPT.md"

echo "--- resolve / audit / heal ---"
$PY resolve
$PY audit
$PY heal --safe

echo "--- daily artifacts ---"
$PY today
$PY daily-pack --out "$CART/today.zip"
$PY static-site

echo "--- backup ---"
$PY export-backup --out "$CART/cartridge-backup.zip"

echo
echo "== smoke demo OK =="
echo "artifacts under: $CART"
