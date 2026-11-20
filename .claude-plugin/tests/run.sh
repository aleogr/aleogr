#!/usr/bin/env bash
# Runs one scenario headless against the fake gcloud, gh and git and checks expect.txt.
# Usage: .claude-plugin/tests/run.sh <scenario>
# Env:   TEST_MODEL (default: sonnet)
set -u

if [ $# -ne 1 ]; then echo "usage: run.sh <scenario>" >&2; exit 2; fi

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
plugins="$(cd "$here/../plugins" && pwd)"
scenario="$here/scenarios/$1"
if [ ! -f "$scenario/prompt.txt" ] || [ ! -f "$scenario/expect.txt" ]; then
  echo "scenario '$1' not found or incomplete: $scenario" >&2
  exit 2
fi

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
mkdir "$work/cwd"
# Files the scenario starts with (dotfiles included) go into the working folder.
if [ -d "$scenario/files" ]; then cp -a "$scenario/files/." "$work/cwd/"; fi
log="$work/calls.log"
out="$work/claude.out"
: > "$log"

(
  cd "$work/cwd" || exit 1
  PATH="$here/bin:$PATH" FAKE_LOG="$log" FAKE_RESPONSES="$scenario/responses" \
    claude -p "$(cat "$scenario/prompt.txt")" \
      --model "${TEST_MODEL:-sonnet}" \
      --plugin-dir "$plugins/aleogr" \
      --plugin-dir "$plugins/aleogr-cloud-gcp" \
      --plugin-dir "$plugins/aleogr-db-gcp-cloud-sql" \
      --plugin-dir "$plugins/aleogr-registry-gcp-artifact-registry" \
      --plugin-dir "$plugins/aleogr-repo-github" \
      --plugin-dir "$plugins/aleogr-stack-go" \
      --allowedTools "Bash" "Skill" "Read" "Write" "Edit" \
      < /dev/null > "$out" 2>&1
)
claude_status=$?
# Claude Code's own call (git ... ls-files --error-unmatch -- :(icase).claude/settings.local.json)
# reaches the fake git through PATH; it is not the skill's, so it is dropped from the log.
grep -vF 'ls-files --error-unmatch -- :(icase).claude/settings.local.json' "$log" > "$log.skill" || true
mv "$log.skill" "$log"

failed=()
if [ "$claude_status" -ne 0 ]; then failed+=("(claude exited with status $claude_status)"); fi
while IFS= read -r line || [ -n "$line" ]; do
  case "$line" in ''|'#'*) continue ;; esac
  kind="${line%% *}"
  arg="${line#* }"
  ok=1
  case "$kind" in
    CALLED)     grep -Eq -- "$arg" "$log" || ok=0 ;;
    NOT_CALLED) ! grep -Eq -- "$arg" "$log" || ok=0 ;;
    COUNT)
      n="${arg%% *}"; re="${arg#* }"
      case "$n" in ''|*[!0-9]*) echo "bad COUNT number: $line" >&2; ok=0 ;; *)
        [ "$(grep -Ec -- "$re" "$log")" -ge "$n" ] || ok=0 ;;
      esac
      ;;
    OUTPUT)     grep -Eq -- "$arg" "$out" || ok=0 ;;
    OUTPUT_NOT) ! grep -Eq -- "$arg" "$out" || ok=0 ;;
    RESULT_NOT)
      # Lines inside the fenced aleogr-result block(s) of the answer; fails when there is none.
      blk="$(awk '/^[[:space:]]*```aleogr-result/ {inb=1; found=1; next}
                  inb && /^[[:space:]]*```[[:space:]]*$/ {inb=0; next}
                  inb {print}
                  END {exit found ? 0 : 1}' "$out")" || ok=0
      if [ "$ok" = 1 ]; then ! printf '%s\n' "$blk" | grep -Eq -- "$arg" || ok=0; fi
      ;;
    FILE)
      # FILE <relative path> <regex>: the file exists and some line matches.
      f="${arg%% *}"; re="${arg#* }"
      if [ "$kind" = "$line" ] || [ "$re" = "$arg" ] || [ -z "$re" ]; then
        echo "bad expect line (FILE needs a path and a regex): $line" >&2; ok=0
      else
        { [ -f "$work/cwd/$f" ] && grep -Eq -- "$re" "$work/cwd/$f"; } || ok=0
      fi
      ;;
    NO_FILE)
      [ ! -e "$work/cwd/$arg" ] || ok=0
      ;;
    FILE_NOT)
      # FILE_NOT <relative path> <regex>: the file is absent, or no line of it matches.
      f="${arg%% *}"; re="${arg#* }"
      if [ "$kind" = "$line" ] || [ "$re" = "$arg" ] || [ -z "$re" ]; then
        echo "bad expect line (FILE_NOT needs a path and a regex): $line" >&2; ok=0
      else
        { [ -f "$work/cwd/$f" ] && grep -Eq -- "$re" "$work/cwd/$f"; } && ok=0
      fi
      ;;
    ORDER)
      first="${arg%% >> *}"; second="${arg#* >> }"
      a="$(grep -En -- "$first" "$log" | head -n1 | cut -d: -f1)"
      b="$(grep -En -- "$second" "$log" | head -n1 | cut -d: -f1)"
      { [ -n "$a" ] && [ -n "$b" ] && [ "$a" -lt "$b" ]; } || ok=0
      ;;
    *) echo "unknown expect line: $line" >&2; ok=0 ;;
  esac
  [ "$ok" = 1 ] || failed+=("$line")
done < "$scenario/expect.txt"

if [ ${#failed[@]} -eq 0 ]; then
  echo "PASS $1"
  exit 0
fi

echo "FAIL $1"
echo "Failed expect lines:"
printf '  %s\n' "${failed[@]}"
echo "call log:"
if [ -s "$log" ]; then sed -E -e '/^(gh|git|sleep) /!s/^/gcloud /' -e 's/^/  /' "$log"; else echo "  (no calls)"; fi
echo "claude exit status: $claude_status"
echo "claude output:"
sed 's/^/  /' "$out"
exit 1
