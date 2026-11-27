#!/usr/bin/env bash
# Runs scenarios in the direct mode (RUN_MODE=direct run.sh: no model, the plugin's
# command against the fakes), in parallel, and prints one line per failure and a summary.
# Usage: .claude-plugin/tests/run-direct.sh [-j <jobs>] [-s <skill>] [<scenario> ...]
#   no scenario: every scenario; -s <skill>: only those whose prompt names that skill
#   (/<plugin>:<skill>, with or without arguments).
# Exit 1 when any scenario failed, 2 on bad usage, otherwise 0. A scenario whose prompt
# is not one slash command of a skill, or whose skill or mode is not converted, counts
# as "not converted", never as a failure.
# Every run has its own temporary folder, call log and response counters, so runs do
# not share state and are safe in parallel.
set -u

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
jobs="$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)"
skill=""
while getopts "j:s:h" opt; do
  case "$opt" in
    j) jobs="$OPTARG" ;;
    s) skill="$OPTARG" ;;
    *) sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//' >&2; exit 2 ;;
  esac
done
shift $((OPTIND - 1))
case "$jobs" in ''|*[!0-9]*|0) echo "bad -j: $jobs" >&2; exit 2 ;; esac

names=()
if [ $# -gt 0 ]; then
  names=("$@")
else
  for d in "$here"/scenarios/*/; do names+=("$(basename "$d")"); done
fi
if [ -n "$skill" ]; then
  kept=()
  for n in "${names[@]}"; do
    first="$(head -n 1 "$here/scenarios/$n/prompt.txt" 2>/dev/null)" || continue
    case "$first" in "/"*":$skill"|"/"*":$skill "*) kept+=("$n") ;; esac
  done
  names=("${kept[@]+"${kept[@]}"}")
fi
if [ ${#names[@]} -eq 0 ]; then echo "no scenario selected" >&2; exit 2; fi

results="$(mktemp -d)"
trap 'rm -rf "$results"' EXIT
printf '%s\0' "${names[@]}" | xargs -0 -P "$jobs" -I{} \
  bash -c 'RUN_MODE=direct bash "$1" "$2" > "$3/$2.out" 2>&1; echo $? > "$3/$2.status"' \
  _ "$here/run.sh" {} "$results"

passed=0; failed=0; skipped=0
for n in "${names[@]}"; do
  status="$(cat "$results/$n.status" 2>/dev/null || echo 1)"
  case "$status" in
    0) passed=$((passed + 1)) ;;
    3) skipped=$((skipped + 1)) ;;
    *)
      failed=$((failed + 1))
      # The first failed expect line, or the first line run.sh printed.
      why="$(sed -n '3s/^  //p' "$results/$n.out")"
      [ -n "$why" ] || why="$(head -n 1 "$results/$n.out")"
      echo "FAIL $n: $why"
      ;;
  esac
done
echo "passed $passed, failed $failed, not converted $skipped"
[ "$failed" -eq 0 ]
