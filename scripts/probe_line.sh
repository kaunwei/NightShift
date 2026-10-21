#!/usr/bin/env bash
# ==============================================================================
# 5-Line Code Probe Helper (Standardized Single-Point Auditor)
# Used by Planner or Sentinel to verify line-number claims in SUMMARY.md
# Usage: scripts/probe_line.sh <file>#L<line> OR scripts/probe_line.sh <file> <line>
# ==============================================================================

set -uo pipefail

TARGET="${1:-}"
LINE="${2:-}"

if [[ "$TARGET" =~ ^(.*)#L([0-9]+)$ ]]; then
  TARGET="${BASH_REMATCH[1]}"
  LINE="${BASH_REMATCH[2]}"
fi

if [ -z "$TARGET" ] || [ -z "$LINE" ] || [ ! -f "$TARGET" ]; then
  echo "Usage: $0 <file>#L<line_number>  OR  $0 <file> <line_number>"
  exit 1
fi

START=$(( LINE - 3 ))
[ $START -lt 1 ] && START=1
END=$(( LINE + 3 ))

awk -v s="$START" -v e="$END" -v tgt="$LINE" '
  NR >= s && NR <= e {
    marker = (NR == tgt) ? ">> " : "   ";
    printf "%s%4d | %s\n", marker, NR, $0;
  }
' "$TARGET"
