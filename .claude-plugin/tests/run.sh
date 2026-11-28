#!/usr/bin/env bash
# Runs one scenario headless against the fake gcloud, gh and git and checks expect.txt.
# Usage: .claude-plugin/tests/run.sh <scenario>
# Env:   TEST_MODEL (default: sonnet)
#        RUN_MODE=direct: no model. Runs the plugin command that prompt.txt names
#        (/<plugin>:<skill> args runs <this repository>/.claude-plugin/plugins/<plugin>/
#        bin/<plugin> <skill> args, by its full path, as a shell runs the command of its
#        own plugin's folder) with the fakes and every plugin's bin/ on PATH; its stdout
#        is the answer. Exit 3 and "NOT CONVERTED <scenario>" when the prompt is not one
#        slash command of a skill, or the command answers 64 (that skill or mode is not
#        converted). While an answer's block says `continue`, the command of its `next:`
#        line runs next (the full real path of the same command, in double quotes, the
#        same skill, the same arguments and one run=; at most eight commands); the last
#        command's stdout is the answer.
#        In both modes a file `clock` (one line `sleep-counts`) makes each logged
#        `sleep 30` move the run's clock by 30 s, a file `step-limit` (one line: a whole
#        number of seconds from 1 to 240) sets ALEOGR_STEP_LIMIT, a file `random` (one
#        line: 1 to 12 of a-z and 0-9) sets ALEOGR_TEST_RANDOM, and a folder `after/`
#        rewrites the working folder on a call (bin/fake-cli: FAKE_AFTER, FAKE_FOLDER).
#        In the direct mode a scenario with a `random` file runs the command of the
#        first line of its prompt (the lines after it are for the model only).
set -u

if [ $# -ne 1 ]; then echo "usage: run.sh <scenario>" >&2; exit 2; fi
case "${RUN_MODE:-}" in
  ''|direct) ;;
  *) echo "unknown RUN_MODE '${RUN_MODE}' (unset, or direct)" >&2; exit 2 ;;
esac

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
plugins="$(cd "$here/../plugins" && pwd -P)"
repo="$(cd "$here/../.." && pwd)"
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

# A file `clock` holding the one line `sleep-counts`: each `sleep <n>` the fake logs
# moves the run's clock by <n> seconds (ALEOGR_TEST_SLEEP_CLOCK, a test aid of the
# shared module that only shortens a run and only works with FAKE_LOG set). Both modes
# set it: in the default mode the model's commands inherit it from claude.
sleep_clock=""
if [ -e "$scenario/clock" ]; then
  if [ "$(cat "$scenario/clock")" = sleep-counts ]; then sleep_clock=1
  else echo "bad clock file (one line: sleep-counts): $scenario/clock" >&2; exit 2; fi
fi
# A file `step-limit` holding one whole number of seconds from 1 to 240: the run's step
# limit (ALEOGR_STEP_LIMIT, a test aid that can only lower it). Every command still
# makes one step after its plan, so a limit shorter than a plan makes each command of
# the run make exactly one step. Both modes set it, as for `clock`.
step_limit=""
if [ -e "$scenario/step-limit" ]; then
  step_limit="$(cat "$scenario/step-limit")"
  case "$step_limit" in
    [1-9]|[1-9][0-9]|1[0-9][0-9]|2[0-3][0-9]|240) ;;
    *) echo "bad step-limit file (one line: 1 to 240): $scenario/step-limit" >&2; exit 2 ;;
  esac
fi
# A file `random` holding one line of 1 to 12 characters of a-z and 0-9: the `<random>`
# that the shared module's random-suffix helper gives (ALEOGR_TEST_RANDOM, a test aid
# honoured only with FAKE_LOG set, and only for a `<random>` of its length: the suffix of
# a new project id). Both modes set it. In the direct mode the command is then the first
# line of prompt.txt: a second line tells the model the same suffix.
random_value=""
if [ -e "$scenario/random" ]; then
  random_value="$(cat "$scenario/random")"
  if ! [[ "$random_value" =~ ^[a-z0-9]{1,12}$ ]]; then
    echo "bad random file (one line: 1 to 12 of a-z and 0-9): $scenario/random" >&2; exit 2
  fi
fi
# A folder `after/` of the scenario: each of its folders, named as a response file is
# named (a prefix of the call, spaces and "/" written "_"), holds files that the fake
# copies over the working folder when a call matching that prefix is made (such as the
# pull that brings a merged declaration). FAKE_FOLDER is the working folder.
after=""
if [ -d "$scenario/after" ]; then after="$scenario/after"; fi

if [ "${RUN_MODE:-}" = direct ]; then
  err="$work/command.err"
  # The prompt, one line "/<plugin>:<skill> key=value ...", split as a shell would split
  # words (quotes), with no expansion of any kind; NUL-separated: plugin, skill, args.
  # With a `random` file, only the first line is the command.
  if ! PYTHONDONTWRITEBYTECODE=1 python3 -I -c '
import re, shlex, sys
text = open(sys.argv[1], encoding="utf-8").read()
if sys.argv[2] == "first-line":
    text = text.split("\n", 1)[0]
if text.endswith("\n"):
    text = text[:-1]
m = re.match(r"/([a-z0-9-]+):([a-z][a-z0-9_-]*)(?: (.*))?$", text)
if "\n" in text or "\r" in text or not m:
    sys.exit(3)
try:
    words = shlex.split(m.group(3) or "")
except ValueError:
    sys.exit(3)
sys.stdout.write("".join(w + "\0" for w in [m.group(1), m.group(2)] + words))
' "$scenario/prompt.txt" "${random_value:+first-line}" > "$work/argv"; then
    echo "NOT CONVERTED $1"
    exit 3
  fi
  argv=()
  while IFS= read -r -d '' w; do argv+=("$w"); done < "$work/argv"
  command_path="$plugins/${argv[0]}/bin/${argv[0]}"
  if [ ! -x "$command_path" ]; then echo "NOT CONVERTED $1"; exit 3; fi
  bins=""
  for b in "$plugins"/*/bin; do bins="$bins:$b"; done
  # A run in more than one command: while the answer's block says `continue`, run the
  # command of its `next:` line (the same plugin command, by the full real path of its
  # executable, the same skill, the same arguments and one `run=`), at most eight
  # commands in all. The answer is the last command's stdout; the call log and stderr
  # are the whole run's.
  cmd=("$command_path" "${argv[@]:1}")
  commands=0
  loop_error=""
  : > "$err"
  : > "$work/commands"
  while :; do
    commands=$((commands + 1))
    printf '%s\n' "${cmd[*]}" >> "$work/commands"
    (
      cd "$work/cwd" || exit 1
      unset ALEOGR_RUN_ENDS ALEOGR_STEP_LIMIT ALEOGR_WAIT_CLOCK_LIMIT ALEOGR_TEST_SLEEP_CLOCK
      unset ALEOGR_TEST_RANDOM FAKE_AFTER FAKE_FOLDER
      if [ -n "$sleep_clock" ]; then export ALEOGR_TEST_SLEEP_CLOCK=1; fi
      if [ -n "$random_value" ]; then export ALEOGR_TEST_RANDOM="$random_value"; fi
      if [ -n "$step_limit" ]; then export ALEOGR_STEP_LIMIT="$step_limit"; fi
      if [ -n "$after" ]; then export FAKE_AFTER="$after" FAKE_FOLDER="$work/cwd"; fi
      PATH="$here/bin$bins:$PATH" FAKE_LOG="$log" FAKE_RESPONSES="$scenario/responses" \
        PYTHONDONTWRITEBYTECODE=1 "${cmd[@]}" < /dev/null > "$out" 2>> "$err"
    )
    claude_status=$?
    if [ "$commands" -eq 1 ] && [ "$claude_status" -eq 64 ]; then echo "NOT CONVERTED $1"; exit 3; fi
    [ "$claude_status" -eq 0 ] || break
    # 0: `continue`, the next command NUL-separated in $work/next; 1: the run ended;
    # 2: a `continue` whose next: line is missing or not this command.
    PYTHONDONTWRITEBYTECODE=1 python3 -I -c '
import json, os, shlex, sys
out = open(sys.argv[1], encoding="utf-8").read().splitlines()
argv = [w for w in open(sys.argv[2], encoding="utf-8").read().split("\0")[:-1]]
# The command is the one this harness ran first, by the full real path of its executable.
argv[0] = os.path.realpath(sys.argv[3])
starts = [i for i, l in enumerate(out) if l.strip().startswith("```aleogr-result")]
if not starts:
    sys.exit(1)
start = starts[-1]
end = next((i for i in range(start + 1, len(out)) if out[i].strip() == "```"), None)
try:
    block = json.loads("\n".join(out[start + 1:end]))
except ValueError:
    sys.exit(1)
if not isinstance(block, dict) or block.get("status") != "continue":
    sys.exit(1)
nexts = [l for l in out[:start] if l.startswith("next: ")]
if not nexts:
    sys.exit(2)
try:
    words = shlex.split(nexts[-1][len("next: "):])
except ValueError:
    sys.exit(2)
plain = lambda ws: [w for w in ws if not w.startswith("run=")]
if words[:2] != argv[:2] or plain(words[2:]) != plain(argv[2:]) \
        or len(words) - len(plain(words)) != 1 or not words[-1].startswith("run="):
    sys.exit(2)
sys.stdout.write("".join(w + "\0" for w in words))
' "$out" "$work/argv" "$command_path" > "$work/next"
    case $? in
      0) ;;
      1) break ;;
      *) loop_error="(the answer says continue, but its next: line is not this command)"; break ;;
    esac
    if [ "$commands" -ge 8 ]; then
      loop_error="(the run did not end within eight commands)"; break
    fi
    cmd=()
    while IFS= read -r -d '' w; do cmd+=("$w"); done < "$work/next"
  done
else
(
  cd "$work/cwd" || exit 1
  unset ALEOGR_TEST_SLEEP_CLOCK ALEOGR_STEP_LIMIT ALEOGR_TEST_RANDOM FAKE_AFTER FAKE_FOLDER
  if [ -n "$sleep_clock" ]; then export ALEOGR_TEST_SLEEP_CLOCK=1; fi
  if [ -n "$random_value" ]; then export ALEOGR_TEST_RANDOM="$random_value"; fi
  if [ -n "$step_limit" ]; then export ALEOGR_STEP_LIMIT="$step_limit"; fi
  if [ -n "$after" ]; then export FAKE_AFTER="$after" FAKE_FOLDER="$work/cwd"; fi
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
fi
# Claude Code's own call (git ... ls-files --error-unmatch -- :(icase).claude/settings.local.json)
# reaches the fake git through PATH; it is not the skill's, so it is dropped from the log.
grep -vF 'ls-files --error-unmatch -- :(icase).claude/settings.local.json' "$log" > "$log.skill" || true
mv "$log.skill" "$log"

failed=()
if [ "${RUN_MODE:-}" = direct ]; then
  if [ "$claude_status" -ne 0 ]; then failed+=("(the command exited with status $claude_status)"); fi
  if [ -n "$loop_error" ]; then failed+=("$loop_error"); fi
elif [ "$claude_status" -ne 0 ]; then failed+=("(claude exited with status $claude_status)"); fi
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
    AT_MOST)
      # AT_MOST <n> <regex>: at most <n> logged calls match (COUNT is "at least").
      n="${arg%% *}"; re="${arg#* }"
      case "$n" in ''|*[!0-9]*) echo "bad AT_MOST number: $line" >&2; ok=0 ;; *)
        [ "$(grep -Ec -- "$re" "$log")" -le "$n" ] || ok=0 ;;
      esac
      ;;
    COMMANDS)
      # COMMANDS <n>: the run took exactly <n> commands (the first and its next: ones).
      # The direct mode only: with the model the loop is the model's, and the line is
      # not checked.
      case "$arg" in ''|*[!0-9]*) echo "bad COMMANDS number: $line" >&2; ok=0 ;; *)
        if [ "${RUN_MODE:-}" = direct ] && [ "$commands" -ne "$arg" ]; then ok=0; fi ;;
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
    SAME_FILE)
      # SAME_FILE <relative path> <repository path>: the file exists and is byte for byte
      # the repository's file (cmp), such as a template the skill copies unchanged.
      f="${arg%% *}"; ref="${arg#* }"
      if [ "$kind" = "$line" ] || [ "$ref" = "$arg" ] || [ -z "$ref" ]; then
        echo "bad expect line (SAME_FILE needs a path and a repository path): $line" >&2; ok=0
      else
        { [ -f "$work/cwd/$f" ] && [ -f "$repo/$ref" ] && cmp -s -- "$work/cwd/$f" "$repo/$ref"; } || ok=0
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
if [ -s "$log" ]; then sed -E -e '/^(gh|git|go|sleep) /!s/^/gcloud /' -e 's/^/  /' "$log"; else echo "  (no calls)"; fi
if [ "${RUN_MODE:-}" = direct ]; then
  echo "commands ($commands):"
  sed 's/^/  /' "$work/commands"
  echo "command exit status: $claude_status"
  echo "command output (the last command's):"
  sed 's/^/  /' "$out"
  echo "command stderr:"
  sed 's/^/  /' "$err"
  exit 1
fi
echo "claude exit status: $claude_status"
echo "claude output:"
sed 's/^/  /' "$out"
exit 1
