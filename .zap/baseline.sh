#!/usr/bin/env bash
# OWASP ZAP baseline scan of one krtr URL (task 7.4 of docs/guia-web-seguridad_modal.md).
#
# Runs ZAP's passive baseline (a 1-minute spider plus passive rules, no attacks) against the
# target and then applies the task's acceptance: no High alert at all, and every Medium alert
# accepted in .zap/rules.tsv with its justification. Used by .github/workflows/zap.yml and
# runnable as is on a laptop with Docker (Colima):
#
#   .zap/baseline.sh <target-url> <report-name>
#
# Reports land in .zap/reports/<report-name>.{html,json,md} (git-ignored).
set -euo pipefail

ZAP_IMAGE="ghcr.io/zaproxy/zaproxy@sha256:781a2bdaea47324e7bab583e2263f21d257b0aee61ed51521a5be45f5f5081ef" # 2.17.0
HIGH=3
MEDIUM=2

target="$1"
name="$2"
zap_dir="$(cd "$(dirname "$0")" && pwd)"
reports="$zap_dir/reports"
mkdir -p "$reports"
cp "$zap_dir/rules.tsv" "$reports/rules.tsv"
chmod -R a+rwX "$reports" # ZAP runs as its own user inside the container.

# -I: ZAP's own WARN verdicts do not fail the run; the policy below decides.
docker run --rm -v "$reports:/zap/wrk:rw" "$ZAP_IMAGE" zap-baseline.py \
  -t "$target" -c rules.tsv -I -m 1 \
  -r "$name.html" -J "$name.json" -w "$name.md" || status=$?
if [ "${status:-0}" -gt 1 ]; then
  echo "ZAP could not scan $target (exit ${status})"; exit "$status"
fi

accepted=$(awk -F'\t' '$2 == "IGNORE" { print $1 }' "$zap_dir/rules.tsv" | paste -sd, -)
failures=$(jq -r --argjson high "$HIGH" --argjson medium "$MEDIUM" --arg accepted "$accepted" '
  ($accepted | split(",")) as $ok
  | .site[].alerts[]
  | select((.riskcode | tonumber) == $high
           or ((.riskcode | tonumber) == $medium and (.pluginid | IN($ok[]) | not)))
  | "[\(.pluginid)] \(.name) (\(.riskdesc))"
' "$reports/$name.json")
if [ -n "$failures" ]; then
  echo "FAIL: High alerts, or Medium alerts not accepted in .zap/rules.tsv:"
  echo "$failures"
  exit 1
fi
echo "OK: no High alert and no unaccepted Medium alert on $target"
