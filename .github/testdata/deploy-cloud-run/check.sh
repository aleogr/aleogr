#!/usr/bin/env bash
# Static check of the reusable deploy workflow. Needs only bash and grep.
#
# Usage: check.sh [path]   (default: .github/workflows/deploy-cloud-run.yml)
#
# Fails unless the file:
#   - has `workflow_call` as its only trigger;
#   - contains none of the forbidden strings (another trigger that runs with
#     the base repository's rights, a create or a change of access on the
#     service, a secret);
#   - pins every `uses:` by a full 40-character commit SHA;
#   - masks the project id, the project number and the service account in the
#     first step of its one job;
#   - puts no `${{ }}` expression inside a script;
#   - replaces the image by digest only, refusing a digest that is not sha256.

set -u

file="${1:-.github/workflows/deploy-cloud-run.yml}"
failures=0

fail() {
  echo "FAIL: $1"
  failures=$((failures + 1))
}

if [ ! -s "$file" ]; then
  echo "FAIL: $file is missing or empty"
  exit 1
fi

# 1. The only trigger is workflow_call.
if [ "$(grep -c '^on:$' "$file")" != 1 ]; then
  fail "expected exactly one block-form 'on:' line"
fi
triggers=""
in_on=0
while IFS= read -r line; do
  if [ "$in_on" = 1 ]; then
    [[ "$line" =~ ^[[:space:]]*(#|$) ]] && continue
    [[ "$line" =~ ^[^[:space:]] ]] && break
    if [[ "$line" =~ ^\ \ ([A-Za-z_]+): ]]; then
      triggers="$triggers ${BASH_REMATCH[1]}"
    fi
  elif [ "$line" = "on:" ]; then
    in_on=1
  fi
done <"$file"
if [ "$triggers" != " workflow_call" ]; then
  fail "the triggers are '${triggers# }', expected only 'workflow_call'"
fi

# 2. Forbidden strings.
for forbidden in pull_request_target workflow_run 'run deploy' '--iap' \
  allow-unauthenticated add-iam-policy-binding 'secrets.' 'secrets:'; do
  if grep -qF -e "$forbidden" "$file"; then
    fail "contains the forbidden string '$forbidden'"
  fi
done

# 3. Every action pinned by a full commit SHA.
if ! grep -qE '^[[:space:]]*(-[[:space:]]+)?uses:' "$file"; then
  fail "no 'uses:' line found"
fi
while IFS= read -r line; do
  if ! [[ "$line" =~ uses:\ [A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+@[0-9a-f]{40}(\ |$) ]]; then
    fail "not pinned by a 40-character commit SHA: ${line#"${line%%[![:space:]]*}"}"
  fi
done < <(grep -E '^[[:space:]]*(-[[:space:]]+)?uses:' "$file")

# 4. One job; its first step masks the three identifiers.
if [ "$(grep -cE '^[[:space:]]+steps:[[:space:]]*$' "$file")" != 1 ]; then
  fail "expected exactly one 'steps:' (one job)"
fi
first_step=""
in_steps=0
step_indent=""
while IFS= read -r line; do
  if [ "$in_steps" = 0 ]; then
    [[ "$line" =~ ^[[:space:]]+steps:[[:space:]]*$ ]] && in_steps=1
    continue
  fi
  if [ -z "$step_indent" ]; then
    if [[ "$line" =~ ^([[:space:]]+)-\  ]]; then
      step_indent="${BASH_REMATCH[1]}"
      first_step="$line"
    fi
    continue
  fi
  # The next item at the same indent, or anything less indented, ends the step.
  if [[ "$line" == "$step_indent- "* ]]; then
    break
  fi
  if [ -n "$line" ] && ! [[ "$line" == "$step_indent "* ]]; then
    break
  fi
  first_step="$first_step"$'\n'"$line"
done <"$file"
if [ -z "$first_step" ]; then
  fail "no first step found"
else
  if [ "$(grep -cF '::add-mask::' <<<"$first_step")" -lt 3 ]; then
    fail "the first step does not register three '::add-mask::'"
  fi
  if grep -qE '^[[:space:]]+(-[[:space:]]+)?uses:' <<<"$first_step"; then
    fail "the first step is an action, not the masking script"
  fi
  for input in project-id service-account workload-identity-provider; do
    if ! grep -qF "\${{ inputs.$input }}" <<<"$first_step"; then
      fail "the first step does not receive inputs.$input"
    fi
  done
fi

# 5. No expression inside a script: every `${{` sits on a `key: value` line
#    whose key is not `run`.
while IFS= read -r line; do
  if ! [[ "$line" =~ ^[[:space:]]*(-[[:space:]]+)?[A-Za-z0-9_-]+:\  ]] ||
    [[ "$line" =~ ^[[:space:]]*(-[[:space:]]+)?run:\  ]]; then
    fail "expression outside a 'key: value' line: ${line#"${line%%[![:space:]]*}"}"
  fi
done < <(grep -F '${{' "$file")

# 6. The image is replaced by digest, never by tag.
if ! grep -qF 'run services update' "$file"; then
  fail "no 'run services update'"
fi
if ! grep -qE -- '--image=' "$file"; then
  fail "no '--image='"
fi
while IFS= read -r line; do
  if ! [[ "$line" == *'--image="$IMAGE@$DIGEST"'* || "$line" == *'--image="${IMAGE}@${DIGEST}"'* ]]; then
    fail "an --image that is not the digest form: ${line#"${line%%[![:space:]]*}"}"
  fi
done < <(grep -F -- '--image' "$file")
if ! grep -qF '^sha256:[0-9a-f]{64}$' "$file"; then
  fail "the digest is not checked against ^sha256:[0-9a-f]{64}\$"
fi
if ! grep -qF 'steps.build.outputs.digest' "$file"; then
  fail "the digest does not come from the build step's 'digest' output"
fi

if [ "$failures" -gt 0 ]; then
  echo "$failures check(s) failed for $file"
  exit 1
fi
echo "OK: $file"
